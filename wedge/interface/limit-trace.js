// Presentation only. Exact Limit trace geometry from the accepted renderer study.
(function (root) {
  'use strict';

  function runs(D, n, axis) {
    const out = [];
    for (let line = 0; line < n; line++) {
      let a = 0;
      const bit = (i) => axis === 'h' ? D[line * n + i] : D[i * n + line];
      for (let b = 1; b <= n; b++) if (b === n || bit(b) !== bit(a)) {
        out.push({ axis, line, a, b, k: b - a, value: bit(a) });
        a = b;
      }
    }
    return out;
  }

  function marks(D, n, L) {
    const out = [];
    const rect = (x, y, w, h) => out.push({ x, y, w, h });
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++)
      if (D[r * n + c] === 0) rect(c + .39, r + .39, .22, .22);
    for (const axis of ['h', 'v']) for (const q of runs(D, n, axis))
      if (q.value === 0 && q.k === L) {
        if (axis === 'h') rect(q.a + .1, q.line + .28, q.k - .2, .44);
        else rect(q.line + .28, q.a + .1, .44, q.k - .2);
      }
    return out;
  }

  function paint(ctx, items, n, { width = ctx.canvas.width, height = ctx.canvas.height,
    x = 0, y = 0, cells = n } = {}) {
    ctx.save();
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, width, height);
    ctx.scale(width / cells, width / cells); ctx.translate(-x, -y);
    ctx.fillStyle = '#000';
    for (const q of items) ctx.fillRect(q.x, q.y, q.w, q.h);
    ctx.restore();
  }

  function loupe(D, n, L) {
    // Same measured horizontal zero-run selection as the accepted study.
    const candidates = runs(D, n, 'h').filter(q => q.value === 0 && q.k === L && q.a > 0 && q.b < n);
    candidates.sort((a, b) =>
      Math.hypot(a.line - n * .43, (a.a + a.b) / 2 - n * .5) -
      Math.hypot(b.line - n * .43, (b.a + b.b) / 2 - n * .5));
    if (!candidates.length) return null;
    const hit = candidates[0];
    return { row: Math.max(0, Math.min(n - 12, hit.line - 6)),
      col: Math.max(0, Math.min(n - 12, Math.floor((hit.a + hit.b) / 2) - 6)), hit };
  }

  const api = { marks, paint, loupe };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.LimitTrace = api;
})(typeof self === 'undefined' ? this : self);
