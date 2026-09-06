/* Ludicrous — playback UI over engine recordings. No dependencies. */
"use strict";

const $ = (sel) => document.querySelector(sel);
const fmt = new Intl.NumberFormat("en-US");
// Ten hues that hold apart on the dark panel: the five validated in the
// dataviz pass, then five more. Highlight index k gets hue k % 10; from k = 10
// the same hue comes back paler and thinner (the "chasers" tier).
const PALETTE = [
  "#3987e5", "#d95926", "#199e70", "#c98500", "#d55181",
  "#9b7be8", "#35b6d9", "#8fb52a", "#c25fd0", "#b58a5a",
];
const HIGHLIGHT_MAX = 20;
const FIELD = "rgba(137, 135, 129, 0.28)";
const CARD_BACK = "/cards/card_back_red.png";
const RANK_NAMES = { 11: "jack", 12: "queen", 13: "king", 14: "ace" };
const CHART_POINTS = 1200;
const V2_WORKER_URL = "war-worker.js";

const STRATEGY_META = [
  ["basic", "Basic strategy"],
  ["never-bust", "Never bust"],
  ["hit-below-15", "Hit below 15"],
  ["hit-below-16", "Hit below 16"],
  ["hit-below-17", "Hit below 17"],
];
const STRATEGY_LABELS = Object.fromEntries(STRATEGY_META);

let state = null;      // prepared recording (see prepare())
let pendingRound = null; // round to jump to after load (from ?round= URL param)
let mode = "single";   // "single" | "batch"
let gameType = "war";  // "war" | "blackjack"
let batchData = null;  // last /api/batch response

const SINGLE_SECTIONS = ["#stats", "#condensedNote", "#unfinishedNote", "#playback", "#table", "#chartSection", "#elimSection"];
const BATCH_SECTIONS = ["#batchStats", "#evSection", "#histSection", "#seatSection", "#outlierSection"];
let current = -1;      // round currently rendered
let pos = 0;           // playhead position (fractional rounds)
let playing = false;
let lastTs = 0;
let winsCache = { round: -1, wins: {} };
let chartScale = null; // set by drawChart()
let hoverX = null;

// v2 (client-side wasm) engine. See war-worker.js for the protocol.
let v2Worker = null;
let v2Seq = 0;
const v2Pending = new Map();
let v2RoundInFlight = false;
let v2RoundQueued = null;
let urlEngine = null;  // engine the URL asked for, consumed by the first run
let loadGen = 0;       // bumped per loaded game, so late replies can't paint

// ---------------------------------------------------------------- helpers

function cardUrl([rank, suit]) {
  const name = RANK_NAMES[rank] || String(rank);
  return `/cards/${name}_of_${suit.toLowerCase()}.png`;
}

function showError(message) {
  const el = $("#error");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.hidden = true; }, 8000);
}

// Any text is a valid seed: integers (incl. hex) pass through, anything else
// — "lucky", "my-seed", "3.5" — is hashed (FNV-1a) to a deterministic 32-bit
// integer. Returns null for empty input (= pick a random seed).
function parseSeed(text) {
  const t = text.trim();
  if (t === "") return null;
  if (/^[+-]?(\d+|0[xX][0-9a-fA-F]+)$/.test(t)) return Number(t);
  let h = 2166136261;
  for (let i = 0; i < t.length; i++) {
    h ^= t.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function fmtMs(ms) {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

// ------------------------------------------------------ layout preferences
//
// Per-viewer conveniences: cards/chart order, collapsed cards, how long
// eliminated players stay in the grid. localStorage may be unavailable
// (private windows, blocked site data) — every touch is guarded.

function loadLayoutPrefs() {
  try { return JSON.parse(localStorage.getItem("ludicrous-layout")) || {}; }
  catch { return {}; }
}

let layoutPrefs = loadLayoutPrefs();

function saveLayoutPrefs() {
  try { localStorage.setItem("ludicrous-layout", JSON.stringify(layoutPrefs)); }
  catch { /* per-viewer convenience only */ }
}

// Phone-width viewports get the compact layout (see the media query in
// style.css) and start a crowded table folded. Same breakpoint as the CSS.
const narrowScreen = window.matchMedia("(max-width: 640px)");
const PHONE_FOLD_PLAYERS = 24;

function tableCollapsed() {
  if (layoutPrefs.tableCollapsed != null) return !!layoutPrefs.tableCollapsed;
  return narrowScreen.matches && !!state && state.summary.num_players > PHONE_FOLD_PLAYERS;
}

function applyLayoutPrefs() {
  // Chart above the cards unless the viewer turned it off: on a phone a big
  // table is a wall of tiles, and the chart is what you scroll to see.
  const chartFirst = layoutPrefs.chartFirst !== false;
  $("#results").classList.toggle("chart-first", chartFirst);
  $("#chartTopChk").checked = chartFirst;
  $("#slowOpening").checked = layoutPrefs.slowOpening === true;
  $("#highlightN").value = String(highlightPref());
  const collapsed = tableCollapsed();
  $("#table").classList.toggle("collapsed", collapsed);
  $("#collapseBtn").textContent = collapsed ? "+" : "−";
  $("#collapseBtn").title = collapsed ? "Expand the cards" : "Collapse the cards";
  const elim = layoutPrefs.elimDisplay || "strip";
  if ($("#elimDisplay").value !== elim) $("#elimDisplay").value = elim;
}

function elimMode() {
  return layoutPrefs.elimDisplay || "strip";
}

// How many rounds an eliminated player's tile stays in the grid.
// null = forever (dimmed); 0 = gone at once ("hide" and "strip" — strip
// re-homes them below the grid); linger scales with game length so the
// choice means the same thing at 100 rounds and at 300,000 — and scrubbing
// backward always brings players back (it's all a function of the current
// round).
function elimHideAfter() {
  const mode = elimMode();
  if (mode === "hide" || mode === "strip") return 0;
  if (mode === "linger") return Math.max(25, Math.round(state.rounds * 0.02));
  return null;
}

// ------------------------------------------------- loading overlay (server)
//
// v2 games build in ~100 ms and never show this. v1 games, and especially
// batches, run on the server and can take real time — this is the "the app
// is working on it" screen: what's running, a live elapsed clock, a cancel.
// It only appears if the wait exceeds 250 ms, so fast runs never flash.

let loadingDelay = null;
let loadingClock = null;
let loadingAbort = null;

function showLoading(title, note) {
  $("#loadingTitle").textContent = title;
  $("#loadingNote").textContent = note || "";
  $("#loadingNote").hidden = !note;
  $("#loadingElapsed").textContent = " ";
  $("#loadingBarWrap").hidden = true;
  $("#loadingCount").hidden = true;
  $("#loadingBar").style.width = "0%";
  const startedAt = performance.now();
  clearTimeout(loadingDelay);
  loadingDelay = setTimeout(() => {
    $("#loading").hidden = false;
    loadingClock = setInterval(() => {
      $("#loadingElapsed").textContent =
        `${((performance.now() - startedAt) / 1000).toFixed(1)} s`;
    }, 100);
  }, 250);
}

function hideLoading() {
  clearTimeout(loadingDelay);
  clearInterval(loadingClock);
  loadingDelay = null;
  loadingClock = null;
  $("#loading").hidden = true;
}

function updateLoadingCount(text) {
  $("#loadingCount").hidden = false;
  $("#loadingCount").textContent = text;
}

function updateLoadingProgress(done, total, unit, label) {
  $("#loadingBarWrap").hidden = false;
  $("#loadingCount").hidden = false;
  $("#loadingBar").style.width = `${(100 * done) / Math.max(total, 1)}%`;
  $("#loadingCount").textContent = label !== undefined
    ? `${label} ${unit}`
    : `${fmt.format(done)} / ${fmt.format(total)} ${unit}`;
}

// Read an /api/batch/stream response: NDJSON progress lines, then exactly
// one {result} (or {error}) line. The connection closing ends the stream.
async function readBatchStream(response, onProgress) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let payload = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });
    let nl;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (!line) continue;
      const msg = JSON.parse(line);
      if (msg.error) throw new Error(msg.error);
      if (msg.progress) onProgress(msg.progress.done, msg.progress.total);
      if (msg.result) payload = msg.result;
    }
    if (done) break;
  }
  if (!payload) throw new Error("the batch stream ended without a result");
  return payload;
}

// ------------------------------------------------------- v2 engine (wasm)
//
// A v2 game never posts to /api/simulate. It is (config, seed) plus a
// checkpoint set living in a worker: prepare() runs the whole game once,
// then every rendered round is reconstructed on demand. There is no event
// log and therefore no size cliff — full playback at any scale.

function v2Available() {
  return typeof Worker === "function" && typeof WebAssembly === "object";
}

function v2Start() {
  if (v2Worker) return v2Worker;
  const worker = new Worker(V2_WORKER_URL);
  worker.onmessage = (event) => {
    const { id, ok, result, error, progress } = event.data;
    const entry = v2Pending.get(id);
    if (!entry) return;
    if (progress) {  // interim: the request is still running
      if (entry.onProgress) entry.onProgress(progress);
      return;
    }
    v2Pending.delete(id);
    if (ok) entry.resolve(result);
    else entry.reject(new Error(error));
  };
  worker.onerror = (event) => {
    const error = new Error(event.message || "engine worker failed to start");
    for (const entry of v2Pending.values()) entry.reject(error);
    v2Pending.clear();
    worker.terminate();
    if (v2Worker === worker) v2Worker = null;
  };
  v2Worker = worker;
  return worker;
}

function v2Send(message, onProgress) {
  const worker = v2Start();
  const id = ++v2Seq;
  const promise = new Promise((resolve, reject) => {
    v2Pending.set(id, { resolve, reject, onProgress });
    worker.postMessage({ ...message, id });
  });
  promise.requestId = id;
  return promise;
}

// Errors that must NOT fall back to the server: the user canceled, or the
// engine rejected the config (the server would reject it the same way, or
// worse, grind through it in Python).
function finalError(message) {
  const error = new Error(message);
  error.v2Final = true;
  return error;
}

// Which engine a click on Simulate should use. The URL wins for the run it
// came with (so an old share link — no engine param — still replays through
// the server, byte for byte as before); everything else prefers v2.
function pickEngine() {
  const forced = urlEngine;
  urlEngine = null;
  if (gameType !== "war" || mode !== "single") return "v1";
  if (!v2Available()) return "v1";
  return forced === null || forced === "v2" ? "v2" : "v1";
}

// Deterministic shuffle for client-side names: same seed, same table, so a
// share URL reproduces the names as well as the cards.
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function makeNames(players, nameMode, seed) {
  const names = {};
  if (nameMode !== "random" || typeof NAME_POOL === "undefined") {
    for (let i = 1; i <= players; i++) names[i] = `Player ${i}`;
    return names;
  }
  const pool = NAME_POOL.slice();
  const rand = mulberry32(seed);
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  for (let i = 0; i < players; i++) {
    names[i + 1] = i < pool.length
      ? pool[i]
      : `${pool[i % pool.length]} ${Math.floor(i / pool.length) + 1}`;
  }
  return names;
}

function buildV2State(result, names) {
  const summary = result.summary;
  const players = result.numPlayers;
  const xs = Array.from(result.chartRounds);
  const samples = xs.length;
  const series = {};
  const initialCounts = {};
  for (let p = 0; p < players; p++) {
    const row = new Array(samples);
    for (let i = 0; i < samples; i++) {
      const value = result.chartSeries[p * samples + i];
      row[i] = value < 0 ? null : value;  // -1 = already eliminated
    }
    series[p + 1] = row;
    initialCounts[p + 1] = result.initialCounts[p];
  }
  const elimRound = {};
  const elimSorted = [];
  for (let i = 0; i < result.elimRounds.length; i++) {
    const player = result.elimPlayers[i];
    elimRound[player] = result.elimRounds[i];
    elimSorted.push({ player, round: result.elimRounds[i] });
  }
  const stats = {
    wars: summary.wars,
    deepest_war: summary.deepest_war,
    biggest_pot: summary.biggest_pot,
    deepest_war_round: summary.deepest_war_round || 0,
    biggest_pot_round: summary.biggest_pot_round || 0,
    total_cards: summary.num_decks * 52,
  };
  return {
    game: "war",
    mode: "full",
    engine: "v2",
    summary,
    rounds: summary.rounds,
    standings: Array.from(result.standings),
    names,
    stats,
    chartData: { rounds: xs, series },
    initialCounts,
    elimRound,
    elimSorted,
    totalCards: stats.total_cards,
    chartRange: { yMin: 0, yMax: stats.total_cards },
  };
}

// The Max rounds cap is opt-in; 0 means no cap everywhere (URL, API, engine).
function roundCap() {
  if (!$("#capRounds").checked) return 0;
  return Math.max(0, Math.floor(Number($("#maxRounds").value) || 0));
}

function setRoundCap(value) {
  const n = Math.max(0, Math.floor(Number(value) || 0));
  $("#capRounds").checked = n > 0;
  if (n > 0) $("#maxRounds").value = n;
  $("#maxRounds").disabled = n === 0;
}

// ----------------------------------------------------- rounds calculator
//
// How long will this game be? rounds-grid.json holds, per (players, decks)
// cell, the median / p10 / p90 round count over 50 seeds and the native
// rounds/s, measured offline (core-rs/crates/ludicrous-bench/examples/grid.rs).
// Rounds grow ~quadratically with the shoe and barely with players, so a
// bilinear interpolation in log space between the four surrounding cells is
// plenty. The wasm build runs at about a third of native speed.

