// Loads web/app.js in node with stubbed browser globals and prints the
// playback plans for synthetic games. Driven by tests/test_playback_plan.py.
import fs from "node:fs";
import vm from "node:vm";

const src = fs.readFileSync(process.env.LUDICROUS_APP_JS ?? new URL("../web/app.js", import.meta.url), "utf8");
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
  Float32Array, URLSearchParams: inert(), location: inert(), performance: inert(),
  setTimeout: () => 0, clearTimeout: () => 0, fetch: inert(), Blob: inert(), Worker: inert(),
});
vm.runInContext(src + `
;globalThis.__t = {
  plan: (game, budget, phased) => {
    state = game; layoutPrefs = { slowOpening: phased };
    const p = phased ? buildPlaybackPlan(budget) : buildStraightPlan(budget);
    return p.spans.map((s) => ({ ...s, secs: (s.to - s.from) / s.speed }));
  },
};`, ctx, { filename: "app.js" });

// A game: `players` players, eliminations at the given rounds, `rounds` total.
const game = (players, elimRounds, rounds) => ({
  rounds, game: "war", mode: "full", summary: { num_players: players },
  elimSorted: elimRounds.map((round, i) => ({ round, name: "p" + i })),
});
const spread = (n, lo, hi) => Array.from({ length: n }, (_, i) => Math.round(lo + ((hi - lo) * i) / Math.max(n - 1, 1)));

const games = {
  // The 2026-09-08 report: 100 players, 1000 decks, 270M rounds. The field
  // was still crowded at round 45,431.
  big_crowded: game(100, [...spread(75, 100, 45431), ...spread(23, 60000, 41000000), 270082175], 270082175),
  // 1000 players, 1000 decks: a 44-round opening in front of 608M rounds.
  huge_short_opening: game(1000, [...spread(975, 1, 44), ...spread(23, 100, 400000000), 608612340], 608612340),
  small: game(7, [3, 4, 18, 35, 61, 67], 67),
  duel_only: game(2, [500], 500),
};
const out = {};
for (const [name, g] of Object.entries(games)) {
  for (const budget of [30, 60, 120, 240]) {
    out[`${name}:d${budget}:straight`] = ctx.__t.plan(g, budget, false);
    out[`${name}:d${budget}:phased`] = ctx.__t.plan(g, budget, true);
  }
}
process.stdout.write(JSON.stringify(out));
