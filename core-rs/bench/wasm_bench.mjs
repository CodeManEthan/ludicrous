// Node benchmark for the wasm build.
//
//   ./build-wasm.sh
//   node bench/wasm_bench.mjs
//
// Prints the same `key<TAB>value` lines the native harness does, so the two
// can be diffed straight into a table. Also re-runs the native `dump` grid
// through wasm and compares, because a benchmark that measures the wrong
// answer fast is worth nothing.

import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const require = createRequire(import.meta.url);
const wasm = require(join(root, "pkg", "ludicrous_wasm.js"));

const now = () => Number(process.hrtime.bigint()) / 1e6; // ms

function timed(minMs, fn) {
  // Warm up so the JIT and the wasm module are past their first call.
  fn();
  const t0 = now();
  let iters = 0;
  let acc = 0;
  do {
    acc += fn();
    iters++;
  } while (now() - t0 < minMs);
  return { ms: now() - t0, iters, acc };
}

// --------------------------------------------------- correctness first

function crossCheckAgainstNative() {
  const bin = join(root, "target", "release", "lud-bench");
  if (!existsSync(bin)) {
    console.log("wasm.parity_vs_native\tSKIPPED\t(build lud-bench first)");
    return;
  }
  const want = execFileSync(bin, ["dump"], { encoding: "utf8" }).trim().split("\n");
  let checked = 0;
  for (const line of want) {
    const [p, d, seed, rounds, wars, deepest, pot, winner, completed, standings] =
      line.split(" ");
    const s = JSON.parse(wasm.simulate(+p, +d, 0, +seed));
    const got = [
      p, d, seed,
      String(s.rounds), String(s.wars), String(s.deepest_war),
      String(s.biggest_pot), String(s.winner ?? 0), String(s.completed),
      s.standings.join(","),
    ].join(" ");
    if (got !== line) {
      console.error("MISMATCH\n  native: " + line + "\n  wasm:   " + got);
      process.exit(1);
    }
    checked++;
  }
  console.log(`wasm.parity_vs_native\tOK\t${checked} games identical`);
}

// ------------------------------------------------------------ benchmarks

function benchSingle() {
  console.log("## wasm single-thread, events off");
  for (const [p, d, gamesPerCall] of [[6, 3, 200], [26, 13, 20], [100, 50, 1]]) {
    let seed = 1;
    const r = timed(2000, () => {
      const rounds = wasm.bench_rounds(p, d, seed, gamesPerCall);
      seed += gamesPerCall;
      return rounds;
    });
    const games = r.iters * gamesPerCall;
    console.log(
      `wasm.rounds_per_sec.${p}p${d}d\t${(r.acc / (r.ms / 1000)).toFixed(0)}\t` +
        `games=${games} rounds=${r.acc} secs=${(r.ms / 1000).toFixed(3)} ` +
        `mean_rounds=${(r.acc / games).toFixed(0)}`
    );
    console.log(
      `wasm.games_per_sec.${p}p${d}d\t${(games / (r.ms / 1000)).toFixed(1)}`
    );
  }
}

function benchOneBigGame() {
  console.log("## wasm, one full 100p/50d game");
  const times = [];
  let rounds = 0;
  for (let seed = 1; seed <= 20; seed++) {
    const t0 = now();
    const g = new wasm.WarSession(100, 50, 0, seed);
    g.run();
    times.push(now() - t0);
    rounds += g.round;
    g.free();
  }
  const mean = times.reduce((a, b) => a + b, 0) / times.length;
  console.log(
    `wasm.one_game_100p50d_ms.mean\t${mean.toFixed(2)}\t` +
      `min=${Math.min(...times).toFixed(2)} max=${Math.max(...times).toFixed(2)} ` +
      `mean_rounds=${(rounds / times.length).toFixed(0)}`
  );
}

function benchEvents() {
  console.log("## wasm with events (JSON out across the boundary)");
  // 100p/50d games run ~700k rounds and emit >100 events each, which is
  // gigabytes of JSON -- past what a JS string can even hold. Cap the big
  // config at a fixed segment so the two numbers are comparable.
  for (const [p, d, cap] of [[6, 3, 0], [100, 50, 2000]]) {
    let seed = 1;
    let rounds = 0;
    let bytes = 0;
    const t0 = now();
    let games = 0;
    do {
      const ndjson = wasm.simulate_with_events(p, d, cap, seed);
      bytes += ndjson.length;
      // Round count comes off the last event: GameOver.total_rounds for a
      // finished game, or the last RoundEnded's round for a capped one.
      const last = JSON.parse(
        ndjson.slice(ndjson.lastIndexOf("\n", ndjson.length - 2) + 1).trim()
      );
      rounds += last.total_rounds ?? last.round;
      seed++;
      games++;
    } while (now() - t0 < 2000);
    const secs = (now() - t0) / 1000;
    console.log(
      `wasm.rounds_per_sec.${p}p${d}d.events_json\t${(rounds / secs).toFixed(0)}\t` +
        `json_bytes_per_round=${(bytes / rounds).toFixed(0)} games=${games}` +
        (cap ? ` (capped at ${cap} rounds/game)` : "")
    );
  }
}

function benchCheckpoint() {
  console.log("## wasm checkpoint");
  for (const [p, d] of [[6, 3], [26, 13], [100, 50]]) {
    const g = new wasm.WarSession(p, d, 0, 7);
    g.advance(500);
    const snap = g.save();
    console.log(`wasm.checkpoint.bytes.${p}p${d}d\t${snap.length}`);

    let r = timed(500, () => g.save().length);
    const saveUs = (r.ms * 1000) / r.iters;
    r = timed(500, () => {
      const g2 = wasm.WarSession.restore(snap);
      const n = g2.round;
      g2.free();
      return n;
    });
    const restoreUs = (r.ms * 1000) / r.iters;
    console.log(
      `wasm.checkpoint.save_us.${p}p${d}d\t${saveUs.toFixed(3)}\t` +
        `restore_us=${restoreUs.toFixed(3)}`
    );
    g.free();
  }
}

function benchSeek() {
  console.log("## wasm seek: restore checkpoint + resim K rounds");
  // 6p/3d games average ~2,100 rounds, so K=5000 there is "run to the end",
  // not 5,000 rounds. The wider tables are the real worst case.
  for (const [p, d] of [[6, 3], [26, 13], [100, 50]]) {
    const g = new wasm.WarSession(p, d, 0, 11);
    g.advance(50);
    const snap = g.save();
    g.free();
    for (const k of [1000, 5000]) {
      let played = 0;
      const r = timed(1000, () => {
        const g2 = wasm.WarSession.restore(snap);
        const n = g2.advance(k);
        played = n;
        g2.free();
        return n;
      });
      console.log(
        `wasm.seek_ms.${p}p${d}d.k${k}\t${(r.ms / r.iters).toFixed(4)}\t` +
          `rounds_actually_played=${played} iters=${r.iters}`
      );
    }
  }
}

console.log(`node\t${process.version}`);
crossCheckAgainstNative();
benchSingle();
benchOneBigGame();
benchEvents();
benchCheckpoint();
benchSeek();