let roundsGrid = null;

fetch("/rounds-grid.json")
  .then((r) => (r.ok ? r.json() : null))
  .then((grid) => { roundsGrid = grid; updateEstimateLine(); })
  .catch(() => {});

function estimateRounds(players, decks) {
  if (decks * 52 < players) return null;
  if (!roundsGrid) return undefined;
  const { players: ps, decks: ds, cells } = roundsGrid;
  const bracket = (axis, v) => {
    const c = Math.min(Math.max(v, axis[0]), axis[axis.length - 1]);
    let i = 0;
    while (i < axis.length - 2 && axis[i + 1] < c) i++;
    const lo = axis[i], hi = axis[i + 1];
    const t = hi === lo ? 0 : (Math.log(c) - Math.log(lo)) / (Math.log(hi) - Math.log(lo));
    return [lo, hi, t];
  };
  const [p0, p1, tp] = bracket(ps, players);
  const [d0, d1, td] = bracket(ds, decks);
  const corners = [[p0, d0], [p0, d1], [p1, d0], [p1, d1]].map(([p, d]) => cells[`${p}:${d}`]);
  // A corner can be missing where the shoe is too small for the players;
  // fall back to whatever corners exist (the estimate is coarse anyway).
  const present = corners.filter(Boolean);
  if (!present.length) return null;
  const pick = (k) => {
    const v = corners.map((c) => (c ? Math.log(c[k]) : null));
    const fill = present.reduce((a, c) => a + Math.log(c[k]), 0) / present.length;
    const w = v.map((x) => (x === null ? fill : x));
    const lo = w[0] * (1 - td) + w[1] * td;
    const hi = w[2] * (1 - td) + w[3] * td;
    return Math.exp(lo * (1 - tp) + hi * tp);
  };
  const median = pick(0), p10 = pick(1), p90 = pick(2), rps = pick(3);
  const wasmRps = rps * (roundsGrid.wasm_speed_factor || 0.33);
  return { median, p10, p90, seconds: median / wasmRps, wasmRps };
}

function describeEstimate(est, cap) {
  if (est === null) return "Not enough cards for that many players.";
  if (est === undefined) return "";
  let text = `Typical game: ~${fmtNum(est.median)} rounds (${fmtNum(est.p10)} to ${fmtNum(est.p90)}) · ` +
    `about ${fmtDuration(Math.max(1, est.seconds)).replace("~", "")} to simulate`;
  if (cap && cap < est.p90) {
    text += ` · a cap of ${fmtNum(cap)} rounds will stop ${cap < est.median ? "most" : "some"} games early`;
  }
  return text;
}

function updateEstimateLine() {
  const line = $("#estimateLine");
  if (gameType !== "war") { line.hidden = true; return; }
  const est = estimateRounds(Number($("#players").value), Number($("#decks").value));
  const text = describeEstimate(est, roundCap());
  line.textContent = text;
  line.hidden = !text;
  line.classList.toggle("warn", est === null);
}

async function simulateV2() {
  const players = Number($("#players").value);
  const decks = Number($("#decks").value);
  const maxRounds = roundCap();
  const parsed = parseSeed($("#seed").value);
  const seed = parsed === null ? Math.floor(Math.random() * 1e9) : parsed;
  const nameMode = $("#nameMode").value;

  pause();
  const estimate = estimateRounds(players, decks);
  if (estimate === null) throw finalError("Not enough cards for that many players — add decks or remove players.");
  loadingAbort = new AbortController();
  showLoading(
    `Simulating War — ${fmt.format(players)} players, ${fmt.format(decks)} decks`,
    describeEstimate(estimate, maxRounds));
  const startedAt = performance.now();
  // Progress against the typical long game (p90). Clamped short of full so
  // the bar never sits at 100% while the engine is still going.
  // Without an estimate (grid not loaded) there is no bar, only the count.
  const p90 = estimate ? estimate.p90 : 0;
  const target = maxRounds && p90 ? Math.min(maxRounds, p90) : maxRounds || p90;
  const request = v2Send({ type: "prepare", players, decks, seed, maxRounds }, (p) => {
    const secs = (performance.now() - startedAt) / 1000;
    const unit = `rounds · ${fmt.format(p.alive)} still in · ${secs.toFixed(1)} s`;
    if (target) updateLoadingProgress(Math.min(p.rounds, target * 0.95), target, unit, fmtNum(p.rounds));
    else updateLoadingCount(`${fmtNum(p.rounds)} ${unit}`);
  });
  const onAbort = () => v2Send({ type: "cancel", target: request.requestId });
  loadingAbort.signal.addEventListener("abort", onAbort);
  let result;
  try {
    result = await request;
  } catch (error) {
    if (error.message === "canceled") throw finalError("Simulation canceled.");
    throw finalError(error.message);
  } finally {
    loadingAbort.signal.removeEventListener("abort", onAbort);
    hideLoading();
  }
  console.info(
    `[ludicrous] v2 prepare: ${fmt.format(result.rounds)} rounds in ` +
    `${result.prepareMs.toFixed(1)} ms · ${fmt.format(result.checkpoints)} checkpoints ` +
    `every ${fmt.format(result.checkpointInterval)} rounds ` +
    `(${(result.checkpointBytes / 1048576).toFixed(2)} MB)`);
  state = buildV2State(result, makeNames(players, nameMode, seed));
  state.prepareMs = result.prepareMs;
  activate();
  const url = new URL(location.href);
  url.search = new URLSearchParams({
    engine: "v2", players, decks, max_rounds: maxRounds,
    names: nameMode, seed, run: "1",
  }).toString();
  // Each run is a history entry, so Back walks through your games instead
  // of dumping you out of the app. A run replayed BY Back (popstate) only
  // corrects the URL in place — pushing there would trap the button.
  if (url.search !== location.search) {
    if (historyNav) history.replaceState(null, "", url);
    else history.pushState(null, "", url);
  }
  historyNav = false;
}

// One round, reconstructed in the worker. Only one request is ever in
// flight: a scrub that outruns the engine collapses to its latest position
// instead of queueing a frame per mousemove.
function requestV2Round(round) {
  if (round === 0) {
    paintWarRound(0, null, {});
    return;
  }
  if (v2RoundInFlight) {
    v2RoundQueued = round;
    return;
  }
  v2RoundInFlight = true;
  const gen = loadGen;
  v2Send({ type: "round", round })
    .then(({ round: got, json }) => {
      v2RoundInFlight = false;
      if (gen !== loadGen) return;
      const view = json === "null" ? null : JSON.parse(json);
      if (got === current) paintWarRound(got, view, view ? view.wins : {});
      const queued = v2RoundQueued;
      v2RoundQueued = null;
      if (queued !== null && queued !== got) requestV2Round(queued);
    })
    .catch((error) => {
      v2RoundInFlight = false;
      v2RoundQueued = null;
      pause();
      showError(`Playback failed: ${error.message}`);
    });
}

// ------------------------------------------------------------ data loading

function setMode(next) {
  mode = next;
  for (const button of $("#modeToggle").children) {
    button.classList.toggle("active", button.dataset.mode === next);
  }
  updateForm();
  showResults();
}

function setGameType(next) {
  if (next === gameType) return;
  gameType = next;
  // Old results describe the other game — showing a Blackjack form above a
  // finished War game reads as a bug, so clear them.
  pause();
  state = null;
  batchData = null;
  $("#gameSel").value = next;
  if (next === "blackjack") {
    $("#decks").value = 6;
    $("#players").min = 1;
    $("#players").value = Math.min(Number($("#players").value), 8) || 4;
  } else {
    $("#decks").value = 3;
    $("#players").min = 2;
    $("#players").value = Math.max(Number($("#players").value), 2) || 6;
  }
  updateForm();
  showResults();
}

function updateForm() {
  const batch = mode === "batch";
  const blackjack = gameType === "blackjack";
  $("#gamesLabel").hidden = !batch;
  $("#roundsLabel").hidden = !blackjack;
  $("#maxRoundsLabel").hidden = blackjack;
  updateEstimateLine();
  $("#stratWrap").hidden = !blackjack;
  $("#namesLabel").hidden = batch || blackjack;
  $("#importBtn").hidden = batch;
  $("#playersLabel").firstChild.textContent = blackjack ? "Seats" : "Players";
  $("#seed").placeholder = batch ? "base seed" : "random";
  $("#simulateBtn").textContent = batch ? "Run batch" : "Simulate";
  $("#welcomeAction").textContent = batch ? "Run batch" : "Simulate";
}

function selectedStrategies() {
  return [...$("#stratChips").children]
    .filter((chip) => chip.classList.contains("on"))
    .map((chip) => chip.dataset.name);
}

function showResults() {
  const hasData = mode === "single" ? state !== null : batchData !== null;
  $("#welcome").hidden = hasData;
  $("#results").hidden = !hasData;
  for (const sel of BATCH_SECTIONS) $(sel).hidden = mode !== "batch" || !batchData;
  if (mode === "batch" && batchData) {
    $("#evSection").hidden = batchData.game !== "blackjack";
    $("#seatSection").hidden = batchData.game === "blackjack";
  }
  $("#batchNote").hidden = mode !== "batch" || !batchData || !batchNoteText;
  if (mode === "single" && state) {
    const full = state.mode === "full";
    $("#stats").hidden = false;
    $("#chartSection").hidden = false;
    $("#playback").hidden = !full;
    $("#table").hidden = !full;
    $("#elimSection").hidden = full || state.game !== "war";
    $("#condensedNote").hidden = full;
    // "WINNER: unfinished" needs the sentence that explains it. Kept quiet
    // during suspense (it would spoil that nobody wins).
    const unfinished = state.game === "war" && !state.summary.completed && !state.suspense;
    if (unfinished) {
      $("#unfinishedNote").textContent =
        `⚠ No winner: this game hit the ${fmt.format(state.rounds)}-round "Max rounds" ` +
        `safety cap and was stopped unfinished. Raise Max rounds (or use fewer decks — ` +
        `more cards mean longer games) to let it play to the end.`;
    }
    $("#unfinishedNote").hidden = !unfinished;
  } else {
    for (const sel of SINGLE_SECTIONS) $(sel).hidden = true;
  }
}

async function simulate(event) {
  event.preventDefault();
  if (mode === "batch") return runBatch();
  const engine = pickEngine();
  const button = $("#simulateBtn");
  button.disabled = true;
  button.textContent = "Simulating…";
  try {
    if (engine === "v2") {
      try {
        await simulateV2();
        return;
      } catch (error) {
        if (error.v2Final) throw error;
        console.warn(
          "[ludicrous] client-side (v2) engine unavailable — falling back to the server:",
          error);
      }
    }
    const payload = {
      game: gameType,
      players: Number($("#players").value),
      decks: Number($("#decks").value),
      names: $("#nameMode").value,
      seed: parseSeed($("#seed").value) ?? "",
    };
    if (gameType === "blackjack") {
      payload.rounds = Number($("#rounds").value);
      payload.strategies = selectedStrategies();
    } else {
      payload.max_rounds = roundCap();
    }
    loadingAbort = new AbortController();
    showLoading(gameType === "blackjack"
      ? `Dealing ${fmt.format(payload.rounds)} rounds of blackjack…`
      : "Simulating on the server…");
    const startedAt = performance.now();
    const response = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: loadingAbort.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    load(data, performance.now() - startedAt);
  } catch (error) {
    showError(error.name === "AbortError" ? "Simulation canceled." : error.message);
  } finally {
    hideLoading();
    button.disabled = false;
    button.textContent = "Simulate";
  }
}

function importRecording(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      if (!data.summary || !data.events) throw new Error("not a recording (expected summary + events)");
      load({ mode: "full", summary: data.summary, events: data.events });
    } catch (error) {
      showError(`Import failed: ${error.message}`);
    }
  };
  reader.readAsText(file);
}

// --------------------------------------------------------------- indexing

function buildIndex(events, rounds) {
  const perRound = new Array(rounds + 1).fill(null);
  const roundAt = (r) => (perRound[r] ??= { faces: {}, counts: null, war: null, win: null, drawn: null, elims: [] });
  const countsSeries = {};
  const elimRound = {};
  const winners = new Int32Array(rounds + 1);
  let names = null;
  let wars = 0, deepestWar = 0, biggestPot = 0;
  let deepestWarRound = 0, biggestPotRound = 0;

  for (const e of events) {
    switch (e.type) {
      case "GameStarted":
        names = e.player_names;
        break;
      case "CardsDealt":
        for (const [pid, count] of Object.entries(e.card_counts)) countsSeries[pid] = [count];
        break;
      case "CardPlayed":
        if (e.face_up) roundAt(e.round).faces[e.player] = e.card;
        break;
      case "WarDeclared": {
        const round = roundAt(e.round);
        round.war = { depth: e.depth, tiebreaker: e.tiebreaker, players: e.players };
        wars += 1;
        if (e.depth > deepestWar) {
          deepestWar = e.depth;
          deepestWarRound = e.round;
        }
        break;
      }
      case "PlayerEliminated":
        roundAt(e.round).elims.push(e.player);
        elimRound[e.player] = e.round;
        countsSeries[e.player].push(0);
        break;
      case "RoundWon": {
        roundAt(e.round).win = { winner: e.winner, cards: e.cards_won, via: e.via };
        winners[e.round] = e.winner;
        if (e.cards_won > biggestPot) {
          biggestPot = e.cards_won;
          biggestPotRound = e.round;
        }
        break;
      }
      case "RoundDrawn":
        roundAt(e.round).drawn = { players: e.players };
        break;
      case "RoundEnded": {
        roundAt(e.round).counts = e.card_counts;
        for (const [pid, count] of Object.entries(e.card_counts)) countsSeries[pid].push(count);
        break;
      }
    }
  }
  const elimSorted = Object.entries(elimRound)
    .map(([pid, round]) => ({ player: Number(pid), round }))
    .sort((a, b) => a.round - b.round);
  return {
    perRound, countsSeries, elimRound, winners, elimSorted,
    namesFromEvents: names,
    computedStats: {
      wars, deepest_war: deepestWar, biggest_pot: biggestPot,
      deepest_war_round: deepestWarRound, biggest_pot_round: biggestPotRound,
    },
  };
}

