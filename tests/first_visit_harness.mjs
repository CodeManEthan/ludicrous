// Loads web/app.js in node with a small fake DOM and prints what the first-
// visit helpers decide: the showcase deck count on the committed rounds
// grid, the cards-per-player hint, the seat-bias caption, the Blackjack
// budget message, and whether a War run with fewer cards than players is
// refused before anything is sent. Driven by tests/test_first_visit.py.
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

// An element remembers what is assigned to it (value, textContent, hidden)
// and is inert otherwise, so the test can fill in the form and read back
// what the page showed.
const element = () => new Proxy({}, {
  get: (t, k) => (k in t ? t[k] : k === Symbol.toPrimitive ? () => "" : inert()),
  set: (t, k, v) => { t[k] = v; return true; },
});
const elements = new Map();
const $el = (sel) => {
  if (!elements.has(sel)) elements.set(sel, element());
  return elements.get(sel);
};
const document = new Proxy({}, {
  get: (_, k) => (k === "querySelector" ? $el : inert()),
});

// Anything that would reach an engine is counted: a request to the server,
// or a worker for the in-browser engine.
const sent = { fetch: [], workers: 0 };
const fetch = (url, init) => { sent.fetch.push(String(url)); return inert(); };
function Worker() { sent.workers += 1; return inert(); }

const ctx = vm.createContext({
  window: inert(), document, localStorage: inert(), navigator: inert(),
  requestAnimationFrame: () => 0, matchMedia: inert(), console, Intl, Math, JSON,
  Number, Object, Array, Map, Set, Symbol, Proxy, Promise, Date, Error, Uint8Array,
  Float32Array, URLSearchParams, location: { search: "?players=6", href: "http://x/" },
  history: inert(), performance: inert(),
  setTimeout: () => 0, clearTimeout: () => 0, setInterval: () => 0, clearInterval: () => 0,
  AbortController, fetch, Blob: inert(), Worker,
});
vm.runInContext(src + `
;globalThis.__t = {
  setGrid: (g) => { roundsGrid = g; },
  showcaseDecks, estimateRounds, cardsHintText, seatBiasCaption, blackjackBudgetProblem,
  presets: PRESETS, budget: BJ_HAND_BUDGET, notEnough: NOT_ENOUGH_CARDS,
  setForm: (g, m) => { gameType = g; mode = m; },
  simulate: () => { simulate({ preventDefault() {} }); },
};`, ctx, { filename: "app.js" });
const t = ctx.__t;
const out = {};

// The showcase deck count, without and with the committed grid.
out.showcaseNoGrid = t.showcaseDecks();
t.setGrid(grid);
out.showcaseDecks = t.showcaseDecks();
out.gridDecks = grid.decks;
out.estimates = Object.fromEntries(grid.decks.map((d) => {
  const est = t.estimateRounds(1000, d);
  return [d, est ? { seconds: est.seconds, median: est.median, p10: est.p10, p90: est.p90 } : null];
}));
out.showcaseSeed = t.presets.war.seed;
out.showcasePlayers = t.presets.war.players;

out.hints = Object.fromEntries([[6, 3], [1000, 20], [1000, 256], [4, 1], [1000, 19], [53, 1], [52, 1]]
  .map(([p, d]) => [`${p}:${d}`, t.cardsHintText(p, d)]));
out.notEnough = t.notEnough;
out.captions = Object.fromEntries([[1000, 20], [1000, 256], [4, 1], [6, 3], [51, 1]]
  .map(([p, d]) => [`${p}:${d}`, t.seatBiasCaption(p, d)]));

out.budget = t.budget;
const cases = [[200, 100, 1000], [200, 100, 500], [200, 100, 501], [10, 100, 10000], [41, 250, 1000],
  [67, 150, 1000], [1, 10000, 1001], [200, 10000, 10000], [7, 333, 4291]];
out.budgetMessages = cases.map(([s, r, g]) => ({ seats: s, rounds: r, games: g, msg: t.blackjackBudgetProblem(s, r, g) }));
const sd = t.presets.showdown;
out.showdown = { ...sd, strategies: [...sd.strategies], msg: t.blackjackBudgetProblem(sd.players, sd.rounds, sd.games) };

// A run that can't deal every player a card is refused before anything is
// sent; one card each is allowed (and does send).
const attempt = (game, runMode, fields) => {
  t.setForm(game, runMode);
  for (const [sel, value] of Object.entries(fields)) $el(sel).value = String(value);
  $el("#simulateBtn").disabled = false;
  $el("#error").textContent = "";
  const before = { fetch: sent.fetch.length, workers: sent.workers };
  t.simulate();
  return {
    error: $el("#error").textContent,
    sent: sent.fetch.slice(before.fetch),
    workers: sent.workers - before.workers,
  };
};
out.runs = {
  warSingleShort: attempt("war", "single", { "#players": 521, "#decks": 10 }),
  warSingleExact: attempt("war", "single", { "#players": 520, "#decks": 10 }),
  warBatchShort: attempt("war", "batch", { "#players": 1000, "#decks": 19, "#games": 10 }),
  bjBatchOver: attempt("blackjack", "batch", { "#players": 200, "#decks": 6, "#rounds": 100, "#games": 1000 }),
  bjBatchFits: attempt("blackjack", "batch", { "#players": 200, "#decks": 6, "#rounds": 100, "#games": 500 }),
};
process.stdout.write(JSON.stringify(out));
