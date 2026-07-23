/* War Simulator — playback UI over engine recordings. No dependencies. */
"use strict";

const $ = (sel) => document.querySelector(sel);
const fmt = new Intl.NumberFormat("en-US");
const PALETTE = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"];
const FIELD = "rgba(137, 135, 129, 0.28)";
const CARD_BACK = "/cards/card_back_red.png";
const RANK_NAMES = { 11: "jack", 12: "queen", 13: "king", 14: "ace" };
const CHART_POINTS = 1200;

let state = null;      // prepared recording (see prepare())
let pendingRound = null; // round to jump to after load (from ?round= URL param)
let current = -1;      // round currently rendered
let pos = 0;           // playhead position (fractional rounds)
let playing = false;
let lastTs = 0;
let winsCache = { round: -1, wins: {} };
let chartScale = null; // set by drawChart()
let hoverX = null;

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
  el._timer = setTimeout(() => { el.hidden = true; }, 6000);
}

// ------------------------------------------------------------ data loading

async function simulate(event) {
  event.preventDefault();
  const button = $("#simulateBtn");
  button.disabled = true;
  button.textContent = "Simulating…";
  try {
    const response = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        players: Number($("#players").value),
        decks: Number($("#decks").value),
        names: $("#nameMode").value,
        seed: $("#seed").value.trim(),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    load(data);
  } catch (error) {
    showError(error.message);
  } finally {
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
        deepestWar = Math.max(deepestWar, e.depth);
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
        biggestPot = Math.max(biggestPot, e.cards_won);
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
    computedStats: { wars, deepest_war: deepestWar, biggest_pot: biggestPot },
  };
}

function downsampleCounts(countsSeries, totalRounds) {
  const samples = Math.min(totalRounds, CHART_POINTS);
  const sampleSet = new Set();
  for (let i = 0; i <= samples; i++) sampleSet.add(Math.round((i * totalRounds) / samples));
  const rounds = [...sampleSet].sort((a, b) => a - b);
  const series = {};
  for (const [pid, counts] of Object.entries(countsSeries)) {
    series[pid] = rounds.map((r) => (r < counts.length ? counts[r] : null));
  }
  return { rounds, series };
}