// Chart sample rounds: CHART_POINTS uniform samples across the game, plus a
// dense opening — every round through CHART_DENSE_ROUNDS, then 2% steps until
// the uniform series is at least that fine. The opening of a big game is a
// few hundred rounds that playback spends real seconds on, and a uniform
// series puts them all in one pixel. Mirrored in server.py
// (chart_sample_rounds) and the wasm prepare pass (prepared.rs).
const CHART_DENSE_ROUNDS = 200;
const CHART_GEO_DIVISOR = 50;

function chartSampleRounds(totalRounds) {
  const samples = Math.min(totalRounds, CHART_POINTS);
  const sampleSet = new Set();
  for (let i = 0; i <= samples; i++) sampleSet.add(Math.round((i * totalRounds) / samples));
  for (let r = 0; r < totalRounds;) {
    r = r < CHART_DENSE_ROUNDS ? r + 1 : r + Math.max(1, Math.floor(r / CHART_GEO_DIVISOR));
    sampleSet.add(Math.min(r, totalRounds));
  }
  return [...sampleSet].sort((a, b) => a - b);
}

function downsampleCounts(countsSeries, totalRounds) {
  const rounds = chartSampleRounds(totalRounds);
  const series = {};
  for (const [pid, counts] of Object.entries(countsSeries)) {
    series[pid] = rounds.map((r) => (r < counts.length ? counts[r] : null));
  }
  return { rounds, series };
}

function prepare(data) {
  const gameName = data.game || data.summary.game || "war";
  if (gameName === "blackjack") return prepareBlackjack(data);
  const s = {
    game: "war",
    mode: data.mode,
    summary: data.summary,
    rounds: data.summary.rounds,
    standings: data.summary.standings,
    names: data.names || null,
    stats: data.stats || null,
  };
  if (data.mode === "full") {
    Object.assign(s, buildIndex(data.events, s.rounds));
    s.chartPrefixMax = null;
    s.names = s.names || s.namesFromEvents || {};
    s.stats = s.stats || { ...s.computedStats, total_cards: data.summary.num_decks * 52 };
    s.chartData = downsampleCounts(s.countsSeries, s.rounds);
    s.initialCounts = {};
    for (const [pid, counts] of Object.entries(s.countsSeries)) s.initialCounts[pid] = counts[0];
  } else {
    s.chartData = data.chart;
    s.eliminations = data.eliminations;
    s.elimRound = {};
    for (const e of data.eliminations) s.elimRound[e.player] = e.round;
  }
  s.totalCards = s.stats.total_cards;
  s.chartRange = { yMin: 0, yMax: s.totalCards };
  return s;
}

function buildIndexBlackjack(events, rounds) {
  const perRound = new Array(rounds + 1).fill(null);
  const roundAt = (r) => (perRound[r] ??= {
    hands: {}, dealer: [], dealerRevealed: false, results: {},
    bankrolls: null, shuffled: false, splits: 0,
  });
  const bankrollSeries = {};
  let names = null;
  let strategies = null;
  for (const e of events) {
    switch (e.type) {
      case "GameStarted":
        names = e.player_names;
        for (const sid of Object.keys(e.player_names)) bankrollSeries[sid] = [0];
        break;
      case "StrategiesAssigned":
        strategies = e.strategies;
        break;
      case "ShoeShuffled":
        if (e.round > 0) roundAt(e.round).shuffled = true;
        break;
      case "CardDealt": {
        const round = roundAt(e.round);
        if (e.seat === 0) round.dealer.push({ card: e.card, faceUp: e.face_up });
        else {
          // hands[seat] is an array of hands (splits create indexes 1+);
          // e.hand is undefined in pre-split recordings -> hand 0
          const seatHands = (round.hands[e.seat] ??= []);
          (seatHands[e.hand ?? 0] ??= []).push(e.card);
        }
        break;
      }
      case "HandSplit": {
        // the pair card was dealt to the source hand; move it to the new one
        const round = roundAt(e.round);
        round.splits += 1;
        const seatHands = (round.hands[e.seat] ??= []);
        const from = seatHands[e.hand ?? 0] || [];
        (seatHands[e.new_hand] ??= []).push(from.pop());
        break;
      }
      case "DealerRevealed":
        roundAt(e.round).dealerRevealed = true;
        break;
      case "HandResult":
        (roundAt(e.round).results[e.seat] ??= [])[e.hand ?? 0] = {
          outcome: e.outcome, payout: e.payout,
          playerTotal: e.player_total, dealerTotal: e.dealer_total,
        };
        break;
      case "RoundSettled": {
        roundAt(e.round).bankrolls = e.bankrolls;
        for (const [sid, bankroll] of Object.entries(e.bankrolls)) {
          bankrollSeries[sid].push(bankroll);
        }
        break;
      }
    }
  }
  return { perRound, bankrollSeries, namesFromEvents: names, strategiesFromEvents: strategies };
}

