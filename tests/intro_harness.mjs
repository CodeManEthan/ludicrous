// Loads web/app.js in node, once per case in a fresh context, with a fake
// DOM whose elements remember what is assigned to them, keep their event
// listeners, and record showModal/close/focus calls. fetch and Worker are
// counted, and localStorage is a Map (or throws, or is missing). Prints what
// the page did on load and after each action: whether the welcome popup
// opened, what ran, and what was stored. Driven by tests/test_intro.py.
import fs from "node:fs";
import vm from "node:vm";

const root = new URL("../web/", import.meta.url);
const src = fs.readFileSync(process.env.LUDICROUS_APP_JS ?? new URL("app.js", root), "utf8");
const grid = JSON.parse(fs.readFileSync(new URL("rounds-grid.json", root), "utf8"));

const inert = () => new Proxy(function () {}, {
  get: (_, k) => (k === Symbol.toPrimitive ? () => "" : k === "value" ? "" : inert()),
  set: () => true,
  defineProperty: () => true,
  deleteProperty: () => true,
  apply: () => inert(),
  construct: () => inert(),
});

// Lets pending promises (the grid fetch, playArrival's awaits) settle.
const flush = async () => {
  for (let i = 0; i < 10; i++) await new Promise((r) => setImmediate(r));
};

