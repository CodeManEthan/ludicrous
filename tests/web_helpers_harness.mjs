// Loads web/app.js in node with stubbed browser globals (the real
// URLSearchParams) and prints what its pure helpers decide: run URLs and
// their round trip, the banner's elimination summary, the speed labels of a
// short game, and the rounds estimate on the committed grid. Driven by
// tests/test_web_helpers.py.
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
const ctx = vm.createContext({
  window: inert(), document: inert(), localStorage: inert(), navigator: inert(),
  requestAnimationFrame: () => 0, matchMedia: inert(), console, Intl, Math, JSON,
  Number, Object, Array, Map, Set, Symbol, Proxy, Promise, Date, Error, Uint8Array,
  Float32Array, URLSearchParams, location: { search: "", href: "http://x/" },
  history: inert(), performance: inert(),
  setTimeout: () => 0, clearTimeout: () => 0, setInterval: () => 0, clearInterval: () => 0,
  AbortController, fetch: () => new Promise(() => {}), Blob: inert(), Worker: inert(),
});
vm.runInContext(src + `
;globalThis.__t = {
  setGrid: (g) => { roundsGrid = g; },
  setState: (s) => { state = s; layoutPrefs = {}; },
  runQuery, configFromQuery, serverRunConfig, batchRunConfig,
  describeEliminations, speedLabel, estimateRounds, rowEstimate,
};`, ctx, { filename: "app.js" });
const t = ctx.__t;
const plain = (x) => JSON.parse(JSON.stringify(x));
const fromQuery = (query) => plain(t.configFromQuery(new URLSearchParams(query)));
const out = {};

// Every kind of run, with and without a round cap where War has one.
const strategies = ["basic", "never-bust", "hit-below-17"];
const configs = {
  warSingleV2: { game: "war", mode: "single", engine: "v2", players: 1000, decks: 256, maxRounds: 0, names: "random", seed: 10 },
  warSingleV2Capped: { game: "war", mode: "single", engine: "v2", players: 6, decks: 3, maxRounds: 5000, names: "default", seed: 123456789 },
  warSingleServer: { game: "war", mode: "single", engine: "v1", players: 6, decks: 3, maxRounds: 0, names: "random", seed: 42 },
  warSingleServerCapped: { game: "war", mode: "single", engine: "v1", players: 6, decks: 3, maxRounds: 1000000, names: "random", seed: 42 },
  blackjackSingle: { game: "blackjack", mode: "single", players: 200, decks: 6, rounds: 100, strategies, seed: 7 },
  warBatchV2: { game: "war", mode: "batch", engine: "v2", players: 4, decks: 1, games: 1000, maxRounds: 0, seed: 0 },
  warBatchV2Capped: { game: "war", mode: "batch", engine: "v2", players: 100, decks: 20, games: 500, maxRounds: 2000, seed: 314159 },
  warBatchPython: { game: "war", mode: "batch", players: 4, decks: 1, games: 1000, maxRounds: 0, seed: 99 },
  blackjackBatch: { game: "blackjack", mode: "batch", players: 10, decks: 6, rounds: 100, games: 1000, strategies, seed: 524288 },
};
out.roundTrips = Object.fromEntries(Object.entries(configs).map(([name, config]) => {
  const query = t.runQuery(config);
  return [name, { config, query, back: fromQuery(query) }];
}));

// Links written before Blackjack and Batch had URLs (no game, no mode).
out.legacy = {
  noEngineNoCap: fromQuery("players=6&decks=3&seed=1&names=random&run=1"),
  v2NoCap: fromQuery("engine=v2&players=6&decks=3&seed=1&run=1"),
  withCap: fromQuery("players=6&decks=3&seed=1&max_rounds=0&run=1"),
  prefillOnly: fromQuery("players=6&decks=3"),
  deepLink: fromQuery("players=6&decks=3&seed=1&run=1&round=42"),
};
// Links that are not legacy by shape never get the legacy defaults.
out.modern = {
  blackjack: fromQuery("game=blackjack&players=4&decks=6&rounds=100&strategies=basic,hit-below-17&seed=1&run=1"),
  warBatch: fromQuery("mode=batch&players=4&decks=1&games=1000&seed=0&run=1"),
};

// The configs the page builds after a server single run and a batch.
const warPayload = { game: "war", players: 6, decks: 3, names: "random", seed: "", max_rounds: 0 };
const bjPayload = { game: "blackjack", players: 4, decks: 6, names: "random", seed: "", rounds: 100, strategies };
out.serverWar = t.runQuery(t.serverRunConfig(warPayload, { seed: 777 }));
out.serverWarBack = fromQuery(out.serverWar);
out.serverBlackjack = t.runQuery(t.serverRunConfig(bjPayload, { seed: 778 }));
const warBatchPayload = { game: "war", players: 4, decks: 1, games: 1000, seed: "", max_rounds: 0 };
out.batchNative = t.runQuery(t.batchRunConfig(warBatchPayload, { engine: "v2", config: { base_seed: 4242 } }));
out.batchPython = t.runQuery(t.batchRunConfig(warBatchPayload, { engine: "v1", config: { base_seed: 4243 } }));
out.batchBlackjack = t.runQuery(t.batchRunConfig({ ...bjPayload, games: 1000 },
  { game: "blackjack", config: { base_seed: 4244 } }));

// The banner's summary of one round's eliminations.
const run = (from, to) => Array.from({ length: to - from + 1 }, (_, i) => ({ place: from + i, name: `P${from + i}` }));
out.narration = {
  one: t.describeEliminations([{ place: 7, name: "Ada" }]),
  three: t.describeEliminations([{ place: 5, name: "Ada" }, { place: 6, name: "Bo" }, { place: 4, name: "Cy" }]),
  fourContiguous: t.describeEliminations(run(9, 12).reverse()),
  big: t.describeEliminations(run(791, 1000)),
  gapped: t.describeEliminations([4, 9, 2, 15, 30].map((place) => ({ place, name: `P${place}` }))),
};

// Speed labels of a 100-round Blackjack game: the 3 rnd/s floor binds.
t.setState({ rounds: 100, game: "blackjack", mode: "full", summary: { num_players: 4 } });
const base = { 1: "1 rnd/s", 3: "3 rnd/s", 10: "10 rnd/s", d240: "game in ~4 min", d120: "game in ~2 min", d60: "game in ~1 min", d30: "game in ~30 s" };
out.speedLabels = Object.fromEntries(Object.entries(base).map(([v, b]) => [v, t.speedLabel(v, b)]));

// The rounds estimate on the committed grid.
t.setGrid(grid);
out.grid = { players: grid.players, decks: grid.decks, cells: grid.cells, edges: grid.edges };
const est = (p, d) => {
  const e = t.estimateRounds(p, d);
  return e ? { median: e.median, p10: e.p10, p90: e.p90, seconds: e.seconds } : e;
};
out.latticeEstimates = Object.fromEntries(Object.keys(grid.cells).map((key) => {
  const [p, d] = key.split(":").map(Number);
  return [key, est(p, d)];
}));
const row = (p, d) => t.rowEstimate(p, d).map(Math.exp);
out.queries = {};
for (const [p, d, lo, hi] of [[1000, 20], [700, 14, 512, 1000], [200, 4, 128, 256], [100, 2, 64, 128],
  [300, 6, 256, 512], [1000, 24], [1000, 19]]) {
  out.queries[`${p}:${d}`] = {
    estimate: est(p, d) ?? null,
    rows: lo ? { lo: row(lo, d), hi: row(hi, d) } : null,
  };
}
process.stdout.write(JSON.stringify(out));
