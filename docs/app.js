// FLOAT wedge — presentation/UI boundary only.
// Consumes FloatCore (../float-core.js) as a library. Does not reimplement or alter the solver.
'use strict';

const $ = (id) => document.getElementById(id);
const cHero = $('c-hero'), cRef = $('c-ref'), cDrawdown = $('c-drawdown'), cLoupe = $('c-loupe');
const stateLine = $('state-line'), loupeWrap = $('loupe-wrap');
const inspectPanel = $('inspect-panel'), inspectDetail = $('inspect-detail'), inspectToggle = $('inspect-toggle');
const openImageBtn = $('open-image'), fileEl = $('file');
const lSetEl = $('l-set');

// The frozen specimen: same source used throughout the wedge (../float_proof.py's SRC), a fixed
// square crop into the diagonal ridge/sky boundary where flat regions produce long runs. This
// crop is presentation/input framing only — it does not change the solver or claim to represent
// the whole source image.
const SPECIMEN_SRC = 'assets/specimen-source.png';
const SPECIMEN_CROP = { x: 384, y: 0, size: 1792 }; // natural pixels, in the 5120x2880 source

const N = 104, SCALE = 4; // 104 threads * 4px = 416px hero
const REF_PX = 176;
const LOUPE_SCALE = 16;

let currentImage = null;   // raw <img>, either the bundled specimen or a user-opened file
let currentCrop = null;    // {x,y,size} in that image's natural pixels, or null = centered square
let currentTarget = null;  // Float64Array, N*N
let currentL = 3;

// ---------- image ingestion ----------

function loadSpecimen() {
  const img = new Image();
  img.onload = () => {
    currentImage = img;
    currentCrop = SPECIMEN_CROP;
    ingest();
  };
  img.src = SPECIMEN_SRC;
}

function loadImageFile(file) {
  const img = new Image();
  const url = URL.createObjectURL(file);
  img.onload = () => {
    currentImage = img;
    currentCrop = null; // user images: centered square, no presumed ridge framing
    ingest();
    URL.revokeObjectURL(url);
  };
  img.onerror = () => {
    // Keep the current plate; only report that the new file was not used.
    stateLine.className = 'state-line mono';
    stateLine.textContent = 'could not read image';
    URL.revokeObjectURL(url);
  };
  img.src = url;
}

function buildTarget(img, crop, n) {
  const s = crop ? crop.size : Math.min(img.naturalWidth, img.naturalHeight);
  const sx = crop ? crop.x : (img.naturalWidth - s) / 2;
  const sy = crop ? crop.y : (img.naturalHeight - s) / 2;

  const tmp = document.createElement('canvas');
  tmp.width = n; tmp.height = n;
  const ctx = tmp.getContext('2d');
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  // Composite onto white: transparent pixels would otherwise read as black.
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, n, n);
  ctx.drawImage(img, sx, sy, s, s, 0, 0, n, n);

  const px = ctx.getImageData(0, 0, n, n).data;
  const gray = new Float64Array(n * n);
  for (let i = 0, p = 0; i < n * n; i++, p += 4) {
    gray[i] = (0.299 * px[p] + 0.587 * px[p + 1] + 0.114 * px[p + 2]) / 255;
  }
  let lo = Infinity, hi = -Infinity;
  for (let i = 0; i < gray.length; i++) { if (gray[i] < lo) lo = gray[i]; if (gray[i] > hi) hi = gray[i]; }
  const span = (hi - lo) || 1;
  for (let i = 0; i < gray.length; i++) gray[i] = (gray[i] - lo) / span;
  return gray;
}

function ingest() {
  currentTarget = buildTarget(currentImage, currentCrop, N);
  drawRef();
  solveAndRender();
}

// ---------- rendering ----------

