/* Ludicrous v2 engine worker.
 *
 * Hosts the Rust War core (core-rs, compiled to wasm) off the main thread.
 * The protocol is deliberately tiny: every message is {id, type, ...} and
 * every reply is {id, ok, result | error}.
 *
 *   prepare {players, decks, seed, maxRounds}
 *       Runs the whole game once. Replies with the summary, the downsampled
 *       chart series as typed arrays, the elimination timeline, standings,
 *       and the checkpoint stats. No event log ever crosses this boundary.
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

function boot() {
  if (!booting) {
    booting = wasm_bindgen({ module_or_path: "core/ludicrous_wasm_bg.wasm" });
  }
  return booting;
}

function runPrepare(msg) {
  const started = performance.now();
  if (prepared) {
    prepared.free();
    prepared = null;
  }
  prepared = wasm_bindgen.prepare(
    msg.players, msg.decks, msg.seed, msg.maxRounds, 0,
  );
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
      case "prepare": reply = runPrepare(msg); break;
      case "round": reply = runRound(msg); break;
      default: throw new Error(`unknown message ${msg.type}`);
    }
    self.postMessage({ id: msg.id, ok: true, result: reply.result }, reply.transfer || []);
  } catch (error) {
    self.postMessage({ id: msg.id, ok: false, error: String((error && error.message) || error) });
  }
};
