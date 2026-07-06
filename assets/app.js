/* Ataraxos showcase: a lazy, memory-light game archive.
 * The games section is a left rail of game rows plus a right pane that plays the
 * selected game's replay video. "Detailed Log" opens a per-move frame viewer
 * (the lightbox): only the current AVIF frame is loaded, plus a couple prefetched
 * neighbors, never the whole sequence at once. games.json loads up front. */

const OUTCOME_NAME = { W: "Win", L: "Loss", D: "Draw" };
const PLAY_MS = 280;        // auto-advance cadence when "play" is on
const PREFETCH = 2;         // frames to warm ahead (and 1 behind) on each step

const els = {
  stats: document.getElementById("stats"),
  grid: document.getElementById("grid"),
  empty: document.getElementById("empty"),
  filters: document.getElementById("filters"),
  gameView: document.getElementById("game-view"),
  gvVideo: document.getElementById("gv-video"),
  gvTitle: document.getElementById("gv-title"),
  gvMeta: document.getElementById("gv-meta"),
  detailBtn: document.getElementById("detail-btn"),
  lb: document.getElementById("lightbox"),
  lbFrame: document.getElementById("lb-frame"),
  lbTitle: document.getElementById("lb-title"),
  lbMeta: document.getElementById("lb-meta"),
  lbPrev: document.getElementById("lb-prev"),      // previous move
  lbNext: document.getElementById("lb-next"),      // next move
  lbGPrev: document.getElementById("lb-gprev"),    // previous game
  lbGNext: document.getElementById("lb-gnext"),    // next game
  lbPlay: document.getElementById("lb-play"),
  lbSlider: document.getElementById("lb-slider"),
  lbInfo: document.getElementById("lb-frameinfo"),
  lbAccent: document.getElementById("lb-accent"),
};

let DATA = null;
let filter = "all";
let visible = [];       // games currently shown (after filter), in order
let openIndex = -1;     // index into `visible` of the modal's open game
let selectedIndex = -1; // index into `visible` of the row shown in the right pane
let frameIdx = 0;       // index into the open game's `frames` array
let playTimer = null;

init();

async function init() {
  try {
    const res = await fetch("assets/games.json", { cache: "no-cache" });
    DATA = await res.json();
  } catch (e) {
    els.grid.innerHTML = `<li class="empty">Could not load games.json — run <code>python3 build.py</code> first.</li>`;
    return;
  }
  renderStats();
  renderGrid();
  wireFilters();
  wireGameView();
  wireLightbox();
}

function renderStats() {
  const r = DATA.record;
  // Effective win rate counts draws as half-wins — the metric the writeup emphasizes.
  const effPct = Math.round(((r.wins + 0.5 * r.draws) / r.total) * 100);
  const lab = (n, one, many) => (n === 1 ? one : many);
  const unit = (n, cls, label) =>
    `<span class="unit"><span class="s-num ${cls}">${n}</span><span class="s-lab">${label}</span></span>`;
  els.stats.innerHTML = `
    <div class="scoreline">
      <div class="score">
        ${unit(r.wins, "rec-w", lab(r.wins, "win", "wins"))}
        <span class="s-sep">–</span>
        ${unit(r.losses, "rec-l", lab(r.losses, "loss", "losses"))}
        <span class="s-sep">–</span>
        ${unit(r.draws, "rec-d", lab(r.draws, "draw", "draws"))}
      </div>
      <div class="wr">
        <span class="wr-num">${effPct}%</span>
        <span class="wr-lab">effective win rate</span>
      </div>
    </div>`;
}

function renderGrid() {
  // Keep the same game selected across a filter change if it survives the filter.
  const keepNum = visible[selectedIndex] ? visible[selectedIndex].num : null;
  visible = DATA.games.filter((g) => filter === "all" || g.outcome === filter);
  const has = visible.length > 0;
  els.empty.hidden = has;
  els.gameView.hidden = !has;

  els.grid.innerHTML = visible.map((g, i) => rowHTML(g, i)).join("");
  els.grid.querySelectorAll(".game-row").forEach((btn) => {
    btn.addEventListener("click", () => selectGame(Number(btn.dataset.index)));
  });

  if (has) {
    const keep = keepNum != null ? visible.findIndex((g) => g.num === keepNum) : -1;
    selectGame(keep < 0 ? 0 : keep);
  } else {
    selectedIndex = -1;
  }
}

function rowHTML(g, i) {
  const label = OUTCOME_NAME[g.outcome] || g.outcome;
  const moves = g.plies != null ? `${g.plies} moves` : "";
  return `
    <li>
      <button class="game-row ${g.outcome}" data-index="${i}" title="Game ${g.num} — ${label}">
        <span class="gr-name">Game ${g.num}</span>
        <span class="gr-moves">${moves}</span>
      </button>
    </li>`;
}

// Select a game: highlight its row and load its replay into the right pane.
function selectGame(i) {
  if (i < 0 || i >= visible.length) return;
  selectedIndex = i;
  els.grid.querySelectorAll(".game-row").forEach((b, j) => {
    const on = j === i;
    b.classList.toggle("is-selected", on);
    if (on) b.setAttribute("aria-current", "true");
    else b.removeAttribute("aria-current");
  });
  renderGameView();
}

function renderGameView() {
  const g = visible[selectedIndex];
  if (!g) return;
  const label = OUTCOME_NAME[g.outcome] || g.outcome;
  els.gvTitle.textContent = `Game ${g.num} — ${label}`;
  els.gvMeta.textContent = [g.date, g.plies != null ? `${g.plies} moves` : null].filter(Boolean).join(" · ");
  // No poster image: #t=0.1 makes the video preview its own first frame until the
  // viewer hits play (no autoplay); load() resets it on switch.
  els.gvVideo.pause();
  els.gvVideo.src = g.video ? g.video + "#t=0.1" : "";
  els.gvVideo.load();
}

