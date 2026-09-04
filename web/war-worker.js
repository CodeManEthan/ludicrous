/* Ludicrous v2 engine worker.
 *
 * Hosts the Rust War core (core-rs, compiled to wasm) off the main thread.
 * The protocol is deliberately tiny: every message is {id, type, ...} and
 * every reply is {id, ok, result | error}.
 *
 *   prepare {players, decks, seed, maxRounds}
 *       Runs the whole game once, in steps. While it runs, {id, progress:
 *       {rounds, alive}} messages go out every ~100 ms (no ok field, so the
 *       page can tell them from the reply). The reply carries the summary,
 *       the downsampled chart series as typed arrays, the elimination
 *       timeline, standings, and the checkpoint stats. No event log ever
 *       crosses this boundary. maxRounds 0 means no cap.
 *
 *   cancel {target}
 *       Stops the prepare with id `target` at its next step. That prepare
 *       replies {ok: false, error: "canceled"}; the previously prepared game
 *       (if any) stays playable.
 *
 *   round {round}
 *       One round's view as JSON: faces, counts, war, win/drawn, elims, and
 *       cumulative wins. Stepping to round+1 costs one round of simulation;
 *       any other round costs a checkpoint restore plus a short resim.
 *
 * The wasm glue is built with --target no-modules so importScripts() works
 * in a classic worker -- see core-rs/build-wasm.sh.
 */
"use strict";

importScripts("core/ludicrous_wasm.js");

let booting = null;
let prepared = null;
const canceled = new Set();  // prepare ids asked to stop

// Rounds per step. ~25 ms of wasm at 10M rounds/s: fine-grained enough that
// cancel feels instant and progress ticks smoothly, coarse enough that the
// yield between steps is noise.
const STEP_ROUNDS = 250_000;
const PROGRESS_EVERY_MS = 100;

// A macrotask yield. Only this lets a queued "cancel" message reach
// onmessage; awaiting a resolved promise runs microtasks only.
const yieldToEvents = () => new Promise((resolve) => setTimeout(resolve, 0));

function boot() {
  if (!booting) {
    booting = wasm_bindgen({ module_or_path: "core/ludicrous_wasm_bg.wasm" });
  }
  return booting;
}

async function runPrepare(msg) {
  const started = performance.now();
  const job = new wasm_bindgen.WarPrepareJob(
    msg.players, msg.decks, msg.seed, msg.maxRounds || 0, 0,
  );
  let lastProgress = started;
  try {
    for (;;) {
      const done = job.step(STEP_ROUNDS);
      if (canceled.has(msg.id)) throw new Error("canceled");
      if (done) break;
      const now = performance.now();
      if (now - lastProgress >= PROGRESS_EVERY_MS) {
        lastProgress = now;
        self.postMessage({ id: msg.id, progress: { rounds: job.round(), alive: job.alive() } });
      }
      await yieldToEvents();
    }
  } catch (error) {
    job.free();
    throw error;
  }
  // finish() consumes the job (its pointer is zeroed by the glue), so no free.
  const next = job.finish();
  if (prepared) prepared.free();
  prepared = next;
  // Every one of these is a fresh copy out of wasm memory, so handing the
  // backing buffers to the main thread costs nothing and detaches nothing.
  const chartRounds = prepared.chartRounds();
  const chartSeries = prepared.chartSeries();
  const initialCounts = prepared.initialCounts();
  const elimRounds = prepared.elimRounds();
  const elimPlayers = prepared.elimPlayers();
  const standings = prepared.standings();
  return {
    result: {
      summary: JSON.parse(prepared.summaryJson()),
      rounds: prepared.rounds,
      numPlayers: prepared.numPlayers,
      chartRounds,
      chartSeries,
      initialCounts,
      elimRounds,
      elimPlayers,
      standings,
      checkpoints: prepared.checkpointCount,
      checkpointBytes: prepared.checkpointBytes,
      checkpointInterval: prepared.checkpointInterval,
      prepareMs: performance.now() - started,
    },
    transfer: [
      chartRounds.buffer, chartSeries.buffer, initialCounts.buffer,
      elimRounds.buffer, elimPlayers.buffer, standings.buffer,
    ],
  };
}

function runRound(msg) {
  if (!prepared) throw new Error("no prepared game");
  const started = performance.now();
  const json = prepared.roundView(msg.round);
  return { result: { round: msg.round, json, seekMs: performance.now() - started } };
}

self.onmessage = async (event) => {
  const msg = event.data;
  try {
    await boot();
    let reply;
    switch (msg.type) {
      case "ping": reply = { result: { ok: true } }; break;
      case "prepare":
        try { reply = await runPrepare(msg); } finally { canceled.delete(msg.id); }
        break;
      case "cancel": canceled.add(msg.target); reply = { result: { ok: true } }; break;
      case "round": reply = runRound(msg); break;
      default: throw new Error(`unknown message ${msg.type}`);
    }
    self.postMessage({ id: msg.id, ok: true, result: reply.result }, reply.transfer || []);
  } catch (error) {
    self.postMessage({ id: msg.id, ok: false, error: String((error && error.message) || error) });
  }
};