function boot({ search = "", storage = "map", stored = {}, engine = true, holdGrid = false,
  boxes = {}, narrow = false } = {}) {
  const world = {
    calls: [],          // ["showModal" | "close" | "focus" | "scroll", selector], ["worker"], ...
    fetches: [],
    workers: [],        // each: { messages: [] }
    storageCalls: [],   // [op, key]
    store: new Map(Object.entries(stored)),
    focus: null,
    boxes,              // selector -> {left, top, width, height}, for elements that have a box
    tourTargets: {},    // data-tour key -> [selectors]
    openBoxes: [],      // details.opt-box elements the page sees as open
  };
  const elements = new Map();

  function makeElement(sel) {
    const t = {
      _sel: sel, listeners: {}, open: false, disabled: false, autofocus: false,
      style: {}, dataset: {}, attrs: {},
    };
    const classes = new Set();
    t.classList = {
      add: (...c) => c.forEach((x) => classes.add(x)),
      remove: (...c) => c.forEach((x) => classes.delete(x)),
      toggle: (c, on) => {
        const want = on === undefined ? !classes.has(c) : !!on;
        if (want) classes.add(c); else classes.delete(c);
        return want;
      },
      contains: (c) => classes.has(c),
    };
    let proxy;
    t.addEventListener = (type, fn) => { (t.listeners[type] ||= []).push(fn); };
    t.removeEventListener = (type, fn) => {
      t.listeners[type] = (t.listeners[type] || []).filter((f) => f !== fn);
    };
    t.dispatch = (type, ev = {}) => {
      const event = { target: proxy, preventDefault() {}, ...ev };
      for (const fn of [...(t.listeners[type] || [])]) fn(event);
    };
    t.showModal = () => {
      if (t.open) throw new Error(`showModal on an open dialog: ${sel}`);
      world.calls.push(["showModal", sel]);
      t.open = true;
    };
    t.close = () => {
      if (!t.open) return;
      t.open = false;
      world.calls.push(["close", sel]);
      t.dispatch("close");
    };
    t.focus = () => { world.focus = sel; world.calls.push(["focus", sel]); };
    t.requestSubmit = () => t.dispatch("submit");
    t.click = () => { if (!t.disabled) t.dispatch("click"); };
    t.scrollIntoView = () => { world.calls.push(["scroll", sel]); };
    t.getBoundingClientRect = () => {
      const b = world.boxes[sel] || { left: 0, top: 0, width: 0, height: 0 };
      return { ...b, x: b.left, y: b.top, right: b.left + b.width, bottom: b.top + b.height };
    };
    t.getClientRects = () => (world.boxes[sel] ? [t.getBoundingClientRect()] : []);
    t.setAttribute = (k, v) => { t.attrs[k] = String(v); };
    t.getAttribute = (k) => (k in t.attrs ? t.attrs[k] : null);
    t.removeAttribute = (k) => { delete t.attrs[k]; };
    t.hasAttribute = (k) => k in t.attrs;
    t.contains = (x) => x === proxy;
    t.closest = () => null;
    t.appendChild = (x) => x;
    proxy = new Proxy(t, {
      get: (o, k) => (k in o ? o[k] : k === Symbol.toPrimitive ? () => "" : inert()),
      set: (o, k, v) => { o[k] = k === "value" ? String(v) : v; return true; },
    });
    return proxy;
  }
  const $el = (sel) => {
    if (!elements.has(sel)) elements.set(sel, makeElement(sel));
    return elements.get(sel);
  };

  const listeners = (target) => {
    const map = {};
    return {
      map,
      addEventListener: (type, fn) => { (map[type] ||= []).push(fn); },
      removeEventListener: (type, fn) => { map[type] = (map[type] || []).filter((f) => f !== fn); },
      dispatch: (type, ev = {}) => {
        for (const fn of [...(map[type] || [])]) fn({ preventDefault() {}, ...ev });
      },
    };
  };
  const docL = listeners();
  const winL = listeners();

  const tourMatch = (sel) => /^\[data-tour="([^"]+)"\]$/.exec(sel);
  const document = new Proxy({
    querySelector: $el,
    querySelectorAll: (sel) => {
      if (sel === "details.opt-box[open]") return world.openBoxes.filter((b) => b.open);
      const m = tourMatch(sel);
      return m ? (world.tourTargets[m[1]] || []).map($el) : [];
    },
    createElement: () => makeElement("(new)"),
    addEventListener: docL.addEventListener,
    removeEventListener: docL.removeEventListener,
    get activeElement() { return world.focus ? $el(world.focus) : null; },
    documentElement: $el("html"),
    body: $el("body"),
  }, { get: (o, k) => (k in o ? o[k] : inert()) });

  const window = new Proxy({
    addEventListener: winL.addEventListener,
    removeEventListener: winL.removeEventListener,
    matchMedia: () => ({ matches: narrow, addEventListener() {} }),
    innerWidth: narrow ? 390 : 1280,
    innerHeight: narrow ? 844 : 800,
    scrollX: 0,
    scrollY: 0,
  }, { get: (o, k) => (k in o ? o[k] : inert()) });

  let releaseGrid;
  const gridGate = holdGrid ? new Promise((r) => { releaseGrid = r; }) : Promise.resolve();
  const fetch = (url) => {
    world.fetches.push(String(url));
    if (String(url) === "/rounds-grid.json") {
      return gridGate.then(() => ({ ok: true, json: async () => grid }));
    }
    return new Promise(() => {});
  };
  class Worker {
    constructor(url) {
      this.record = { url, messages: [] };
      world.workers.push(this.record);
      world.calls.push(["worker"]);
    }
    postMessage(message) { this.record.messages.push(JSON.parse(JSON.stringify(message))); }
    terminate() {}
  }

  const globals = {
    window, document, navigator: inert(),
    requestAnimationFrame: () => 0, console, Intl, Math, JSON,
    Number, Object, Array, Map, Set, Symbol, Proxy, Promise, Date, Error, Uint8Array,
    Float32Array, URLSearchParams, location: { search, href: `http://x/${search}` },
    history: { pushState() {}, replaceState() {} }, performance: { now: () => Date.now() },
    setTimeout: () => 0, clearTimeout: () => 0, setInterval: () => 0, clearInterval: () => 0,
    AbortController, fetch, Blob: inert(),
  };
  if (engine) {
    globals.Worker = Worker;
    globals.WebAssembly = {};
  }
  if (storage === "map") {
    globals.localStorage = {
      getItem: (k) => { world.storageCalls.push(["get", k]); return world.store.has(k) ? world.store.get(k) : null; },
      setItem: (k, v) => { world.storageCalls.push(["set", k]); world.store.set(k, String(v)); },
      removeItem: (k) => { world.storageCalls.push(["remove", k]); world.store.delete(k); },
    };
  } else if (storage === "throw") {
    const boom = () => { throw new Error("storage is blocked"); };
    globals.localStorage = new Proxy({}, { get: () => boom });
  }
  // storage === "absent": no localStorage global at all.

  const ctx = vm.createContext(globals);
  let bootError = null;
  try {
    vm.runInContext(src + `
;globalThis.__t = {
  QUERY_KEYS, runPreset,
  simulateBtn: () => $("#simulateBtn"),
};`, ctx, { filename: "app.js" });
  } catch (error) {
    bootError = String(error && error.stack || error);
  }
  return { world, ctx, $el, docL, winL, releaseGrid, bootError, t: ctx.__t };
}