function drawGrayToCanvas(canvas, data, n) {
  canvas.width = n; canvas.height = n;
  const ctx = canvas.getContext('2d');
  const imgData = ctx.createImageData(n, n);
  for (let i = 0; i < n * n; i++) {
    const v = Math.max(0, Math.min(255, Math.round(data[i] * 255)));
    imgData.data[i * 4] = v; imgData.data[i * 4 + 1] = v; imgData.data[i * 4 + 2] = v; imgData.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(imgData, 0, 0);
}

function drawRef() {
  const refData = buildTarget(currentImage, currentCrop, REF_PX);
  drawGrayToCanvas(cRef, refData, REF_PX);
}

function drawDrawdown(D, n) {
  const flat = new Float64Array(n * n);
  for (let i = 0; i < n * n; i++) flat[i] = D[i] ? 1 : 0;
  drawGrayToCanvas(cDrawdown, flat, n);
}

// Cache drawing primitives only: resizing must never solve again or revive a refused result.
let currentMarks = null;

function drawHero(items, n, scale) {
  const W = Math.max(n * scale, Math.round(cHero.getBoundingClientRect().width * devicePixelRatio));
  cHero.width = W; cHero.height = W;
  LimitTrace.paint(cHero.getContext('2d'), items, n);
}

function drawLoupe(items, D, n, L) {
  const region = LimitTrace.loupe(D, n, L);
  if (!region) { loupeWrap.style.display = 'none'; return; }
  const s = LOUPE_SCALE, grid = 12 * s;
  cLoupe.width = grid; cLoupe.height = grid + 26;
  const ctx = cLoupe.getContext('2d');
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, grid, grid + 26);
  ctx.save(); ctx.beginPath(); ctx.rect(0, 0, grid, grid); ctx.clip();
  // Clip whole-field marks; a crop edge must not become a new run endpoint.
  LimitTrace.paint(ctx, items, n, { width: grid, height: grid,
    x: region.col, y: region.row, cells: 12 });
  ctx.restore();

  // Caliper spans the run's exact cell extent [x0, x1). Verticals sit on whole device pixels
  // (the run's first and last pixel columns), so every tick renders as one crisp hairline.
  const x0 = (region.hit.a - region.col) * s, x1 = (region.hit.b - region.col) * s;
  ctx.strokeStyle = '#000'; ctx.lineWidth = 1; ctx.beginPath();
  ctx.moveTo(x0 + 0.5, grid + 9); ctx.lineTo(x0 + 0.5, grid + 18);
  ctx.moveTo(x1 - 0.5, grid + 9); ctx.lineTo(x1 - 0.5, grid + 18);
  ctx.moveTo(x0, grid + 13.5); ctx.lineTo(x1, grid + 13.5);
  // One unit tick at every internal cell boundary: L cells read as L intervals.
  for (let k = 1; k < L; k++) {
    ctx.moveTo(x0 + k * s + 0.5, grid + 11); ctx.lineTo(x0 + k * s + 0.5, grid + 16);
  }
  ctx.stroke(); loupeWrap.style.display = '';
}

// ---------- solve ----------

function solveAndRender() {
  if (!currentTarget) return;
  const L = currentL;
  currentMarks = null;
  const res = FloatCore.run(currentTarget, N, L);

  if (res.status !== 'OK') {
    stateLine.className = 'state-line mono refused';
    stateLine.textContent = `L = ${L} · refused, fail-closed`;
    loupeWrap.style.display = 'none';
    const ctx = cDrawdown.getContext('2d'); ctx.clearRect(0, 0, cDrawdown.width, cDrawdown.height);
    const ctx2 = cHero.getContext('2d'); ctx2.clearRect(0, 0, cHero.width, cHero.height);
    return;
  }

  const m = res.measured;
  currentMarks = LimitTrace.marks(res.D, N, L);
  drawHero(currentMarks, N, SCALE);
  drawDrawdown(res.D, N);
  drawLoupe(currentMarks, res.D, N, L);

  stateLine.className = 'state-line mono';
  stateLine.textContent = `L = ${L} · max run ${m.maxrun_h}/${m.maxrun_v}`;

  inspectDetail.textContent =
    `maxrun_h ${m.maxrun_h}  maxrun_v ${m.maxrun_v}  forced_dropped ${res.forcedDropped}  ` +
    `structure ${N}×${N}`;
}

// ---------- wiring ----------

lSetEl.addEventListener('click', (e) => {
  const btn = e.target.closest('.l-opt');
  if (!btn) return;
  setL(parseInt(btn.dataset.l, 10));
});

document.addEventListener('keydown', (e) => {
  if (['1', '2', '3', '5', '8'].includes(e.key)) setL(parseInt(e.key, 10));
});

function setL(L) {
  if (L === currentL) return;
  currentL = L;
  [...lSetEl.children].forEach((b) => b.classList.toggle('active', parseInt(b.dataset.l, 10) === L));
  solveAndRender();
}

openImageBtn.addEventListener('click', () => fileEl.click());
fileEl.addEventListener('change', (e) => { if (e.target.files[0]) loadImageFile(e.target.files[0]); });
document.addEventListener('dragover', (e) => e.preventDefault());
document.addEventListener('drop', (e) => {
  e.preventDefault();
  const f = e.dataTransfer.files[0];
  if (f) loadImageFile(f);
});

inspectToggle.addEventListener('click', () => {
  inspectPanel.classList.toggle('open');
});

let resizeFrame;
new ResizeObserver(() => {
  cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(() => {
    if (currentMarks) drawHero(currentMarks, N, SCALE);
  });
}).observe(document.querySelector('.plate-wrap'));

loadSpecimen();