function prepareBlackjack(data) {
  const s = {
    game: "blackjack",
    mode: data.mode || "full",
    summary: data.summary,
    rounds: data.summary.rounds,
    standings: data.summary.standings,
    names: data.names || null,
    strategies: data.strategies || null,
    stats: data.stats || null,
  };
  if (s.mode === "full") {
    Object.assign(s, buildIndexBlackjack(data.events, s.rounds));
    s.names = s.names || s.namesFromEvents || {};
    s.strategies = s.strategies || s.strategiesFromEvents || {};
    s.chartData = downsampleCounts(s.bankrollSeries, s.rounds);
  } else {
    s.chartData = data.chart;
  }
  if (!s.stats) {
    const seats = Object.values(data.summary.seats);
    s.stats = {
      hands: seats.reduce((a, x) => a + x.hands, 0),
      net: Math.round(seats.reduce((a, x) => a + x.bankroll, 0) * 10) / 10,
      blackjacks: seats.reduce((a, x) => a + x.blackjacks, 0),
      busts: seats.reduce((a, x) => a + x.busts, 0),
      splits: seats.reduce((a, x) => a + (x.splits || 0), 0),
    };
  }
  let lo = 0, hi = 1;
  for (const values of Object.values(s.chartData.series)) {
    for (const v of values) {
      if (v == null) continue;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  }
  s.chartRange = { yMin: lo === 0 ? 0 : Math.floor(lo * 1.1), yMax: Math.ceil(hi * 1.1) };
  return s;
}

// -------------------------------------------------------------- rendering

function load(data, elapsedMs) {
  pause();
  state = prepare(data);
  if (elapsedMs !== undefined) state.prepareMs = elapsedMs;
  activate();
}

// Everything that happens once `state` is built, whichever engine built it.
function activate() {
  pause();
  current = -1;
  pos = 0;
  winsCache = { round: -1, wins: {} };
  v2RoundQueued = null;
  loadGen += 1;

  const full = state.mode === "full";
  const blackjack = state.game === "blackjack";

  // Suspense is the default: the winner, the spoiler stats, and the chart's
  // future stay hidden until playback gets there (or "Skip to results").
  // Only a ?round= deep link starts revealed — it points at a specific
  // moment in a known game. A plain run=1 URL does NOT reveal: the app
  // writes run=1 into the address bar after every simulate, so a reload of
  // your own game would spoil it (that bug shipped once; don't rebuild it).
  state.suspense = full && pendingRound === null;
  $("#skipBtn").hidden = !state.suspense;
  $("#finale").hidden = true;
  $("#pauseNote").hidden = true;

  showResults();
  $("#chartHint").hidden = !full;
  $("#chartTitle").textContent = blackjack ? "Bankroll over rounds (units)" : "Card counts over time";
  $("#pauseElim").parentElement.hidden = blackjack;

  renderStats();
  renderLegend();
  applyLayoutPrefs();
  drawChart();
  updateSpeedLabels();

  state.highlights = full && state.game === "war" ? buildHighlights() : null;
  const hasReel = !!state.highlights && state.highlights.length >= 3;
  $("#reelBtn").hidden = !hasReel;
  if (hasReel) {
    const secs = state.highlights.length * ((REEL_LEAD + REEL_TAIL) / REEL_SPEED + 0.15);
    $("#reelBtn").textContent = `▶ Highlights (${fmtDuration(secs)})`;
  }
  renderHighlights();

  if (full) {
    $("#scrubber").max = state.rounds;
    $("#scrubber").value = 0;
    buildGrid();
    seek(pendingRound !== null ? pendingRound : 0);
    pendingRound = null;
  } else {
    $("#condensedNote").textContent = blackjack
      ? `This session ran ${fmt.format(state.rounds)} rounds — too long for hand-by-hand playback, ` +
        `so here's the aggregate view.`
      : `This game ran ${fmt.format(state.rounds)} rounds — too long for card-by-card playback, ` +
        `so here's the aggregate view. (Full playback kicks in for games under ~40,000 rounds.)`;
    if (!blackjack) renderElimFeed();
    drawOverlay();
  }
}

// Ends suspense: unmask the tiles, unmask the chart, show the finale line.
// Reached by playback arriving at the last round, by "Skip to results", by
// ⏭, or by scrubbing to the end.
function revealResults() {
  if (!state || !state.suspense) return;
  state.suspense = false;
  $("#skipBtn").hidden = true;
  renderStats();
  showResults();   // re-evaluates the unfinished-game note
  drawChart();     // snap the zoomed axis back to the full game, mask off
  renderHighlights();  // the labeled chips waited for the reveal
  showFinale();
}

function showFinale() {
  const el = $("#finale");
  const { summary, stats } = state;
  if (state.game === "war") {
    el.innerHTML = summary.completed
      ? `🏆 <span class="win-name">${state.names[summary.winner]}</span> takes it in ` +
        `${fmt.format(summary.rounds)} rounds — ${fmt.format(stats.wars)} wars` +
        (stats.deepest_war ? `, deepest ×${stats.deepest_war}` : "") +
        `, biggest pot ${fmt.format(stats.biggest_pot)} cards.`
      : `No winner — the game was stopped at the ${fmt.format(summary.rounds)}-round safety cap.`;
  } else {
    const winner = summary.winner ? summary.seats[summary.winner] : null;
    el.innerHTML = (winner
      ? `🏆 <span class="win-name">${winner.name}</span> finishes ${signed(winner.bankroll)}u — table `
      : `Table finishes `) +
      `${signed(stats.net)}u over ${fmt.format(summary.rounds)} rounds.`;
  }
  el.hidden = false;
}

function fmtDuration(seconds) {
  if (seconds < 90) return `~${Math.max(1, Math.round(seconds))}s`;
  if (seconds < 5400) return `~${Math.round(seconds / 60)}m`;
  if (seconds < 99 * 3600) return `~${(seconds / 3600).toFixed(1)}h`;
  return `~${Math.round(seconds / 86400)}d`;
}

// -------------------------------------------------------- highlight reel
//
// An OPTIONAL way to watch, never the default: the game's key moments —
// first blood, the endgame eliminations, the deepest war, the biggest pot,
// lead changes — played a few rounds each in order. In suspense mode the
// reel works (it only ever moves the playhead forward, so the chart reveal
// stays honest) but the labeled chips wait for the reveal.

const REEL_SPEED = 6;  // rnd/s while the reel plays
const REEL_LEAD = 4;   // rounds shown before each moment
const REEL_TAIL = 3;   // rounds shown after it
let reel = null;       // {idx, until} while the reel is playing
let reelJumping = false;

function buildHighlights() {
  if (state.game !== "war" || state.mode !== "full") return null;
  const raw = [];
  const push = (round, label) => {
    if (round >= 1 && round <= state.rounds) raw.push({ round, label });
  };

  const elims = state.elimSorted || [];
  if (elims.length) {
    const first = elims[0];
    push(first.round, `☠ first blood — ${state.names[first.player]} out`);
    for (const e of elims.slice(-3)) {
      if (e.round === first.round) continue;
      push(e.round, `☠ ${state.names[e.player]} out (#${state.standings.indexOf(e.player) + 1})`);
    }
  }
  const stats = state.stats;
  if (stats.deepest_war_round && stats.deepest_war > 1) {
    push(stats.deepest_war_round, `⚔ deepest war ×${stats.deepest_war}`);
  }
  if (stats.biggest_pot_round) {
    push(stats.biggest_pot_round, `💰 biggest pot — ${fmt.format(stats.biggest_pot)} cards`);
  }

  // Lead changes, at chart-sample resolution (exactness doesn't matter for
  // "take me to where the game turned"). The opening rounds are churn, not
  // narrative — skip changes before round 10.
  const { rounds: xs, series } = state.chartData;
  const pids = Object.keys(series);
  let leader = null;
  const changes = [];
  for (let i = 0; i < xs.length; i++) {
    let best = -1;
    let bestPid = null;
    for (const pid of pids) {
      const v = series[pid][i];
      if (v != null && v > best) { best = v; bestPid = Number(pid); }
    }
    if (bestPid === null) continue;
    if (leader !== null && bestPid !== leader && xs[i] >= 10) {
      changes.push({ round: xs[i], pid: bestPid });
    }
    leader = bestPid;
  }
  const step = Math.max(1, Math.ceil(changes.length / 5));
  for (let i = 0; i < changes.length; i += step) {
    push(changes[i].round, `📈 ${state.names[changes[i].pid]} takes the lead`);
  }

  push(state.rounds, "🏁 the finish");

  // Sort, and merge moments that share a round.
  raw.sort((a, b) => a.round - b.round);
  const merged = [];
  for (const m of raw) {
    const last = merged[merged.length - 1];
    if (last && last.round === m.round) last.label += ` · ${m.label}`;
    else merged.push({ ...m });
  }
  return merged;
}

function renderHighlights() {
  const strip = $("#highlights");
  const moments = state.highlights;
  const show = !!(moments && moments.length) && !state.suspense;
  strip.hidden = !show;
  if (!show) return;
  strip.innerHTML = moments
    .map((m, i) =>
      `<button class="hl-chip" data-hl="${i}" type="button">` +
      `${m.label} <span class="hint" title="round ${fmt.format(m.round)}">· r${fmtNum(m.round)}</span></button>`)
    .join("");
}

function reelSeek(round) {
  reelJumping = true;
  seek(round);
  reelJumping = false;
}

// Move the reel to its next moment; false when the reel is finished.
function advanceReel() {
  reel.idx += 1;
  const moments = state.highlights;
  if (reel.idx >= moments.length) {
    reel = null;
    return false;
  }
  const moment = moments[reel.idx];
  reel.until = Math.min(state.rounds, moment.round + REEL_TAIL);
  reelSeek(Math.max(0, moment.round - REEL_LEAD));
  return true;
}

function playReel() {
  if (!state || !state.highlights || !state.highlights.length) return;
  pause();  // also clears any running reel
  reel = { idx: -1, until: 0 };
  advanceReel();
  playing = true;
  lastTs = 0;
  $("#playBtn").textContent = "⏸";
  requestAnimationFrame(tick);
}

// Playback speed in rounds/sec for a speed-select value. Absolute values
// ("10") pass through; duration values ("d60" = the whole game in ~60 s)
// scale to the round count, so "game in ~1 min" means the same thing at
// 1,500 rounds and at 300,000. The floor keeps tiny games from crawling —
// they just finish early.
const MIN_SCALED_SPEED = 3;

function speedFor(value) {
  if (value.startsWith("d")) {
    return Math.max(MIN_SCALED_SPEED, state.rounds / Number(value.slice(1)));
  }
  return Number(value);
}

// ---- elimination-aware schedule for the scaled speeds
//
// A big War game is a crowded opening (three quarters of the field goes out
// inside the first hand's worth of rounds), a middle where the last dozen
// drop one by one, and a duel that is most of the game by round count. At
// one constant rate the opening is over in a millisecond. So the "game in
// ~N" budget is split by phase: the opening plays at a fixed slow pace, each
// middle elimination gets the same beat, and the duel takes what is left,
// never under 60%. Speed is constant inside a span between eliminations, so
// the scrubber and round counter need to know nothing about this.
const OPENING_RATE = 3;        // rounds/s while the field is crowded
const OPENING_SHARE = 0.20;    // of the budget, at most
const MIDDLE_SHARE = 0.20;
const MIDDLE_MIN_BEAT = 0.5;   // seconds per elimination, when the budget allows

function buildPlaybackPlan(budget) {
  const total = state.rounds;
  const players = state.summary.num_players;
  const elims = state.elimSorted || [];
  const bounds = [0];
  for (const e of elims) {
    if (e.round > 0 && e.round < total && e.round !== bounds[bounds.length - 1]) bounds.push(e.round);
  }
  bounds.push(total);
  const crowded = Math.max(10, players / 4);
  const spans = [];
  let outSoFar = 0;
  for (let i = 0; i + 1 < bounds.length; i++) {
    while (outSoFar < elims.length && elims[outSoFar].round <= bounds[i]) outSoFar++;
    const alive = players - outSoFar;
    spans.push({
      from: bounds[i], to: bounds[i + 1],
      phase: alive > crowded ? "opening" : alive > 2 ? "middle" : "duel",
    });
  }
  const rounds = (phase) => spans.filter((x) => x.phase === phase).reduce((a, x) => a + x.to - x.from, 0);
  const middle = spans.filter((x) => x.phase === "middle");
  const openingSecs = Math.min(OPENING_SHARE * budget, rounds("opening") / OPENING_RATE);
  let beat = middle.length ? (MIDDLE_SHARE * budget) / middle.length : 0;
  if (middle.length && beat < MIDDLE_MIN_BEAT && middle.length * MIDDLE_MIN_BEAT <= 0.25 * budget) {
    beat = MIDDLE_MIN_BEAT;
  }
  const middleSecs = beat * middle.length;
  const duelRounds = rounds("duel");
  const duelSecs = Math.max(budget - openingSecs - middleSecs, 0.6 * budget);
  const duelSpeed = Math.max(MIN_SCALED_SPEED, duelRounds / duelSecs);
  for (const span of spans) {
    const n = span.to - span.from;
    span.speed = span.phase === "opening" ? OPENING_RATE
      : span.phase === "middle" ? Math.max(MIN_SCALED_SPEED, n / beat)
      : duelSpeed;
  }
  return { spans, duelSpeed, openingSecs, middleSecs, duelSecs };
}

function slowOpeningOn() {
  return layoutPrefs.slowOpening === true;
}

function highlightPref() {
  const n = Number(layoutPrefs.highlightN);
  return n >= 1 && n <= HIGHLIGHT_MAX ? n : 10;
}

// The default: one constant rate across the budget, with one exception. At
// 600k rounds/s the crowded opening is a single frame, so while the field is
// crowded the rate is capped at one round per frame — the opening of a
// 1000-player game is about two seconds of cards flipping, then the game
// runs proportionally. Small games never hit the cap.
const FRAME_RATE = 60;  // rounds/s: one round per frame

function buildStraightPlan(budget) {
  const total = state.rounds;
  const players = state.summary.num_players;
  const crowded = Math.max(10, players / 4);
  let openingEnd = 0;
  const elims = state.elimSorted || [];
  for (let i = 0; i < elims.length; i++) {
    if (players - (i + 1) <= crowded) { openingEnd = Math.min(elims[i].round, total); break; }
  }
  if (players <= crowded) openingEnd = 0;
  const straight = Math.max(MIN_SCALED_SPEED, total / budget);
  const openingSpeed = Math.min(FRAME_RATE, straight);
  const openingSecs = openingEnd / openingSpeed;
  const restSpeed = openingEnd < total
    ? Math.max(MIN_SCALED_SPEED, (total - openingEnd) / Math.max(budget - openingSecs, 0.5 * budget))
    : straight;
  const spans = [];
  if (openingEnd > 0) spans.push({ from: 0, to: openingEnd, phase: "opening", speed: openingSpeed });
  spans.push({ from: openingEnd, to: total, phase: "duel", speed: restSpeed });
  return { spans, duelSpeed: restSpeed, openingSecs, phased: false };
}

function playbackPlan(value) {
  if (!value.startsWith("d")) return null;
  if (!state || state.game !== "war" || state.mode !== "full" || !state.elimSorted) return null;
  state.plans ??= {};
  const key = value + (slowOpeningOn() ? ":phased" : ":straight");
  return (state.plans[key] ??= slowOpeningOn()
    ? { ...buildPlaybackPlan(Number(value.slice(1))), phased: true }
    : buildStraightPlan(Number(value.slice(1))));
}

function spanAt(plan, at) {
  const spans = plan.spans;
  let lo = 0, hi = spans.length - 1;
  while (lo < hi) {  // last span whose `from` is <= at
    const mid = (lo + hi + 1) >> 1;
    if (spans[mid].from <= at) lo = mid; else hi = mid - 1;
  }
  return spans[lo];
}

// Rounds/s at playhead position `at` for the selected speed.
function playSpeedAt(at) {
  const value = $("#speedSel").value;
  const plan = playbackPlan(value);
  return plan ? spanAt(plan, at).speed : speedFor(value);
}

function playSpeed() {
  return playSpeedAt(pos);
}

// "10 rnd/s" means nothing for a 41,919-round game until you do the division
// — so do it for the user: absolute speeds show how long THIS game takes,
// scaled speeds show the rate they work out to.
function updateSpeedLabels() {
  const full = state && state.mode === "full";
  for (const option of $("#speedSel").options) {
    const base = (option.dataset.base ??= option.textContent);
    if (!full) { option.textContent = base; continue; }
    const plan = playbackPlan(option.value);
    const speed = plan ? plan.duelSpeed : speedFor(option.value);
    option.textContent = option.value.startsWith("d")
      ? `${base} · ${fmtNum(Math.round(speed))} rnd/s${plan && plan.phased ? " in the duel" : ""}`
      : `${base} · ${fmtDuration(state.rounds / speed)}`;
  }
}

function renderStats() {
  const { summary, stats } = state;
  const MASK = "?";  // suspense mode: outcome tiles stay masked until reveal
  const hide = state.suspense;
  const tileHtmlMasked = ([label, value, exact]) =>
    `<div class="tile"><div class="label">${label}</div>` +
    `<div class="value${value === MASK ? " masked" : ""}" title="${exact ?? value}">${value}</div></div>`;
  let tiles;
  if (state.game === "blackjack") {
    const winner = summary.winner ? summary.seats[summary.winner] : null;
    tiles = [
      ["Winner",
       hide ? MASK : winner ? `${winner.name} · ${signed(winner.bankroll)}u` : "—"],
      ["Rounds", fmtNum(summary.rounds), fmt.format(summary.rounds)],
      ["Hands", fmtNum(stats.hands), fmt.format(stats.hands)],
      ["Table net", hide ? MASK : `${stats.net >= 0 ? "+" : ""}${fmt.format(stats.net)}u`],
      ["Blackjacks", hide ? MASK : fmt.format(stats.blackjacks)],
      ["Splits", hide ? MASK : fmt.format(stats.splits ?? 0)],
      ["Busts", hide ? MASK : fmt.format(stats.busts)],
      ["Seats / decks", `${summary.num_players} / ${summary.num_decks}`],
      ["Seed", String(summary.seed)],
    ];
  } else {
    const winnerName = summary.winner ? state.names[summary.winner] : "—";
    tiles = [
      ["Winner", hide ? MASK : summary.completed ? winnerName : "unfinished"],
      ["Rounds", fmtNum(summary.rounds), fmt.format(summary.rounds)],
      ["Wars", hide ? MASK : fmtNum(stats.wars), hide ? MASK : fmt.format(stats.wars)],
      ["Deepest war", hide ? MASK : stats.deepest_war ? `×${stats.deepest_war}` : "—"],
      ["Biggest pot", hide ? MASK : `${fmtNum(stats.biggest_pot)} cards`,
       hide ? MASK : `${fmt.format(stats.biggest_pot)} cards`],
      ["Players / cards", `${fmt.format(summary.num_players)} / ${fmtNum(stats.total_cards)}`,
       `${fmt.format(summary.num_players)} / ${fmt.format(stats.total_cards)}`],
      ["Seed", String(summary.seed)],
    ];
  }
  if (state.prepareMs !== undefined) tiles.push(["Simulated in", fmtMs(state.prepareMs)]);
  $("#stats").innerHTML = tiles.map(tileHtmlMasked).join("");
  fitTiles($("#stats"));
}

function buildGrid() {
  const grid = $("#grid");
  const dealerArea = $("#dealerArea");
  const count = Object.keys(state.names).length;
  $("#outStrip").hidden = true;
  $("#outStrip")._count = -1;
  $("#tableTitle")._in = undefined;
  $("#tableTitle").textContent = state.game === "blackjack"
    ? `The table — ${count} seat${count === 1 ? "" : "s"} vs the dealer`
    : `The table — ${count} players`;
  $("#tableHint").textContent = state.game === "blackjack"
    ? "" : "— under each card: cards held · rounds won";
  $("#elimDisplayLabel").hidden = state.game === "blackjack";
  grid.innerHTML = "";
  grid.classList.toggle("bj", state.game === "blackjack");
  if (state.game === "blackjack") {
    dealerArea.hidden = false;
    dealerArea.innerHTML =
      `<span class="dlabel">Dealer</span>` +
      `<div class="hand-cards" id="dealerCards"></div>` +
      `<span class="dtotal" id="dealerTotal"></span>`;
    for (const sid of Object.keys(state.names)) {
      const tile = document.createElement("div");
      tile.className = "player";
      tile.dataset.pid = sid;
      const strategy = STRATEGY_LABELS[state.strategies[sid]] || state.strategies[sid] || "";
      tile.innerHTML =
        `<div class="pname" title="${state.names[sid]}">${state.names[sid]}</div>` +
        `<div class="pstrat" title="${strategy}">${strategy}</div>` +
        `<div class="hand-cards"></div>` +
        `<div class="pmeta"></div>`;
      grid.appendChild(tile);
    }
    return;
  }
  dealerArea.hidden = true;
  for (const pid of Object.keys(state.names)) {
    const tile = document.createElement("div");
    tile.className = "player";
    tile.dataset.pid = pid;
    tile.innerHTML =
      `<div class="pname" title="${state.names[pid]}">${state.names[pid]}</div>` +
      `<img src="${CARD_BACK}" alt="">` +
      `<div class="pmeta" title="cards held · rounds won"></div>`;
    grid.appendChild(tile);
  }
}

function winsAt(round) {
  if (winsCache.round === round) return winsCache.wins;
  if (winsCache.round === round - 1) {
    const w = state.winners[round];
    if (w) winsCache.wins[w] = (winsCache.wins[w] || 0) + 1;
    winsCache.round = round;
    return winsCache.wins;
  }
  const wins = {};
  for (let r = 1; r <= round; r++) {
    const w = state.winners[r];
    if (w) wins[w] = (wins[w] || 0) + 1;
  }
  winsCache = { round, wins };
  return wins;
}

function describeRound(roundData, round) {
  if (!roundData) return `Cards dealt — ${state.summary.num_players} players, ${fmt.format(state.totalCards)} cards. Press play.`;
  const parts = [];
  if (roundData.win) {
    const { winner, cards, via } = roundData.win;
    let tail = "";
    if (via === "war") tail = ` <span class="war-flash">after a WAR${roundData.war && roundData.war.depth > 1 ? ` ×${roundData.war.depth}` : ""}</span>`;
    if (via === "forfeit") tail = " by forfeit";
    parts.push(`<span class="win-name">${state.names[roundData.win.winner]}</span> wins ${fmt.format(cards)} cards${tail}`);
  } else if (roundData.drawn) {
    parts.push(`<span class="war-flash">Drawn war</span> — table split between ${roundData.drawn.players.length} players`);
  }
  for (const pid of roundData.elims) {
    const place = state.standings.indexOf(pid) + 1;
    parts.push(`${state.names[pid]} eliminated (#${place})`);
  }
  return `Round ${fmt.format(round)}: ` + parts.join(" · ");
}

function render(round) {
  current = round;
  $("#scrubber").value = round;
  const label = $("#roundLabel");
  label.textContent = `Round ${fmtNum(round)} / ${fmtNum(state.rounds)}`;
  label.title = `Round ${fmt.format(round)} of ${fmt.format(state.rounds)}`;
  if (state.suspense && round >= state.rounds) revealResults();
  if (state.game === "blackjack") {
    renderBlackjackRound(round);
    if (state.suspense) drawChart(); else drawOverlay();  // live axis follows the playhead
    return;
  }
  renderWarRound(round);
  if (state.suspense) drawChart(); else drawOverlay();
}

function renderWarRound(round) {
  // v1 has the whole round index in memory; v2 asks the worker for it and
  // paints when the answer comes back.
  if (state.engine === "v2") {
    requestV2Round(round);
    return;
  }
  paintWarRound(round, round > 0 ? state.perRound[round] : null, winsAt(round));
}

function paintWarRound(round, roundData, wins) {
  const warPlayers = roundData?.war ? new Set(roundData.war.players) : null;
  const linger = elimHideAfter();
  if (!state.rankOf) state.rankOf = new Map(state.standings.map((pid, i) => [pid, i + 1]));

  // At 1000 tiles, touching every tile every frame is the frame budget. Each
  // tile remembers what it last painted and is skipped when nothing changed
  // -- in a long game that is every eliminated tile, which is most of them.
  for (const tile of $("#grid").children) {
    const pid = Number(tile.dataset.pid);
    const outAt = state.elimRound[pid];
    const out = outAt !== undefined && outAt <= round;
    const hidden = out && linger !== null && round >= outAt + linger;
    const winner = roundData?.win?.winner === pid;
    const war = !out && !!warPlayers?.has(pid);
    let src, text;
    if (out) {
      src = CARD_BACK;
      text = `#${state.rankOf.get(pid) || "?"}`;
    } else {
      const face = roundData?.faces[pid];
      src = face ? cardUrl(face) : CARD_BACK;
      const count = round === 0 ? state.initialCounts[pid] : roundData?.counts?.[pid] ?? 0;
      text = `${fmtNum(count)} · ${fmtNum(wins[pid] || 0)}W`;
    }
    const sig = `${hidden}|${out}|${winner}|${war}|${src}|${text}`;
    if (tile._sig === sig) continue;
    tile._sig = sig;
    tile.hidden = hidden;
    tile.classList.toggle("out", out);
    tile.classList.toggle("winner", winner);
    tile.classList.toggle("war", war);
    const img = tile.querySelector("img");
    if (img.getAttribute("src") !== src) img.src = src;
    tile.querySelector(".pmeta").textContent = text;
  }
  renderOutStrip(round);
  $("#banner").innerHTML = describeRound(roundData, round);
}

// The out-strip: in "collapse into a strip" mode, eliminated players leave
// the grid and stack up here as compact placement chips — the active table
// stays a clean block that shrinks as the field thins, instead of a sea of
// grayed-out tiles at 200 players. Newest elimination first. Rebuilt only
// when the set changes; eliminations are monotonic in round, so the count
// identifies the set (scrubbing back shrinks it again).
function renderOutStrip(round) {
  const strip = $("#outStrip");
  const out = state.elimSorted.filter((e) => e.round <= round);
  const total = Object.keys(state.names).length;
  const title = $("#tableTitle");
  const inCount = total - out.length;
  if (title._in !== inCount) {
    title._in = inCount;
    title.textContent = out.length > 0
      ? `The table — ${fmt.format(inCount)} of ${fmt.format(total)} still in`
      : `The table — ${total} players`;
  }
  const show = elimMode() === "strip" && out.length > 0;
  if (!show) {
    strip.hidden = true;
    strip._count = -1;
    return;
  }
  strip.hidden = false;
  if (strip._count === out.length) return;
  strip._count = out.length;
  strip.innerHTML =
    `<span class="out-label">Out · ${fmtNum(out.length)}</span>` +
    out.slice().reverse().map(({ player, round: r }) =>
      `<span class="out-chip" title="eliminated round ${fmt.format(r)}">` +
      `<b>#${state.standings.indexOf(player) + 1}</b> ${state.names[player]}</span>`)
      .join("");
}

const OUTCOME_LABELS = { win: "Win", blackjack: "Blackjack!", lose: "Lose", bust: "Bust", push: "Push" };

function renderBlackjackRound(round) {
  const roundData = round > 0 ? state.perRound[round] : null;
  const dealerCards = $("#dealerCards");
  const dealerTotal = $("#dealerTotal");
  if (!roundData) {
    dealerCards.innerHTML = "";
    dealerTotal.textContent = "";
  } else {
    dealerCards.innerHTML = roundData.dealer
      .map((entry) => `<img src="${entry.faceUp || roundData.dealerRevealed ? cardUrl(entry.card) : CARD_BACK}" alt="">`)
      .join("");
    const anyResult = Object.values(roundData.results).flat()[0];
    dealerTotal.textContent =
      roundData.dealerRevealed && anyResult ? String(anyResult.dealerTotal) : "?";
  }
  const outcomeClass = (r) =>
    r.outcome === "win" || r.outcome === "blackjack" ? "o-win"
      : r.outcome === "lose" || r.outcome === "bust" ? "o-lose" : "o-push";
  for (const tile of $("#grid").children) {
    const sid = tile.dataset.pid;
    const hands = roundData?.hands[sid] || [];
    const results = roundData?.results[sid] || [];
    tile.querySelector(".hand-cards").innerHTML = hands
      .map((cards, hi) => {
        const r = results[hi];
        const cls = r ? outcomeClass(r).replace("o-", "h-") : "";
        return `<span class="bjhand ${cls}">` +
          cards.map((card) => `<img src="${cardUrl(card)}" alt="">`).join("") +
          `</span>`;
      })
      .join("");
    const meta = tile.querySelector(".pmeta");
    if (!roundData) {
      meta.textContent = "±0u";
      continue;
    }
    const bankroll = roundData.bankrolls?.[sid] ?? 0;
    const perHand = results
      .map((r) => `${r.playerTotal} <span class="outcome ${outcomeClass(r)}">${OUTCOME_LABELS[r.outcome]}</span>`)
      .join(" / ");
    meta.innerHTML = `${perHand} · ${bankroll >= 0 ? "+" : ""}${bankroll}u`;
  }
  $("#banner").innerHTML = describeBlackjackRound(roundData, round);
}

function describeBlackjackRound(roundData, round) {
  if (!roundData) {
    return `Session start — ${state.summary.num_players} seat(s) vs the dealer, ` +
      `${state.summary.num_decks}-deck shoe. Press play.`;
  }
  const outcomes = Object.values(roundData.results).flat();
  const wins = outcomes.filter((r) => r.outcome === "win" || r.outcome === "blackjack").length;
  const losses = outcomes.filter((r) => r.outcome === "lose" || r.outcome === "bust").length;
  const pushes = outcomes.length - wins - losses;
  const net = Math.round(outcomes.reduce((sum, r) => sum + r.payout, 0) * 10) / 10;
  const parts = [
    `${wins} won · ${losses} lost · ${pushes} push${pushes === 1 ? "" : "es"}`,
    `table ${net >= 0 ? "+" : ""}${net}u this round`,
  ];
  if (outcomes.some((r) => r.outcome === "blackjack")) parts.push(`<span class="win-name">Blackjack!</span>`);
  if (roundData.splits) parts.push(`${roundData.splits} split${roundData.splits > 1 ? "s" : ""}`);
  if (roundData.shuffled) parts.push("shoe reshuffled");
  return `Round ${fmt.format(round)}: ` + parts.join(" · ");
}

function renderElimFeed() {
  const feed = $("#elimFeed");
  feed.innerHTML = state.eliminations
    .map(({ round, player }) => {
      const place = state.standings.indexOf(player) + 1;
      return `<li><span class="rnd" title="round ${fmt.format(round)}">Round ${fmtNum(round)}</span> — ${state.names[player]} out (#${place})</li>`;
    })
    .join("");
}

// --------------------------------------------------------------- playback

function seek(round) {
  if (!reelJumping) reel = null;  // manual navigation ends the reel
  round = Math.max(0, Math.min(state.rounds, Math.round(round)));
  pos = round;
  if (round !== current) render(round);
}

function pause() {
  playing = false;
  reel = null;
  const btn = $("#playBtn");
  if (btn) btn.textContent = "▶";
  const note = $("#pauseNote");
  if (note) note.hidden = true;
}

function togglePlay() {
  if (!state || state.mode !== "full") return;
  if (playing) { pause(); return; }
  if (pos >= state.rounds) seek(0);
  playing = true;
  lastTs = 0;
  $("#playBtn").textContent = "⏸";
  requestAnimationFrame(tick);
}

function tick(ts) {
  if (!playing) return;
  if (!lastTs) lastTs = ts;
  const dt = (ts - lastTs) / 1000;
  lastTs = ts;
  let next;
  if (reel) {
    next = Math.min(pos + REEL_SPEED * dt, state.rounds);
  } else {
    // Advance span by span: a frame that crosses into a slower span spends
    // the remaining time at that span's speed, so a long frame never skips
    // the opening.
    const plan = playbackPlan($("#speedSel").value);
    let left = dt;
    next = pos;
    for (let guard = 0; left > 0 && next < state.rounds && guard < 64; guard++) {
      const span = plan ? spanAt(plan, next) : null;
      const speed = span ? span.speed : speedFor($("#speedSel").value);
      const edge = span ? span.to : state.rounds;
      const step = Math.min(speed * left, edge - next);
      left -= step / speed;
      next += step;
    }
    next = Math.min(next, state.rounds);
  }

  if (reel && next >= reel.until) {
    // Land on the moment's last round (so it actually renders — the finale
    // hook included), then cut to the next moment or stop.
    pos = reel.until;
    if (Math.floor(pos) !== current) render(Math.floor(pos));
    if (pos >= state.rounds || !advanceReel()) {
      pause();
      return;
    }
    requestAnimationFrame(tick);
    return;
  }

  if (!reel && state.game === "war" && $("#pauseElim").checked) {
    const from = Math.floor(pos);
    const hit = state.elimSorted.find((e) => e.round > from && e.round <= Math.floor(next));
    if (hit && hit.round < state.rounds) {  // final elimination = game over, no need to pause
      pos = hit.round;
      render(hit.round);
      pause();
      $("#pauseNote").hidden = false;  // say WHY playback stopped
      return;
    }
  }
  pos = next;
  const round = Math.floor(pos);
  if (round !== current) render(round);
  if (pos >= state.rounds) { pause(); return; }
  requestAnimationFrame(tick);
}

// ------------------------------------------------------------------ chart

function highlightN() {
  return Math.min(highlightPref(), state.summary.num_players);
}

function highlightStyle(index) {
  const hue = PALETTE[index % PALETTE.length];
  const tier = Math.floor(index / PALETTE.length);
  return tier === 0 ? { color: hue, width: 2 } : { color: hue + "a6", width: 1.25 };
}

// Everyone ranked by what has happened up to `round`: players still in by
// cards held (bankroll for blackjack), then players already out, most recent
// first. An eliminated player's rank never changes again — it is their final
// place — so nothing here leaks the ending.
function rankingAt(round) {
  const { rounds: xs, series } = state.chartData;
  let i = sampleIndexAt(xs, round);
  if (xs[i] > round && i > 0) i--;
  const alive = [], out = [];
  for (const pid of Object.keys(series)) {
    const e = state.elimRound ? state.elimRound[pid] : undefined;
    if (e != null && e <= round) out.push([pid, e]);
    else alive.push([pid, series[pid][i] ?? -Infinity]);
  }
  alive.sort((a, b) => b[1] - a[1]);
  out.sort((a, b) => b[1] - a[1]);
  return alive.map((a) => a[0]).concat(out.map((o) => o[0]));
}

// While the outcome is hidden the colored lines are the leaders of the
// moment, not the finishers. Colors are sticky: a player takes a free color
// on entering the top N and keeps it until they fall well below the cutoff,
// so two players trading tenth place do not swap colors every frame.
// Scrubbing backwards rebuilds the assignment from scratch (deterministic).
function liveHighlights(round) {
  const n = highlightN();
  const hl = (state.hl ??= { map: new Map(), at: -1, n: 0, cache: null });
  if (hl.cache && hl.cache.round === round && hl.cache.n === n) return hl.cache.list;
  if (round < hl.at || hl.n !== n) { hl.map.clear(); hl.n = n; }
  hl.at = round;
  const ranking = rankingAt(round);
  const rankOf = new Map(ranking.map((pid, i) => [pid, i]));
  const margin = Math.max(2, Math.round(n * 0.3));
  for (const pid of [...hl.map.keys()]) {
    if ((rankOf.get(pid) ?? Infinity) >= n + margin) hl.map.delete(pid);
  }
  const used = new Set(hl.map.values());
  for (let i = 0; i < n && i < ranking.length; i++) {
    const pid = ranking[i];
    if (hl.map.has(pid)) continue;
    if (hl.map.size >= n) {
      // Full: the worst-ranked member is a holder in the hysteresis band
      // (all n members inside the top n would leave no room for this one).
      let worst = null;
      for (const m of hl.map.keys()) {
        if (worst === null || (rankOf.get(m) ?? Infinity) > (rankOf.get(worst) ?? Infinity)) worst = m;
      }
      if ((rankOf.get(worst) ?? Infinity) < n) break;
      used.delete(hl.map.get(worst));
      hl.map.delete(worst);
    }
    let k = 0;
    while (used.has(k)) k++;
    used.add(k);
    hl.map.set(pid, k);
  }
  const list = [...hl.map]
    .sort((a, b) => rankOf.get(a[0]) - rankOf.get(b[0]))
    .map(([pid, k]) => ({ pid: Number(pid), rank: rankOf.get(pid) + 1, ...highlightStyle(k) }));
  hl.cache = { round, n, list };
  return list;
}

function topSeries() {
  if (state.mode === "full" && state.suspense) return liveHighlights(Math.floor(pos));
  return state.standings.slice(0, highlightN()).map((pid, i) => ({ pid, rank: i + 1, ...highlightStyle(i) }));
}

function renderLegend() {
  const top = topSeries();
  const others = state.summary.num_players - top.length;
  let html = top
    .map(({ pid, color }) => `<span class="chip"><i style="background:${color}"></i>${state.names[pid]}</span>`)
    .join("");
  state.legendKey = top.map((t) => t.pid + t.color).join();
  if (others > 0) html += `<span class="chip"><i style="background:${FIELD}"></i>Field (${others} other${others === 1 ? "" : "s"})</span>`;
  $("#legend").innerHTML = html;
}

// Numbers in boxes are compact ("7.07M", "45.2k"); numbers in sentences are
// exact ("7,070,047"). Three significant figures, trailing zeros dropped,
// exact below 10,000. The exact value belongs in the tooltip.
function fmtNum(n) {
  if (n == null || !Number.isFinite(n)) return "—";
  if (n < 0) return "-" + fmtNum(-n);
  const sig = (v) => {
    const digits = v >= 100 ? 0 : v >= 10 ? 1 : 2;
    return String(Number(v.toFixed(digits)));
  };
  if (n >= 1e9) return sig(n / 1e9) + "B";
  if (n >= 1e6) return sig(n / 1e6) + "M";
  if (n >= 1e4) return sig(n / 1e3) + "k";
  return fmt.format(Math.round(n));
}
const compact = fmtNum;

function setupCanvas(canvas) {
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return [ctx, rect.width, rect.height];
}

// Index of the first chart sample at or past `round`.
function sampleIndexAt(xs, round) {
  let lo = 0, hi = xs.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] < round) lo = mid + 1; else hi = mid;
  }
  return lo;
}