// What a case reports: popup and dialog activity, what ran, what was stored.
function report(page) {
  const { world } = page;
  const introKey = (k) => k === "ludicrous-intro";
  return {
    bootError: page.bootError,
    calls: world.calls,
    introOpened: world.calls.some(([c, s]) => c === "showModal" && s === "#intro"),
    introOpen: page.$el("#intro").open,
    fetches: world.fetches,
    workers: world.workers.length,
    messages: world.workers.flatMap((w) => w.messages),
    flag: world.store.get("ludicrous-intro") ?? null,
    flagCalls: world.storageCalls.filter(([, k]) => introKey(k)),
    focus: world.focus,
  };
}

const out = {};
const RUN_URL = "?engine=v2&players=6&decks=3&max_rounds=0&names=random&seed=1&run=1";

// 1-2. A bare load: the popup with no flag, nothing with it.
for (const [name, opts] of Object.entries({
  bare: {},
  tracking: { search: "?utm_source=x" },
  flagSet: { stored: { "ludicrous-intro": "seen" } },
  flagSetTracking: { search: "?utm_source=x&fbclid=y", stored: { "ludicrous-intro": "seen" } },
})) {
  const page = boot(opts);
  await flush();
  out[name] = report(page);
}

// 3. URLs that name a key the page reads.
for (const [name, search] of Object.entries({ runUrl: RUN_URL, prefill: "?players=6" })) {
  const page = boot({ search });
  await flush();
  out[name] = report(page);
}
out.queryKeys = [...boot().t.QUERY_KEYS];

// 4. Storage that can't be used.
for (const storage of ["throw", "absent"]) {
  const page = boot({ storage });
  await flush();
  out[`storage_${storage}`] = report(page);
}

// 5. Every way out of the popup sets the flag.
const routes = {
  closeButton: (p) => p.$el("#introClose").click(),
  escape: (p) => { p.$el("#intro").dispatch("cancel"); p.$el("#intro").close(); },
  backdrop: (p) => p.$el("#intro").dispatch("click"),
  simulate: (p) => p.$el("#introSimulate").click(),
  tour: (p) => p.$el("#introTour").click(),
  popstate: (p) => p.winL.dispatch("popstate"),
};
out.routes = {};
for (const [name, act] of Object.entries(routes)) {
  const page = boot();
  await flush();
  act(page);
  await flush();
  out.routes[name] = report(page);
}

// A click inside the popup that isn't a control leaves it open.
{
  const page = boot();
  await flush();
  page.$el("#intro").dispatch("click", { target: page.$el("#introText") });
  out.innerClick = report(page);
}

// 5. Without WebAssembly: Simulate a game is disabled, says why, runs nothing.
{
  const page = boot({ engine: false });
  await flush();
  const sim = page.$el("#introSimulate");
  out.noEngine = {
    ...report(page),
    disabled: sim.disabled,
    title: sim.title,
    noteHidden: page.$el("#introNoEngine").hidden,
    simulateAutofocus: sim.autofocus,
    tourAutofocus: page.$el("#introTour").autofocus,
  };
  sim.click();                    // a disabled button: no click event
  page.$el("#introSimulate").dispatch("click");  // and the handler itself refuses too
  await flush();
  out.noEngineAfter = report(page);
}
{
  const page = boot();
  await flush();
  out.withEngine = {
    disabled: page.$el("#introSimulate").disabled,
    noteHidden: page.$el("#introNoEngine").hidden,
    simulateAutofocus: page.$el("#introSimulate").autofocus,
    tourAutofocus: page.$el("#introTour").autofocus,
  };
}

// The page ignores keys while the popup is open: Escape doesn't reach an
// open Options popover behind it. Without the popup, the same Escape closes it.
for (const [name, opts] of Object.entries({ keysPopupOpen: {}, keysNoPopup: { stored: { "ludicrous-intro": "seen" } } })) {
  const page = boot(opts);
  await flush();
  const box = page.$el("#advancedBox");
  box.open = true;
  page.world.openBoxes.push(box);
  page.docL.dispatch("keydown", { key: "Escape", code: "Escape", target: page.$el("body") });
  out[name] = { boxOpen: box.open };
}

process.stdout.write(JSON.stringify(out));
