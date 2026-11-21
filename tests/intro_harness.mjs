// Loads web/app.js in node, once per case in a fresh context, with a fake
// DOM whose elements remember what is assigned to them, keep their event
// listeners, and record showModal/close/focus calls. fetch and Worker are
// counted, and localStorage and sessionStorage are each a Map (or throw, or
// are missing). Prints what
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

function boot({ search = "", storage = "map", stored = {}, session = "map", sessionStored = {},
  engine = true, holdGrid = false, boxes = {}, narrow = false } = {}) {
  const world = {
    calls: [],          // ["showModal" | "close" | "focus" | "scroll", selector], ["worker"],
                        // ["set", "local" | "session", key, value], ...
    fetches: [],
    workers: [],        // each: { messages: [] }
    storageCalls: [],   // [op, key, "local" | "session"]
    store: new Map(Object.entries(stored)),            // localStorage
    session: new Map(Object.entries(sessionStored)),   // sessionStorage
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
    t.replaceChildren = (...nodes) => { t.children = nodes; };
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
    // Import reads the file at once.
    FileReader: class { readAsText(file) { this.result = file.text; this.onload(); } },
  };
  if (engine) {
    globals.Worker = Worker;
    globals.WebAssembly = {};
  }
  // Both stores log into storageCalls with a tag, and log each set into
  // calls too, so a case can see a write's order against the dialog's close.
  // "absent" leaves the global out altogether.
  const makeStore = (kind, map, tag) => {
    if (kind === "map") {
      return {
        getItem: (k) => { world.storageCalls.push(["get", k, tag]); return map.has(k) ? map.get(k) : null; },
        setItem: (k, v) => {
          world.storageCalls.push(["set", k, tag]);
          world.calls.push(["set", tag, k, String(v)]);
          map.set(k, String(v));
        },
        removeItem: (k) => { world.storageCalls.push(["remove", k, tag]); map.delete(k); },
      };
    }
    if (kind === "throw") {
      const boom = () => { throw new Error("storage is blocked"); };
      return new Proxy({}, { get: () => boom });
    }
    return undefined;
  };
  if (storage !== "absent") globals.localStorage = makeStore(storage, world.store, "local");
  if (session !== "absent") globals.sessionStorage = makeStore(session, world.session, "session");

  const ctx = vm.createContext(globals);
  let bootError = null;
  try {
    vm.runInContext(src + `
;globalThis.__t = {
  QUERY_KEYS, TOUR_STEPS,
  tour: () => (tour ? { keys: tour.steps.map((s) => s.key), index: tour.index } : null),
  play: () => { playing = true; },
  playing: () => playing,
};`, ctx, { filename: "app.js" });
  } catch (error) {
    bootError = String(error && error.stack || error);
  }
  // The tour panel's size, and the viewport width the page measures.
  $el("#tourPanel").offsetWidth = 340;
  $el("#tourPanel").offsetHeight = 150;
  $el("html").clientWidth = window.innerWidth;
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
    session: world.session.get("ludicrous-intro") ?? null,
    flagCalls: world.storageCalls.filter(([, k]) => introKey(k)),
    flagSets: world.storageCalls.filter(([op, k]) => op === "set" && introKey(k)),
    focus: world.focus,
  };
}

const out = {};
const RUN_URL = "?engine=v2&players=6&decks=3&max_rounds=0&names=random&seed=1&run=1";

// 1-2. A bare load: the popup with neither flag, nothing with either. The
// "seen" value older builds stored doesn't keep it shut.
const CLOSED = { sessionStored: { "ludicrous-intro": "closed" } };
const NEVER = { stored: { "ludicrous-intro": "never" } };
for (const [name, opts] of Object.entries({
  bare: {},
  tracking: { search: "?utm_source=x" },
  closedForNow: CLOSED,
  closedForNowTracking: { search: "?utm_source=x&fbclid=y", ...CLOSED },
  never: NEVER,
  neverTracking: { search: "?utm_source=x&fbclid=y", ...NEVER },
  oldSeen: { stored: { "ludicrous-intro": "seen" } },
})) {
  const page = boot(opts);
  await flush();
  out[name] = report(page);
}