// Round a value up to the next 5% step, so an axis that follows the playhead
// moves in a couple of hundred jumps per game instead of one per frame (the
// field layer is redrawn whenever the axes move).
function snapUp(v) {
  return Math.ceil(Math.pow(1.05, Math.ceil(Math.log(Math.max(v, 1)) / Math.log(1.05))));
}

// Largest card count held by anyone at or before sample i, for every i, so
// the live y-axis can read "the biggest stack so far" in O(1) per frame.
function chartPrefixMax() {
  if (state.chartPrefixMax) return state.chartPrefixMax;
  const { rounds: xs, series } = state.chartData;
  const out = new Float64Array(xs.length);
  for (const values of Object.values(series)) {
    for (let i = 0; i < xs.length; i++) {
      const v = values[i];
      if (v == null) break;
      if (v > out[i]) out[i] = v;
    }
  }
  for (let i = 1; i < out.length; i++) if (out[i - 1] > out[i]) out[i] = out[i - 1];
  return (state.chartPrefixMax = out);
}

const MIN_VISIBLE_SAMPLES = 12;

function drawChart() {
  const [ctx, width, height] = setupCanvas($("#chart"));
  const { rounds: xs, series } = state.chartData;
  // Suspense on a big game: against a fixed full-game axis the reveal edge
  // moves invisibly (round 400 of 300,000 is half a pixel). So while the
  // outcome is hidden, both axes span only the revealed portion and grow
  // with the playhead — a live feed — then snap to the full game on reveal.
  // The x window keeps at least MIN_VISIBLE_SAMPLES samples on screen; the
  // samples are dense through the opening (chartSampleRounds), so early in
  // the game that floor is a dozen rounds, not a hundred thousand.
  let xMax = Math.max(state.rounds, 1);
  let { yMin, yMax } = state.chartRange;
  const live = state.suspense && state.mode === "full";
  if (live) {
    const at = sampleIndexAt(xs, pos);
    const floorX = xs[Math.min(at + MIN_VISIBLE_SAMPLES, xs.length - 1)];
    xMax = Math.min(Math.max(state.rounds, 1), snapUp(Math.max(pos * 1.25, floorX, MIN_VISIBLE_SAMPLES)));
    if (state.game === "war") {
      // With 200 players every line starts at 1/200 of the shoe; against a
      // full-shoe axis the opening is a flat smear along the bottom. So the
      // y-axis starts at a few opening stacks and rises with the leader.
      const biggest = chartPrefixMax()[Math.min(at, xs.length - 1)];
      const start = Math.max(...Object.values(state.initialCounts || { a: 1 })) * 2.5;
      yMax = Math.min(state.chartRange.yMax, snapUp(Math.max(biggest * 1.15, start, 10)));
    }
  }
  const pad = { left: 46, right: 12, top: 8, bottom: 22 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const x = (r) => pad.left + (r / xMax) * plotW;
  const y = (v) => pad.top + (1 - (v - yMin) / (yMax - yMin)) * plotH;
  chartScale = { x, y, xs, xMax, yMax, pad, width, height };

  ctx.clearRect(0, 0, width, height);
  ctx.font = "11px system-ui, sans-serif";

  // gridlines + y labels
  ctx.strokeStyle = "#2c2c2a";
  ctx.fillStyle = "#898781";
  ctx.lineWidth = 1;
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  const gridYs = [];
  for (const v of valueTicks(yMin, yMax, 4)) {
    ctx.beginPath();
    ctx.moveTo(pad.left, y(v));
    ctx.lineTo(width - pad.right, y(v));
    ctx.stroke();
    ctx.fillText(compact(v), pad.left - 6, y(v));
    gridYs.push(y(v));
  }
  chartScale.gridYs = gridYs;
  if (yMin < 0) {
    // emphasize break-even
    ctx.strokeStyle = "#54534f";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.left, y(0));
    ctx.lineTo(width - pad.right, y(0));
    ctx.stroke();
    ctx.setLineDash([]);
  }
  // x labels
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (const r of valueTicks(0, xMax, 6)) {
    ctx.fillText(compact(r), x(r), height - pad.bottom + 6);
  }

  const drawSeries = (pid, color, lineWidth) => {
    const values = series[pid];
    if (!values) return;
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < xs.length; i++) {
      if (values[i] == null) break; // series ends at elimination
      if (!started) { ctx.moveTo(x(xs[i]), y(values[i])); started = true; }
      else ctx.lineTo(x(xs[i]), y(values[i]));
    }
    ctx.stroke();
  };

  const top = topSeries();
  const topIds = new Set(top.map((t) => String(t.pid)));
  // Clip to the plot: on the live axes a future value can sit above yMax or
  // past xMax, and the suspense mask only covers the plot itself.
  ctx.save();
  ctx.beginPath();
  ctx.rect(pad.left, pad.top - 2, plotW + pad.right, plotH + 4);
  ctx.clip();
  drawField(ctx, width, height, xMax, series, topIds, x, y, xs);
  for (let i = top.length - 1; i >= 0; i--) drawSeries(String(top[i].pid), top[i].color, top[i].width);
  ctx.restore();
  if (top.map((t) => t.pid + t.color).join() !== state.legendKey) renderLegend();
  drawOverlay();
}