// "Detailed Log" opens the per-move frame viewer for the currently selected game.
function wireGameView() {
  els.detailBtn.addEventListener("click", () => { if (selectedIndex >= 0) openAt(selectedIndex); });
}

function wireFilters() {
  els.filters.addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    filter = btn.dataset.filter;
    els.filters.querySelectorAll(".chip").forEach((c) => c.classList.toggle("is-active", c === btn));
    renderGrid();
  });
}

/* ---------- Lightbox: per-move frame viewer ---------- */
function wireLightbox() {
  els.lb.addEventListener("click", (e) => { if (e.target.dataset.close !== undefined) close(); });
  els.lbPrev.addEventListener("click", () => { pause(); stepFrame(-1); });
  els.lbNext.addEventListener("click", () => { pause(); stepFrame(1); });
  els.lbGPrev.addEventListener("click", () => stepGame(-1));
  els.lbGNext.addEventListener("click", () => stepGame(1));
  els.lbPlay.addEventListener("click", togglePlay);
  els.lbSlider.addEventListener("input", () => { pause(); showFrame(Number(els.lbSlider.value)); });

  document.addEventListener("keydown", (e) => {
    if (els.lb.hidden) return;
    switch (e.key) {
      case "Escape": close(); break;
      case "ArrowLeft": pause(); stepFrame(-1); break;
      case "ArrowRight": pause(); stepFrame(1); break;
      case "Home": pause(); showFrame(0); break;
      case "End": pause(); showFrame(frameCount() - 1); break;
      case "[": stepGame(-1); break;
      case "]": stepGame(1); break;
      case " ": e.preventDefault(); togglePlay(); break;
      default: return;
    }
  });
}

function game() { return visible[openIndex]; }
function frames() { return (game() && game().frames) || []; }
function frameCount() { return frames().length; }

function frameURL(g, moveNum) { return `${g.framesDir}/move${moveNum}.avif`; }

function openAt(i) {
  openIndex = i;
  els.gvVideo.pause();            // don't leave the inline replay playing behind the modal
  els.lb.hidden = false;
  document.body.style.overflow = "hidden";
  loadGame();
}

function loadGame() {
  const g = game();
  if (!g) return;
  pause();
  frameIdx = 0;
  els.lbTitle.textContent = `Game ${g.num} — ${OUTCOME_NAME[g.outcome] || g.outcome}`;
  els.lbMeta.textContent = [g.date, g.plies != null ? `${g.plies} moves` : null].filter(Boolean).join(" · ");
  els.lbAccent.className = "lb-accent " + g.outcome;   // top color bar: win/loss/draw
  els.lbGPrev.disabled = openIndex <= 0;
  els.lbGNext.disabled = openIndex >= visible.length - 1;

  const n = frameCount();
  const has = n > 0;
  els.lbSlider.max = has ? n - 1 : 0;
  els.lbSlider.disabled = !has;
  els.lbPlay.disabled = !has;
  if (has) {
    showFrame(0);
  } else {
    // No frames deployed (e.g. Nortrom/frames/ not present) — nothing to show.
    els.lbFrame.removeAttribute("src");
    els.lbInfo.textContent = "no frames";
  }
}

function showFrame(k) {
  const g = game();
  const n = frameCount();
  if (!g || n === 0) return;
  frameIdx = Math.max(0, Math.min(k, n - 1));
  els.lbFrame.src = frameURL(g, g.frames[frameIdx]);
  els.lbFrame.alt = `Game ${g.num}, move ${g.frames[frameIdx]}`;
  els.lbSlider.value = frameIdx;
  els.lbInfo.textContent = `t = ${g.frames[frameIdx]}`;   // current move number
  els.lbPrev.disabled = frameIdx <= 0;
  els.lbNext.disabled = frameIdx >= n - 1;
  prefetch(g);
}

// Warm the browser cache for nearby frames so stepping/playing feels instant.
function prefetch(g) {
  const n = frameCount();
  for (let d = -1; d <= PREFETCH; d++) {
    const j = frameIdx + d;
    if (d !== 0 && j >= 0 && j < n) new Image().src = frameURL(g, g.frames[j]);
  }
}

function stepFrame(delta) {
  const next = frameIdx + delta;
  if (next < 0 || next >= frameCount()) return;
  showFrame(next);
}

function stepGame(delta) {
  const next = openIndex + delta;
  if (next < 0 || next >= visible.length) return;
  openIndex = next;
  loadGame();
}

/* ----- playback ----- */
function togglePlay() { (playTimer ? pause : play)(); }

function play() {
  if (frameCount() < 2) return;
  if (frameIdx >= frameCount() - 1) showFrame(0); // restart from the top
  els.lbPlay.textContent = "⏸";
  playTimer = setInterval(() => {
    if (frameIdx >= frameCount() - 1) { pause(); return; }
    showFrame(frameIdx + 1);
  }, PLAY_MS);
}

function pause() {
  if (playTimer) clearInterval(playTimer);
  playTimer = null;
  els.lbPlay.textContent = "▶";
}

function close() {
  pause();
  els.lbFrame.removeAttribute("src");  // drop the current frame from memory
  els.lb.hidden = true;
  document.body.style.overflow = "";
  if (openIndex >= 0) selectGame(openIndex);  // right pane reflects the game the modal ended on
  openIndex = -1;
}