function prepare(data) {
  const s = {
    mode: data.mode,
    summary: data.summary,
    rounds: data.summary.rounds,
    standings: data.summary.standings,
    names: data.names || null,
    stats: data.stats || null,
  };
  if (data.mode === "full") {
    Object.assign(s, buildIndex(data.events, s.rounds));
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
  return s;
}

// -------------------------------------------------------------- rendering

function load(data) {
  pause();
  state = prepare(data);
  current = -1;
  pos = 0;
  winsCache = { round: -1, wins: {} };

  $("#welcome").hidden = true;
  $("#results").hidden = false;
  const full = state.mode === "full";
  $("#playback").hidden = !full;
  $("#table").hidden = !full;
  $("#elimSection").hidden = full;
  $("#condensedNote").hidden = full;
  $("#chartHint").hidden = !full;

  renderStats();
  renderLegend();
  drawChart();

  if (full) {
    $("#scrubber").max = state.rounds;
    $("#scrubber").value = 0;
    buildGrid();
    seek(pendingRound !== null ? pendingRound : 0);
    pendingRound = null;
  } else {
    $("#condensedNote").textContent =
      `This game ran ${fmt.format(state.rounds)} rounds — too long for card-by-card playback, ` +
      `so here's the aggregate view. (Full playback kicks in for games under ~40,000 rounds.)`;
    renderElimFeed();
    drawOverlay();
  }
}

function renderStats() {
  const { summary, stats } = state;
  const winnerName = summary.winner ? state.names[summary.winner] : "—";
  const tiles = [
    ["Winner", summary.completed ? winnerName : "unfinished"],
    ["Rounds", fmt.format(summary.rounds)],
    ["Wars", fmt.format(stats.wars)],
    ["Deepest war", stats.deepest_war ? `×${stats.deepest_war}` : "—"],
    ["Biggest pot", `${fmt.format(stats.biggest_pot)} cards`],
    ["Players / cards", `${summary.num_players} / ${fmt.format(stats.total_cards)}`],
    ["Seed", String(summary.seed)],
  ];
  $("#stats").innerHTML = tiles
    .map(([label, value]) => `<div class="tile"><div class="label">${label}</div><div class="value" title="${value}">${value}</div></div>`)
    .join("");
}

function buildGrid() {
  const grid = $("#grid");
  grid.innerHTML = "";
  for (const pid of Object.keys(state.names)) {
    const tile = document.createElement("div");
    tile.className = "player";
    tile.dataset.pid = pid;
    tile.innerHTML =
      `<div class="pname" title="${state.names[pid]}">${state.names[pid]}</div>` +
      `<img src="${CARD_BACK}" alt="">` +
      `<div class="pmeta"></div>`;
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
  $("#roundLabel").textContent = `Round ${fmt.format(round)} / ${fmt.format(state.rounds)}`;

  const roundData = round > 0 ? state.perRound[round] : null;
  const wins = winsAt(round);
  const warPlayers = roundData?.war ? new Set(roundData.war.players) : null;

  for (const tile of $("#grid").children) {
    const pid = Number(tile.dataset.pid);
    const outAt = state.elimRound[pid];
    const out = outAt !== undefined && outAt <= round;
    tile.classList.toggle("out", out);
    tile.classList.toggle("winner", roundData?.win?.winner === pid);
    tile.classList.toggle("war", !out && !!warPlayers?.has(pid));
    const img = tile.querySelector("img");
    const meta = tile.querySelector(".pmeta");
    if (out) {
      img.src = CARD_BACK;
      meta.textContent = `#${state.standings.indexOf(pid) + 1}`;
    } else {
      const face = roundData?.faces[pid];
      const next = face ? cardUrl(face) : CARD_BACK;
      if (img.getAttribute("src") !== next) img.src = next;
      const count = round === 0 ? state.initialCounts[pid] : roundData?.counts?.[pid] ?? 0;
      meta.textContent = `${fmt.format(count)} · ${wins[pid] || 0}W`;
    }
  }
  $("#banner").innerHTML = describeRound(roundData, round);
  drawOverlay();
}

function renderElimFeed() {
  const feed = $("#elimFeed");
  feed.innerHTML = state.eliminations
    .map(({ round, player }) => {
      const place = state.standings.indexOf(player) + 1;
      return `<li><span class="rnd">Round ${fmt.format(round)}</span> — ${state.names[player]} out (#${place})</li>`;
    })
    .join("");
}

// --------------------------------------------------------------- playback

function seek(round) {
  round = Math.max(0, Math.min(state.rounds, Math.round(round)));
  pos = round;
  if (round !== current) render(round);
}

function pause() {
  playing = false;
  const btn = $("#playBtn");
  if (btn) btn.textContent = "▶";
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
  const speed = Number($("#speedSel").value);
  let next = Math.min(pos + speed * dt, state.rounds);

  if ($("#pauseElim").checked) {
    const from = Math.floor(pos);
    const hit = state.elimSorted.find((e) => e.round > from && e.round <= Math.floor(next));
    if (hit && hit.round < state.rounds) {  // final elimination = game over, no need to pause
      pos = hit.round;
      render(hit.round);
      pause();
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

function topSeries() {
  return state.standings.slice(0, PALETTE.length).map((pid, i) => ({ pid, color: PALETTE[i] }));
}

function renderLegend() {
  const top = topSeries();
  const others = state.summary.num_players - top.length;
  let html = top
    .map(({ pid, color }) => `<span class="chip"><i style="background:${color}"></i>${state.names[pid]}</span>`)
    .join("");
  if (others > 0) html += `<span class="chip"><i style="background:${FIELD}"></i>Field (${others} other${others === 1 ? "" : "s"})</span>`;
  $("#legend").innerHTML = html;
}

function chartTicks(max, count) {
  const step = Math.pow(10, Math.floor(Math.log10(max / count)));
  const nice = [1, 2, 2.5, 5, 10].map((m) => m * step).find((s) => max / s <= count) || step * 10;
  const ticks = [];
  for (let v = 0; v <= max; v += nice) ticks.push(v);
  return ticks;
}

function compact(n) {
  if (n >= 1e6) return (n / 1e6).toFixed(n % 1e6 ? 1 : 0) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(n % 1e3 ? 1 : 0) + "k";
  return String(n);
}

function setupCanvas(canvas) {
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return [ctx, rect.width, rect.height];
}

function drawChart() {
  const [ctx, width, height] = setupCanvas($("#chart"));
  const { rounds: xs, series } = state.chartData;
  const xMax = Math.max(state.rounds, 1);
  const yMax = state.totalCards;
  const pad = { left: 46, right: 12, top: 8, bottom: 22 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const x = (r) => pad.left + (r / xMax) * plotW;
  const y = (v) => pad.top + (1 - v / yMax) * plotH;
  chartScale = { x, y, xs, xMax, yMax, pad, width, height };

  ctx.clearRect(0, 0, width, height);
  ctx.font = "11px system-ui, sans-serif";

  // gridlines + y labels
  ctx.strokeStyle = "#2c2c2a";
  ctx.fillStyle = "#898781";
  ctx.lineWidth = 1;
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (const v of chartTicks(yMax, 4)) {
    ctx.beginPath();
    ctx.moveTo(pad.left, y(v));
    ctx.lineTo(width - pad.right, y(v));
    ctx.stroke();
    ctx.fillText(compact(v), pad.left - 6, y(v));
  }
  // x labels
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (const r of chartTicks(xMax, 6)) {
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
  for (const pid of Object.keys(series)) {
    if (!topIds.has(pid)) drawSeries(pid, FIELD, 1);
  }
  for (let i = top.length - 1; i >= 0; i--) drawSeries(String(top[i].pid), top[i].color, 2);
  drawOverlay();
}

function drawOverlay() {
  if (!chartScale) return;
  const [ctx, width, height] = setupCanvas($("#overlay"));
  const { x, pad } = chartScale;
  ctx.clearRect(0, 0, width, height);
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
  const px = event.clientX - rect.left;
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
  const rows = topSeries()
    .map(({ pid, color }) => {
      const value = state.chartData.series[pid]?.[idx];
      const text = value == null ? "out" : fmt.format(value);
      return `<div><span class="dot" style="background:${color}"></span>${state.names[pid]}: <span class="t-val">${text}</span></div>`;
    })
    .join("");
  tooltip.innerHTML = `<div class="t-round">Round ${fmt.format(xs[idx])}</div>${rows}`;
  tooltip.hidden = false;
  const wrapRect = $("#chartWrap").getBoundingClientRect();
  const flip = px > wrapRect.width - 170;
  tooltip.style.left = flip ? `${px - tooltip.offsetWidth - 12}px` : `${px + 12}px`;
  tooltip.style.top = "12px";
  drawOverlay();
}

// -------------------------------------------------------------- wire-up

$("#setup").addEventListener("submit", simulate);
$("#importBtn").addEventListener("click", () => $("#importFile").click());
$("#importFile").addEventListener("change", (e) => {
  if (e.target.files[0]) importRecording(e.target.files[0]);
  e.target.value = "";
});

$("#playBtn").addEventListener("click", togglePlay);
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

window.addEventListener("resize", () => { if (state) drawChart(); });

// URL parameters: prefill the form, optionally auto-run and jump to a round.
// e.g. /?players=6&decks=3&seed=1&names=random&run=1&round=42
(function initFromUrl() {
  const params = new URLSearchParams(location.search);
  if (params.has("players")) $("#players").value = params.get("players");
  if (params.has("decks")) $("#decks").value = params.get("decks");
  if (params.has("seed")) $("#seed").value = params.get("seed");
  if (params.has("names")) $("#nameMode").value = params.get("names");
  if (params.has("round")) pendingRound = Number(params.get("round"));
  if (params.get("run") === "1") $("#setup").requestSubmit();
})();