// The field: every series that is not one of the top few, in one muted
// color. With 1000 players that is 1000 polylines, so it is stroked into an
// offscreen canvas and blitted, redrawn only when the axes move. In suspense
// the x axis grows with the playhead; drawChart snaps it to 5% steps, which
// turns thousands of redraws into a couple of hundred across a whole game.
// Series stop at their elimination and the loop stops past the window, so
// the cost is bounded by points actually on screen.
let fieldCache = null;

function drawField(ctx, width, height, xMax, series, topIds, x, y, xs) {
  const key = `${loadGen}|${width}|${height}|${xMax}|${chartScale.yMax}|${[...topIds].join(",")}`;
  if (!fieldCache || fieldCache.key !== key) {
    const layer = fieldCache?.layer || document.createElement("canvas");
    if (layer.width !== ctx.canvas.width || layer.height !== ctx.canvas.height) {
      layer.width = ctx.canvas.width;
      layer.height = ctx.canvas.height;
    }
    const fctx = layer.getContext("2d");
    fctx.setTransform(1, 0, 0, 1, 0, 0);
    fctx.clearRect(0, 0, layer.width, layer.height);
    fctx.setTransform(ctx.getTransform());
    fctx.strokeStyle = FIELD;
    fctx.lineWidth = 1;
    fctx.beginPath();
    for (const pid of Object.keys(series)) {
      if (topIds.has(pid)) continue;
      const values = series[pid];
      let started = false;
      for (let i = 0; i < xs.length; i++) {
        if (values[i] == null) break;
        if (!started) { fctx.moveTo(x(xs[i]), y(values[i])); started = true; }
        else fctx.lineTo(x(xs[i]), y(values[i]));
        if (xs[i] > xMax) break;
      }
    }
    fctx.stroke();
    fieldCache = { key, layer };
  }
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.drawImage(fieldCache.layer, 0, 0);
  ctx.restore();
}

function drawOverlay() {
  if (!chartScale) return;
  const [ctx, width, height] = setupCanvas($("#overlay"));
  const { x, pad } = chartScale;
  ctx.clearRect(0, 0, width, height);
  if (state.mode === "full" && state.suspense) {
    // Suspense: the chart is the biggest spoiler of all, so everything past
    // the playhead is papered over in the panel color — the line "draws
    // itself" as playback advances. Gridlines are re-stroked so the covered
    // region still looks like an empty plot, not a hole.
    const xp = Math.max(pad.left, Math.min(x(pos), width - pad.right));
    ctx.fillStyle = "#1a1a19";  // --surface (committed dark theme)
    // Mask to the canvas edge, not just the plot edge: on a zoomed axis the
    // series overdraws into the right padding, and a sliver would spoil.
    ctx.fillRect(xp, pad.top - 4, width - xp, height - pad.top - pad.bottom + 8);
    ctx.strokeStyle = "#2c2c2a";  // --grid-line
    ctx.lineWidth = 1;
    for (const gy of chartScale.gridYs || []) {
      ctx.beginPath();
      ctx.moveTo(xp, gy);
      ctx.lineTo(width - pad.right, gy);
      ctx.stroke();
    }
  }
  if (state.mode === "full") {
    ctx.strokeStyle = "#c3c2b7";
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(x(pos), pad.top);
    ctx.lineTo(x(pos), height - pad.bottom);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  if (hoverX !== null) {
    ctx.strokeStyle = "rgba(137,135,129,0.6)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(hoverX, pad.top);
    ctx.lineTo(hoverX, height - pad.bottom);
    ctx.stroke();
  }
}

function chartRoundAt(px) {
  const { pad, width, xMax } = chartScale;
  const frac = (px - pad.left) / (width - pad.left - pad.right);
  return Math.max(0, Math.min(xMax, frac * xMax));
}

function handleChartHover(event) {
  if (!chartScale || !state) return;
  const rect = $("#overlay").getBoundingClientRect();
  let px = event.clientX - rect.left;
  // In suspense the future is masked; don't let the tooltip read through it.
  if (state.mode === "full" && state.suspense) px = Math.min(px, chartScale.x(pos));
  hoverX = px;
  const round = chartRoundAt(px);
  const { xs } = chartScale;
  // nearest sample index
  let lo = 0, hi = xs.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] < round) lo = mid + 1; else hi = mid;
  }
  const idx = lo > 0 && Math.abs(xs[lo - 1] - round) < Math.abs(xs[lo] - round) ? lo - 1 : lo;

  const tooltip = $("#tooltip");
  const top = topSeries();
  const shown = top.slice(0, 10);
  let rows = shown
    .map(({ pid, color }) => {
      const value = state.chartData.series[pid]?.[idx];
      const text = value == null ? "out" : fmtNum(value);
      return `<div><span class="dot" style="background:${color}"></span>${state.names[pid]}: <span class="t-val">${text}</span></div>`;
    })
    .join("");
  if (top.length > shown.length) rows += `<div class="t-round">+${top.length - shown.length} more highlighted</div>`;
  tooltip.innerHTML = `<div class="t-round">Round ${fmtNum(xs[idx])}</div>${rows}`;
  tooltip.hidden = false;
  const wrapRect = $("#chartWrap").getBoundingClientRect();
  const flip = px > wrapRect.width - 170;
  tooltip.style.left = flip ? `${px - tooltip.offsetWidth - 12}px` : `${px + 12}px`;
  tooltip.style.top = "12px";
  drawOverlay();
}