// 3. URLs that name a key the page reads, with empty stores and with both
// flags set.
for (const [name, search] of Object.entries({ runUrl: RUN_URL, prefill: "?players=6" })) {
  for (const [suffix, opts] of Object.entries({ "": {}, Flags: { ...NEVER, ...CLOSED } })) {
    const page = boot({ search, ...opts });
    await flush();
    out[name + suffix] = report(page);
  }
}
out.queryKeys = [...boot().t.QUERY_KEYS];

// 4. Storage that can't be used: either store throwing or missing. With
// localStorage blocked, "Don't show again" still closes the popup.
for (const kind of ["throw", "absent"]) {
  {
    const page = boot({ storage: kind });
    await flush();
    out[`storage_${kind}`] = report(page);
    let clickError = null;
    try { page.$el("#introNever").click(); } catch (error) { clickError = String(error); }
    await flush();
    out[`storage_${kind}_never`] = { ...report(page), clickError };
  }
  {
    const page = boot({ session: kind });
    await flush();
    out[`session_${kind}`] = report(page);
    let closeError = null;
    try { page.$el("#introClose").click(); } catch (error) { closeError = String(error); }
    await flush();
    out[`session_${kind}_closed`] = { ...report(page), closeError };
  }
}

// 5. Every way out of the popup sets the session flag.
const routes = {
  closeButton: (p) => p.$el("#introClose").click(),
  escape: (p) => { p.$el("#intro").dispatch("cancel"); p.$el("#intro").close(); },
  backdrop: (p) => p.$el("#intro").dispatch("click"),
  simulate: (p) => p.$el("#introSimulate").click(),
  tour: (p) => p.$el("#introTour").click(),
  popstate: (p) => p.winL.dispatch("popstate"),
  never: (p) => p.$el("#introNever").click(),
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
for (const [name, opts] of Object.entries({ keysPopupOpen: {}, keysNoPopup: CLOSED })) {
  const page = boot(opts);
  await flush();
  const box = page.$el("#advancedBox");
  box.open = true;
  page.world.openBoxes.push(box);
  page.docL.dispatch("keydown", { key: "Escape", code: "Escape", target: page.$el("body") });
  out[name] = { boxOpen: box.open };
}

// ------------------------------------------------------------ the tour

// Which elements carry each step's data-tour key, as in index.html.
const TOUR_TARGETS = {
  mode: ["#modeToggle"], game: ["gameLabel"], size: ["#playersLabel", "decksLabel", "#cardsHint"],
  options: ["#advancedBox"], run: ["#simulateBtn"], presets: [".preset-cards", "#presetRow"],
  playback: ["#playback .controls"], chart: ["#chartSection"], help: ["#aboutBtn"],
};
// What has a box on each screen. The empty state shows the preset cards; over
// results the preset row shows instead.
const SCREENS = {
  empty: ["#presetRow", "#playback .controls", "#chartSection"],
  game: [".preset-cards"],
  condensed: [".preset-cards", "#playback .controls"],
  blackjackBatch: [".preset-cards", "#cardsHint", "#playback .controls", "#chartSection"],
};
function screen(name, extra = {}) {
  const hidden = new Set(SCREENS[name]);
  const boxes = {};
  let y = 20;
  for (const sels of Object.values(TOUR_TARGETS)) {
    for (const sel of sels) {
      if (!hidden.has(sel)) boxes[sel] = { left: 40, top: y, width: 120, height: 30 };
      y += 40;
    }
  }
  return { boxes: { ...boxes, ...extra } };
}
function bootScreen(name, opts = {}) {
  const { boxes } = screen(name);
  const page = boot({ ...CLOSED, boxes, ...opts });
  page.world.tourTargets = TOUR_TARGETS;
  return page;
}
const tourView = (page) => ({
  tour: page.t.tour(),
  open: page.$el("#tour").open,
  title: page.$el("#tourTitle").textContent,
  text: page.$el("#tourText").textContent,
  count: page.$el("#tourCount").textContent,
  next: page.$el("#tourNext").textContent,
  backDisabled: page.$el("#tourBack").disabled,
  rings: Array.isArray(page.$el("#tourRings").children) ? page.$el("#tourRings").children.length : null,
  panel: { left: page.$el("#tourPanel").style.left, top: page.$el("#tourPanel").style.top },
  focus: page.world.focus,
});
const sets = (page) => page.world.storageCalls.filter(([op]) => op !== "get");

out.tourSteps = boot().t.TOUR_STEPS.map((s) => ({ ...s }));

// 6. The Tour link over each screen: walk every step with Next to Done.
out.walks = {};
for (const name of Object.keys(SCREENS)) {
  const page = bootScreen(name);
  await flush();
  const before = sets(page).length;
  page.t.play();
  page.$el("#tourBtn").click();
  const steps = [tourView(page)];
  const paused = !page.t.playing();
  for (let i = 0; i < 12 && page.t.tour(); i++) {
    page.$el("#tourNext").click();
    if (page.t.tour()) steps.push(tourView(page));
  }
  out.walks[name] = {
    steps, paused, after: tourView(page), writes: sets(page).length - before,
    calls: page.world.calls,
  };
}

// Back, End tour and Escape; nothing is written.
{
  const page = bootScreen("empty");
  await flush();
  const before = sets(page).length;
  page.$el("#tourBtn").click();
  page.$el("#tourNext").click();
  page.$el("#tourNext").click();
  const third = tourView(page);
  page.$el("#tourBack").click();
  const back = tourView(page);
  page.$el("#tourEnd").click();
  const ended = tourView(page);
  page.$el("#tourBtn").click();
  const again = tourView(page);
  page.$el("#tour").dispatch("cancel");
  page.$el("#tour").close();
  const escaped = tourView(page);
  out.tourControls = { third, back, ended, again, escaped, writes: sets(page).length - before };
}

// Show me around: the popup closes first, then the tour opens at step 1.
{
  const { boxes } = screen("empty");
  const page = boot({ boxes });
  page.world.tourTargets = TOUR_TARGETS;
  await flush();
  page.$el("#introTour").click();
  const opened = tourView(page);
  const setsAtOpen = sets(page).length;
  page.$el("#tourNext").click();
  page.$el("#tourEnd").click();
  out.showMeAround = {
    opened, after: tourView(page), calls: page.world.calls,
    flag: page.world.store.get("ludicrous-intro") ?? null,
    session: page.world.session.get("ludicrous-intro") ?? null,
    flagSets: report(page).flagSets,
    writesInTour: sets(page).length - setsAtOpen,
  };
}

// The panel's place: below the element when it fits, else above, inside the
// viewport; centred with no ring when the step's elements lose their boxes.
// Re-placed on resize.
{
  const page = bootScreen("empty");
  await flush();
  page.$el("#tourBtn").click();
  const place = {};
  const at = (box) => {
    page.world.boxes["#modeToggle"] = box;
    page.winL.dispatch("resize");
    return { ...tourView(page).panel, rings: tourView(page).rings };
  };
  place.below = at({ left: 900, top: 60, width: 200, height: 34 });
  place.above = at({ left: 300, top: 700, width: 200, height: 40 });
  place.right = at({ left: 1200, top: 60, width: 60, height: 34 });
  delete page.world.boxes["#modeToggle"];
  page.winL.dispatch("resize");
  place.none = { ...tourView(page).panel, rings: tourView(page).rings, title: tourView(page).title };
  page.$el("#tourNext").click();
  place.stepsOn = tourView(page).title;
  out.place = place;
}

// 8. The tour and a run never overlap.
{
  const page = bootScreen("empty");
  await flush();
  page.$el("#simulateBtn").disabled = true;
  page.$el("#tourBtn").click();
  out.claimedTourLink = tourView(page);
}
{
  const { boxes } = screen("empty");
  const page = boot({ boxes });
  page.world.tourTargets = TOUR_TARGETS;
  await flush();
  page.$el("#simulateBtn").disabled = true;
  page.$el("#introTour").click();
  out.claimedShowMeAround = { ...tourView(page), introOpen: page.$el("#intro").open };
}
const clickPreset = (page, name) => page.docL.dispatch("click", {
  target: { closest: () => ({ dataset: { preset: name }, disabled: false }) },
});
{
  // A preset clicked while the grid loads claims the run at once; the tour
  // won't open over it; the preset runs once the grid is in.
  const page = bootScreen("empty", { holdGrid: true });
  await flush();
  clickPreset(page, "war");
  const claimedAtOnce = page.$el("#simulateBtn").disabled === true;
  page.$el("#tourBtn").click();
  const tourDuringWait = tourView(page).open;
  const workersDuringWait = page.world.workers.length;
  page.releaseGrid();
  await flush();
  out.presetWait = { claimedAtOnce, tourDuringWait, workersDuringWait, messages: report(page).messages };
}
{
  // A run started during the preset's grid wait (Replay submits the form):
  // the preset gives way and leaves that run's claim in place.
  const page = bootScreen("empty", { holdGrid: true });
  await flush();
  clickPreset(page, "war");
  page.$el("#players").value = 6;
  page.$el("#decks").value = 3;
  page.$el("#setup").requestSubmit();
  page.releaseGrid();
  await flush();
  out.presetRunDuringWait = {
    messages: report(page).messages,
    stillClaimed: page.$el("#simulateBtn").disabled === true,
  };
}
{
  // The same, but that run also finishes inside the wait and frees the
  // button: the preset still gives way, since a later claim was made.
  const page = bootScreen("empty", { holdGrid: true });
  await flush();
  clickPreset(page, "war");
  page.$el("#players").value = 6;
  page.$el("#decks").value = 3;
  page.$el("#setup").requestSubmit();
  page.$el("#simulateBtn").disabled = false;  // as that run's finally does
  page.releaseGrid();
  await flush();
  out.presetRunDoneDuringWait = { messages: report(page).messages };
}

// 9. Back or Forward with the tour open ends the tour before the run starts.
{
  const page = bootScreen("game");
  await flush();
  page.$el("#tourBtn").click();
  const opened = page.$el("#tour").open;
  page.ctx.location.search = RUN_URL;
  page.winL.dispatch("popstate");
  await flush();
  out.popstateTour = { opened, ...report(page), tourOpen: page.$el("#tour").open, tour: page.t.tour() };
}

// The page ignores keys while the tour is open, as with the popup: Escape
// doesn't reach an open Options popover behind it (nor does Space or an
// arrow reach playback; the same guard returns before either).
{
  const page = bootScreen("empty");
  await flush();
  page.$el("#tourBtn").click();
  const opened = page.$el("#tour").open;
  const box = page.$el("#advancedBox");
  box.open = true;
  page.world.openBoxes.push(box);
  page.docL.dispatch("keydown", { key: "Escape", code: "Escape", target: page.$el("body") });
  out.keysTourOpen = { opened, boxOpen: box.open };
}

// A game that loads while the tour is open (an Import) ends the tour.
if (process.env.LUDICROUS_RECORDING) {
  const page = bootScreen("empty");
  await flush();
  page.$el("#tourBtn").click();
  const opened = page.$el("#tour").open;
  const text = fs.readFileSync(process.env.LUDICROUS_RECORDING, "utf8");
  page.$el("#importFile").dispatch("change", { target: { files: [{ text }], value: "" } });
  out.importDuringTour = {
    opened, tourOpen: page.$el("#tour").open, tour: page.t.tour(),
    error: typeof page.$el("#error").textContent === "string" ? page.$el("#error").textContent : null,
  };
}

process.stdout.write(JSON.stringify(out));