// ------------------------------------------------------------------ batch

async function runBatch() {
  const button = $("#simulateBtn");
  button.disabled = true;
  button.textContent = "Running batch…";
  // Clear the previous run the moment a new one starts — stale results under
  // a multi-minute batch look exactly like a finished page.
  batchData = null;
  showResults();
  try {
    const payload = {
      game: gameType,
      players: Number($("#players").value),
      decks: Number($("#decks").value),
      games: Number($("#games").value),
      seed: parseSeed($("#seed").value) ?? "",
    };
    if (gameType === "blackjack") {
      payload.rounds = Number($("#rounds").value);
      payload.strategies = selectedStrategies();
    } else {
      payload.max_rounds = roundCap();
    }
    const work = gameType === "blackjack" ? payload.games * payload.rounds : payload.games;
    const big = gameType === "blackjack" ? work >= 2_000_000 : payload.games >= 2000;
    loadingAbort = new AbortController();
    showLoading(
      `Running ${fmt.format(payload.games)} ${gameType} ${payload.games === 1 ? "game" : "games"}…`,
      big ? "Large batch — the server simulates every game, so this can take minutes." : "");
    // The stream route sends live progress; the buffered route stays as a
    // fallback for anything without ReadableStream response bodies.
    const streaming = typeof ReadableStream === "function";
    const response = await fetch(streaming ? "/api/batch/stream" : "/api/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: loadingAbort.signal,
    });
    let data;
    if (streaming && response.ok && response.body) {
      const unit = gameType === "blackjack" ? "sessions" : "games";
      data = await readBatchStream(response,
        (done, total) => updateLoadingProgress(done, total, unit));
    } else {
      data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    }
    batchData = data;
    renderBatch();
  } catch (error) {
    showError(error.name === "AbortError"
      ? "Batch canceled. (The server may keep crunching the old request for a while.)"
      : error.message);
  } finally {
    hideLoading();
    button.disabled = false;
    button.textContent = mode === "batch" ? "Run batch" : "Simulate";
  }
}

function tileHtml([label, value, exact]) {
  return `<div class="tile"><div class="label">${label}</div><div class="value" title="${exact ?? value}">${value}</div></div>`;
}

// A value that would clip steps down a font size (twice if needed) — the
// tester's "+124 / -1…" tiles were cut off at full size with room below.
function fitTiles(container) {
  for (const value of container.querySelectorAll(".tile .value")) {
    value.classList.remove("fit-small", "fit-tiny");
    if (value.scrollWidth > value.clientWidth) value.classList.add("fit-small");
    if (value.scrollWidth > value.clientWidth) {
      value.classList.replace("fit-small", "fit-tiny");
    }
  }
}

function signed(n) {
  return `${n >= 0 ? "+" : ""}${fmt.format(Math.round(n * 10) / 10)}`;
}

let batchNoteText = null;

function renderBatch() {
  showResults();
  if (batchData.game === "blackjack") {
    batchNoteText = null;
    $("#batchNote").hidden = true;
    renderBlackjackBatch();
    return;
  }
  const { config, aggregate: agg, elapsed } = batchData;
  $("#evSection").hidden = true;
  $("#seatSection").hidden = false;
  const unfinished = agg.unfinished || 0;
  batchNoteText = unfinished > 0
    ? `⚠ ${fmt.format(unfinished)} of ${fmt.format(agg.games)} games hit the ` +
      `${fmt.format(config.max_rounds)}-round cap and were stopped unfinished. ` +
      `They're excluded from the distribution and wars-per-game statistics below ` +
      `(which are therefore biased toward shorter games) but still listed under ` +
      `outliers. Raise "Max rounds" to let them finish.`
    : null;
  $("#batchNote").textContent = batchNoteText || "";
  $("#batchNote").hidden = !batchNoteText;
  $("#histTitle").textContent = unfinished > 0
    ? "Game length distribution (completed games only)"
    : "Game length distribution";
  $("#outlierHead").innerHTML =
    "<tr><th></th><th>Seed</th><th>Rounds</th><th>Wars</th><th>Deepest</th><th>Biggest pot</th><th>Winner</th><th></th></tr>";
  const r = agg.rounds;
  const tiles = [
    ["Games", agg.completed === agg.games ? fmtNum(agg.games) : `${fmtNum(agg.completed)}/${fmtNum(agg.games)}`,
     agg.completed === agg.games ? fmt.format(agg.games) : `${fmt.format(agg.completed)}/${fmt.format(agg.games)}`],
    ["Mean rounds", `${fmtNum(r.mean)} ±${fmtNum(r.stdev)}`,
     `${fmt.format(Math.round(r.mean))} ±${fmt.format(Math.round(r.stdev))}`],
    ["Median rounds", fmtNum(r.median), fmt.format(Math.round(r.median))],
    ["Range", `${fmtNum(r.min)}–${fmtNum(r.max)}`, `${fmt.format(r.min)}–${fmt.format(r.max)}`],
    ["Wars / game", fmtNum(agg.mean_wars), fmt.format(Math.round(agg.mean_wars))],
    ["Deepest war", `×${agg.deepest_war}`],
    ["Biggest pot", `${fmtNum(agg.biggest_pot)} cards`, `${fmt.format(agg.biggest_pot)} cards`],
    [`Games / sec (${elapsed.toFixed(1)}s total)`, `${compact(Math.round(agg.games / elapsed))}/s`],
    ["Base seed", String(config.base_seed)],
  ];
  $("#batchStats").innerHTML = tiles.map(tileHtml).join("");
  fitTiles($("#batchStats"));
  const finished = batchData.games.filter((g) => g.completed);
  histValues = (finished.length ? finished : batchData.games).map((g) => g.rounds);
  drawHistogram();
  drawSeatChart();
  renderOutliers();
}

function renderBlackjackBatch() {
  const { config, aggregate: agg, elapsed } = batchData;
  $("#evSection").hidden = false;
  $("#seatSection").hidden = true;
  $("#histTitle").textContent = "Session net distribution (units)";
  $("#outlierHead").innerHTML =
    "<tr><th></th><th>Seed</th><th>Session net</th><th>Best seat</th><th>Worst seat</th><th></th></tr>";
  const s = agg.session_net;
  const tiles = [
    ["Sessions", fmtNum(agg.games), fmt.format(agg.games)],
    ["Hands", fmtNum(agg.hands), fmt.format(agg.hands)],
    ["Overall EV", `${(agg.ev * 100).toFixed(2)}%`],
    ["Net units", `${signed(agg.net)}u`],
    ["Session net (mean ± spread)", `${signed(s.mean)} ±${fmt.format(Math.round(s.stdev))}u`],
    ["Best / worst session", `${signed(s.max)} / ${signed(s.min)}u`],
    [`Hands / sec (${elapsed.toFixed(1)}s total)`, `${compact(Math.round(agg.hands / elapsed))}/s`],
    ["Base seed", String(config.base_seed)],
  ];
  $("#batchStats").innerHTML = tiles.map(tileHtml).join("");
  fitTiles($("#batchStats"));
  drawEVChart();
  histValues = batchData.games.map((g) => g.net);
  drawHistogram();
  renderBlackjackOutliers();
}

let evEntries = null;

function drawEVChart() {
  const [ctx, width, height] = setupCanvas($("#evChart"));
  evEntries = Object.entries(batchData.aggregate.per_strategy)
    .sort((a, b) => b[1].ev - a[1].ev);
  const evs = evEntries.map(([, entry]) => entry.ev);
  const pad = { left: 56, right: 12, top: 16, bottom: 24 };
  const yMax = Math.max(0.002, ...evs.map((v) => v * 1.25));
  const yMin = Math.min(-0.002, ...evs.map((v) => v * 1.25));
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const y = (v) => pad.top + (1 - (v - yMin) / (yMax - yMin)) * plotH;

  ctx.clearRect(0, 0, width, height);
  ctx.font = "11px system-ui, sans-serif";
  ctx.strokeStyle = "#2c2c2a";
  ctx.fillStyle = "#898781";
  ctx.lineWidth = 1;
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (const v of valueTicks(yMin * 100, yMax * 100, 4)) {
    ctx.beginPath();
    ctx.moveTo(pad.left, y(v / 100));
    ctx.lineTo(width - pad.right, y(v / 100));
    ctx.stroke();
    ctx.fillText(`${v.toFixed(1)}%`, pad.left - 6, y(v / 100));
  }
  ctx.strokeStyle = "#c3c2b7";  // break-even baseline
  ctx.beginPath();
  ctx.moveTo(pad.left, y(0));
  ctx.lineTo(width - pad.right, y(0));
  ctx.stroke();

  const slot = plotW / evEntries.length;
  const barW = Math.min(90, slot * 0.55);
  evEntries.forEach(([name, entry], i) => {
    const x0 = pad.left + i * slot + (slot - barW) / 2;
    const top = Math.min(y(0), y(entry.ev));
    const h = Math.max(1, Math.abs(y(entry.ev) - y(0)));
    ctx.fillStyle = "#3987e5";
    ctx.beginPath();
    ctx.roundRect(x0, top, barW, h, entry.ev >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4]);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = entry.ev >= 0 ? "bottom" : "top";
    ctx.fillText(`${(entry.ev * 100).toFixed(2)}%`, x0 + barW / 2,
                 entry.ev >= 0 ? top - 3 : top + h + 3);
    ctx.fillStyle = "#898781";
    ctx.textBaseline = "alphabetic";
    ctx.fillText(STRATEGY_LABELS[name] || name, x0 + barW / 2, height - 7);
  });
}

function renderBlackjackOutliers() {
  const { best, worst } = batchData.aggregate;
  const row = (session, type) => `
    <tr>
      <td class="otype">${type}</td>
      <td>${session.seed}</td>
      <td>${signed(session.net)}u</td>
      <td>${signed(session.best_seat)}u</td>
      <td>${signed(session.worst_seat)}u</td>
      <td><button class="btn" data-replay="${session.seed}">Replay</button></td>
    </tr>`;
  $("#outlierRows").innerHTML =
    best.map((g) => row(g, "best")).join("") +
    worst.map((g) => row(g, "worst")).join("");
}

function valueTicks(min, max, count) {
  const span = Math.max(max - min, 1);
  const step = Math.pow(10, Math.floor(Math.log10(span / count)));
  const nice = [1, 2, 2.5, 5, 10].map((m) => m * step).find((s) => span / s <= count) || step * 10;
  const ticks = [];
  for (let v = Math.ceil(min / nice) * nice; v <= max; v += nice) ticks.push(v);
  return ticks;
}

function drawBarAxes(ctx, width, height, pad, yMax) {
  ctx.font = "11px system-ui, sans-serif";
  ctx.strokeStyle = "#2c2c2a";
  ctx.fillStyle = "#898781";
  ctx.lineWidth = 1;
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  const y = (v) => pad.top + (1 - v / yMax) * (height - pad.top - pad.bottom);
  for (const v of valueTicks(0, yMax, 4)) {
    ctx.beginPath();
    ctx.moveTo(pad.left, y(v));
    ctx.lineTo(width - pad.right, y(v));
    ctx.stroke();
    ctx.fillText(compact(v), pad.left - 6, y(v));
  }
  return y;
}

function histogramBins(values, maxBins = 40) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return [{ lo: min, hi: max + 1, count: values.length }];
  const n = Math.min(maxBins, Math.max(8, Math.ceil(Math.sqrt(values.length))));
  const width = (max - min) / n;
  const bins = Array.from({ length: n }, (_, i) => ({ lo: min + i * width, hi: min + (i + 1) * width, count: 0 }));
  for (const v of values) bins[Math.min(n - 1, Math.floor((v - min) / width))].count += 1;
  return bins;
}

let histBins = null;
let histValues = null;

function drawHistogram() {
  const [ctx, width, height] = setupCanvas($("#hist"));
  const values = histValues;
  histBins = histogramBins(values);
  const pad = { left: 44, right: 12, top: 8, bottom: 22 };
  const yMax = Math.max(...histBins.map((b) => b.count));
  const y = drawBarAxes(ctx, width, height, pad, yMax);
  const plotW = width - pad.left - pad.right;
  const barW = plotW / histBins.length;
  const gap = barW > 5 ? 2 : barW > 2 ? 1 : 0;

  ctx.fillStyle = "#3987e5";
  for (let i = 0; i < histBins.length; i++) {
    const h = ((height - pad.top - pad.bottom) * histBins[i].count) / yMax;
    if (h === 0) continue;
    const x0 = pad.left + i * barW + gap / 2;
    ctx.beginPath();
    ctx.roundRect(x0, y(histBins[i].count), barW - gap, h, [Math.min(4, barW / 2), Math.min(4, barW / 2), 0, 0]);
    ctx.fill();
  }
  // x-axis: round values across the bin range
  ctx.fillStyle = "#898781";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const lo = histBins[0].lo;
  const hi = histBins[histBins.length - 1].hi;
  for (const v of valueTicks(lo, hi, 6)) {
    const px = pad.left + ((v - lo) / (hi - lo)) * plotW;
    ctx.fillText(compact(Math.round(v)), px, height - pad.bottom + 6);
  }
}

function drawSeatChart() {
  const [ctx, width, height] = setupCanvas($("#seatChart"));
  const seats = batchData.config.players;
  const wins = Array.from({ length: seats }, (_, i) => batchData.aggregate.wins_by_seat[i + 1] || 0);
  const expected = batchData.aggregate.completed / seats;
  const pad = { left: 44, right: 12, top: 8, bottom: 22 };
  const yMax = Math.max(Math.max(...wins), expected) * 1.1;
  const y = drawBarAxes(ctx, width, height, pad, yMax);
  const plotW = width - pad.left - pad.right;
  const barW = plotW / seats;
  const gap = barW > 5 ? 2 : barW > 2 ? 1 : 0;

  ctx.fillStyle = "#3987e5";
  for (let i = 0; i < seats; i++) {
    if (wins[i] === 0) continue;
    const h = ((height - pad.top - pad.bottom) * wins[i]) / yMax;
    ctx.beginPath();
    ctx.roundRect(pad.left + i * barW + gap / 2, y(wins[i]), barW - gap, h, [Math.min(4, barW / 2), Math.min(4, barW / 2), 0, 0]);
    ctx.fill();
  }
  // expected-wins reference line
  ctx.strokeStyle = "#898781";
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(pad.left, y(expected));
  ctx.lineTo(width - pad.right, y(expected));
  ctx.stroke();
  ctx.setLineDash([]);
  // x-axis: seat numbers, thinned when crowded
  ctx.fillStyle = "#898781";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const every = Math.ceil(seats / 15);
  for (let i = 0; i < seats; i += every) {
    ctx.fillText(String(i + 1), pad.left + (i + 0.5) * barW, height - pad.bottom + 6);
  }
}

function barHover(event, wrap, tip, barCount, padLeft, padRight, content) {
  const rect = wrap.getBoundingClientRect();
  const px = event.clientX - rect.left;
  const plotW = rect.width - padLeft - padRight;
  const index = Math.floor(((px - padLeft) / plotW) * barCount);
  if (index < 0 || index >= barCount) { tip.hidden = true; return; }
  tip.innerHTML = content(index);
  tip.hidden = false;
  const flip = px > rect.width - 180;
  tip.style.left = flip ? `${px - tip.offsetWidth - 12}px` : `${px + 12}px`;
}

function renderOutliers() {
  const { shortest, longest } = batchData.aggregate;
  const row = (game, type) => `
    <tr>
      <td class="otype">${type}</td>
      <td>${game.seed}</td>
      <td title="${fmt.format(game.rounds)}">${fmtNum(game.rounds)}</td>
      <td title="${fmt.format(game.wars)}">${fmtNum(game.wars)}</td>
      <td>×${game.deepest_war}</td>
      <td>${game.biggest_pot}</td>
      <td>${game.completed ? `Seat ${game.winner}` : `<span class="otype">unfinished (hit cap)</span>`}</td>
      <td><button class="btn" data-replay="${game.seed}">Replay</button></td>
    </tr>`;
  $("#outlierRows").innerHTML =
    shortest.map((g) => row(g, "shortest")).join("") +
    longest.map((g) => row(g, "longest")).join("");
}

function replaySeed(seed) {
  $("#seed").value = seed;
  const nameModeBefore = $("#nameMode").value;
  $("#nameMode").value = "default";  // batch reports seats, not names — match it
  setMode("single");
  // A seed names a different game in each engine's namespace (v1 = Python
  // MT19937, v2 = Rust xoshiro), so the replay has to use the engine the
  // batch ran on or it won't be the game the table promised.
  urlEngine = batchData && batchData.engine === "v2" ? "v2" : "v1";
  setRoundCap(batchData ? batchData.config.max_rounds : 0);
  $("#setup").requestSubmit();
  $("#nameMode").value = nameModeBefore;  // payload is read synchronously above
}

// -------------------------------------------------------------- wire-up

$("#setup").addEventListener("submit", simulate);
$("#importBtn").addEventListener("click", () => $("#importFile").click());
$("#importFile").addEventListener("change", (e) => {
  if (e.target.files[0]) importRecording(e.target.files[0]);
  e.target.value = "";
});

$("#playBtn").addEventListener("click", togglePlay);
$("#skipBtn").addEventListener("click", () => {
  pause();
  revealResults();
  seek(state.rounds);
});
$("#reelBtn").addEventListener("click", playReel);
$("#highlights").addEventListener("click", (event) => {
  const chip = event.target.closest("button[data-hl]");
  if (!chip) return;
  pause();
  seek(state.highlights[Number(chip.dataset.hl)].round);
});
$("#loadingCancel").addEventListener("click", () => {
  if (loadingAbort) loadingAbort.abort();
});

$("#chartTopChk").addEventListener("change", (event) => {
  layoutPrefs.chartFirst = event.target.checked;
  saveLayoutPrefs();
  applyLayoutPrefs();
});
// The options popovers close on any click outside them.
document.addEventListener("click", (event) => {
  for (const box of document.querySelectorAll("details.opt-box[open]")) {
    if (!box.contains(event.target)) box.open = false;
  }
});
$("#collapseBtn").addEventListener("click", () => {
  layoutPrefs.tableCollapsed = !tableCollapsed();
  saveLayoutPrefs();
  applyLayoutPrefs();
});
$("#highlightN").addEventListener("change", (event) => {
  layoutPrefs.highlightN = Number(event.target.value);
  saveLayoutPrefs();
  if (state) { state.hl = null; renderLegend(); drawChart(); }
});
$("#slowOpening").addEventListener("change", (event) => {
  layoutPrefs.slowOpening = event.target.checked;
  saveLayoutPrefs();
  if (state) { state.plans = null; updateSpeedLabels(); }
});
$("#capRounds").addEventListener("change", (event) => {
  $("#maxRounds").disabled = !event.target.checked;
  updateEstimateLine();
});
$("#maxRounds").addEventListener("input", updateEstimateLine);
$("#players").addEventListener("input", updateEstimateLine);
$("#decks").addEventListener("input", updateEstimateLine);
$("#elimDisplay").addEventListener("change", (event) => {
  layoutPrefs.elimDisplay = event.target.value;
  saveLayoutPrefs();
  if (state && state.mode === "full" && state.game === "war" && current >= 0) render(current);
});
applyLayoutPrefs();
$("#toStart").addEventListener("click", () => { pause(); seek(0); });
$("#toEnd").addEventListener("click", () => { pause(); seek(state.rounds); });
$("#stepBack").addEventListener("click", () => { pause(); seek(current - 1); });
$("#stepFwd").addEventListener("click", () => { pause(); seek(current + 1); });
$("#scrubber").addEventListener("input", (e) => seek(Number(e.target.value)));

$("#overlay").addEventListener("mousemove", handleChartHover);
$("#overlay").addEventListener("mouseleave", () => {
  hoverX = null;
  $("#tooltip").hidden = true;
  drawOverlay();
});
$("#overlay").addEventListener("click", (event) => {
  if (!state || state.mode !== "full" || !chartScale) return;
  const rect = $("#overlay").getBoundingClientRect();
  seek(chartRoundAt(event.clientX - rect.left));
});

document.addEventListener("keydown", (event) => {
  if (!state || state.mode !== "full") return;
  if (["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName)) return;
  if (event.code === "Space") { event.preventDefault(); togglePlay(); }
  if (event.code === "ArrowRight") { pause(); seek(current + 1); }
  if (event.code === "ArrowLeft") { pause(); seek(current - 1); }
});

$("#modeToggle").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-mode]");
  if (button) setMode(button.dataset.mode);
});

$("#outlierRows").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-replay]");
  if (button) replaySeed(Number(button.dataset.replay));
});

$("#histWrap").addEventListener("mousemove", (event) => {
  if (!batchData || !histBins) return;
  const blackjack = batchData.game === "blackjack";
  barHover(event, $("#histWrap"), $("#histTip"), histBins.length, 44, 12, (i) => {
    const bin = histBins[i];
    const pct = ((100 * bin.count) / batchData.aggregate.games).toFixed(1);
    return `<div class="t-label">${fmtNum(bin.lo)}–${fmtNum(bin.hi)} ${blackjack ? "units" : "rounds"}</div>` +
           `<div><span class="t-val">${fmt.format(bin.count)}</span> ${blackjack ? "sessions" : "games"} (${pct}%)</div>`;
  });
});
$("#histWrap").addEventListener("mouseleave", () => { $("#histTip").hidden = true; });

$("#seatWrap").addEventListener("mousemove", (event) => {
  if (!batchData) return;
  const seats = batchData.config.players;
  barHover(event, $("#seatWrap"), $("#seatTip"), seats, 44, 12, (i) => {
    const wins = batchData.aggregate.wins_by_seat[i + 1] || 0;
    const pct = ((100 * wins) / Math.max(batchData.aggregate.completed, 1)).toFixed(1);
    return `<div class="t-label">Seat ${i + 1}</div>` +
           `<div><span class="t-val">${fmt.format(wins)}</span> wins (${pct}%)</div>`;
  });
});
$("#seatWrap").addEventListener("mouseleave", () => { $("#seatTip").hidden = true; });

$("#evWrap").addEventListener("mousemove", (event) => {
  if (!batchData || batchData.game !== "blackjack" || !evEntries) return;
  barHover(event, $("#evWrap"), $("#evTip"), evEntries.length, 56, 12, (i) => {
    const [name, entry] = evEntries[i];
    return `<div class="t-label">${STRATEGY_LABELS[name] || name}</div>` +
           `<div>EV <span class="t-val">${(entry.ev * 100).toFixed(2)}%</span> per hand</div>` +
           `<div><span class="t-val">${fmt.format(entry.hands)}</span> hands · net <span class="t-val">${signed(entry.net)}u</span></div>`;
  });
});
$("#evWrap").addEventListener("mouseleave", () => { $("#evTip").hidden = true; });

$("#gameSel").addEventListener("change", (event) => setGameType(event.target.value));

window.addEventListener("resize", () => {
  if (mode === "single" && state) drawChart();
  if (mode === "batch" && batchData) {
    drawHistogram();
    if (batchData.game === "blackjack") drawEVChart();
    else drawSeatChart();
  }
});

// Strategy picker chips (blackjack).
(function initStrategyChips() {
  const wrap = $("#stratChips");
  for (const [name, label] of STRATEGY_META) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.dataset.name = name;
    chip.textContent = label;
    if (name === "basic" || name === "hit-below-17") chip.classList.add("on");
    chip.addEventListener("click", () => {
      if (chip.classList.contains("on") && selectedStrategies().length === 1) return;
      chip.classList.toggle("on");
    });
    wrap.appendChild(chip);
  }
})();

// URL parameters: prefill the form, optionally auto-run and jump to a round.
// e.g. /?players=6&decks=3&seed=1&names=random&run=1&round=42
//      /?engine=v2&players=6&decks=3&seed=1&run=1   (client-side wasm engine)
//      /?mode=batch&players=4&decks=1&games=1000&seed=0&run=1
//      /?game=blackjack&players=4&rounds=100&strategies=basic,hit-below-17&run=1
//
// `engine` is the only new key. Absent means v1, so every share URL written
// before v2 existed still replays through the Python server exactly as it
// did; `engine=v2` re-simulates in the browser instead.
let historyNav = false;  // the next run came from Back/Forward, not a click

function applyUrlParams(params) {
  if (params.has("engine")) urlEngine = params.get("engine") === "v2" ? "v2" : "v1";
  setGameType(params.get("game") === "blackjack" ? "blackjack" : "war");
  setMode(params.get("mode") === "batch" ? "batch" : "single");
  if (params.has("players")) $("#players").value = params.get("players");
  if (params.has("decks")) $("#decks").value = params.get("decks");
  if (params.has("rounds")) $("#rounds").value = params.get("rounds");
  if (params.has("games")) $("#games").value = params.get("games");
  // max_rounds=0 is "no cap". A run link from before caps were optional has
  // no max_rounds at all and meant the old 1M default; keep it so the link
  // replays the game it promised.
  if (params.has("max_rounds")) setRoundCap(params.get("max_rounds"));
  else if (params.get("run") === "1" && !params.has("engine")) setRoundCap(1_000_000);
  if (params.has("seed")) $("#seed").value = params.get("seed");
  if (params.has("names")) $("#nameMode").value = params.get("names");
  if (params.has("strategies")) {
    const wanted = new Set(params.get("strategies").split(","));
    for (const chip of $("#stratChips").children) {
      chip.classList.toggle("on", wanted.has(chip.dataset.name));
    }
  }
  if (params.has("round")) pendingRound = Number(params.get("round"));
  if (params.get("run") === "1") {
    if (!params.has("engine")) urlEngine = "v1";
    $("#setup").requestSubmit();
    return true;
  }
  return false;
}

(function initFromUrl() {
  applyUrlParams(new URLSearchParams(location.search));
})();

// Back/Forward re-runs the game at that URL (v2 re-simulates in ~100 ms).
window.addEventListener("popstate", () => {
  historyNav = true;
  const params = new URLSearchParams(location.search);
  if (!applyUrlParams(params)) {
    // Back to the blank form: clear the table rather than stranding stale
    // results under an empty URL.
    pause();
    state = null;
    batchData = null;
    showResults();
    historyNav = false;
  }
});
