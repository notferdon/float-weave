// FLOAT core — JS port of weave.py (solve / verify / metrics / render / exports).
// The solver mirrors the frozen kernel operation-for-operation; test_parity.py checks
// the port bit-for-bit against weave.solve on the same targets.
// Claim ceiling: float-legal at L by construction. Not a woven or weavable claim.
(function (root) {
  'use strict';

  class Infeasible extends Error {}

  // tgt: Float64Array (h*w, row-major, 0..1). Returns {D: Int8Array, forcedDropped}.
  function solve(tgt, h, w, L, diffuse = true) {
    const D = new Int8Array(h * w);
    const colval = new Int8Array(w).fill(-1);
    const colrun = new Int32Array(w);
    let err = new Float64Array(w);
    let forcedDropped = 0;
    const INF = 1e18;
    const t = new Float64Array(w);
    const forced = new Int8Array(w);
    const back = new Int16Array(w * 2 * (L + 1) * 2);   // [c][v][k][0|1]
    const bi = (c, v, k) => ((c * 2 + v) * (L + 1) + k) * 2;
    let cost = new Float64Array(2 * (L + 1));
    let nc = new Float64Array(2 * (L + 1));
    const ci = (v, k) => v * (L + 1) + k;
    const row = new Int8Array(w);

    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const x = tgt[r * w + c];
        t[c] = diffuse ? Math.min(Math.max(x + err[c], -0.5), 1.5) : x;
      }
      forced.fill(-1);
      for (let c = 0; c < w; c++) if (colrun[c] >= L) forced[c] = 1 - colval[c];
      for (let c = 0; c < w - L; c++) {
        const b0 = forced[c];
        if (b0 === -1) continue;
        let all = true;
        for (let j = 1; j <= L; j++) if (forced[c + j] !== b0) { all = false; break; }
        if (all) { forced[c + L] = -1; forcedDropped++; }
      }
      cost.fill(INF);
      for (let v = 0; v <= 1; v++) {
        if (forced[0] === -1 || forced[0] === v) { const q = t[0] - v; cost[ci(v, 1)] = q * q; }
      }
      for (let c = 1; c < w; c++) {
        nc.fill(INF);
        for (let v = 0; v <= 1; v++) {
          if (forced[c] !== -1 && forced[c] !== v) continue;
          const q = t[c] - v, d = q * q;
          for (let k = 1; k < L; k++) {
            const a = cost[ci(v, k)];
            if (a < INF && a + d < nc[ci(v, k + 1)]) {
              nc[ci(v, k + 1)] = a + d;
              const p = bi(c, v, k + 1); back[p] = v; back[p + 1] = k;
            }
          }
          const o = 1 - v;
          let kb = 1, best = cost[ci(o, 1)];
          for (let k = 2; k <= L; k++) if (cost[ci(o, k)] < best) { best = cost[ci(o, k)]; kb = k; }
          if (best < INF && best + d < nc[ci(v, 1)]) {
            nc[ci(v, 1)] = best + d;
            const p = bi(c, v, 1); back[p] = o; back[p + 1] = kb;
          }
        }
        const tmp = cost; cost = nc; nc = tmp;
      }
      let fv = 0, fk = 0, m = Infinity;
      for (let v = 0; v <= 1; v++) for (let k = 0; k <= L; k++) if (cost[ci(v, k)] < m) { m = cost[ci(v, k)]; fv = v; fk = k; }
      if (m >= INF) throw new Infeasible(`row ${r} infeasible at L=${L}`);
      let v = fv, k = fk;
      for (let c = w - 1; c >= 0; c--) {
        row[c] = v;
        if (c) { const p = bi(c, v, k); const nv = back[p], nk = back[p + 1]; v = nv; k = nk; }
      }
      for (let c = 0; c < w; c++) {
        D[r * w + c] = row[c];
        colrun[c] = row[c] === colval[c] ? colrun[c] + 1 : 1;
        colval[c] = row[c];
      }
      if (diffuse) {
        const e = new Float64Array(w);
        for (let c = 0; c < w; c++) e[c] = t[c] - row[c];
        const ne = new Float64Array(w);
        for (let c = 0; c < w - 1; c++) ne[c] += 0.3125 * e[c + 1];
        for (let c = 0; c < w; c++) ne[c] += 0.3125 * e[c];
        for (let c = 1; c < w; c++) ne[c] += 0.125 * e[c - 1];
        err = ne;
      }
    }
    return { D, forcedDropped };
  }

  // Independent re-measurement (does not trust the solver).
  function maxrun(D, h, w, axis) {
    let m = 0;
    const lines = axis === 0 ? h : w, len = axis === 0 ? w : h;
    for (let a = 0; a < lines; a++) {
      let k = 1, prev = axis === 0 ? D[a * w] : D[a];
      m = Math.max(m, 1);
      for (let i = 1; i < len; i++) {
        const cur = axis === 0 ? D[a * w + i] : D[i * w + a];
        k = cur === prev ? k + 1 : 1; prev = cur;
        if (k > m) m = k;
      }
    }
    return m;
  }

  function box(a, n, f) {
    const m = Math.floor(n / f), out = new Float64Array(m * m);
    for (let i = 0; i < m; i++) for (let j = 0; j < m; j++) {
      let s = 0;
      for (let y = 0; y < f; y++) for (let x = 0; x < f; x++) s += a[(i * f + y) * n + j * f + x];
      out[i * m + j] = s / (f * f);
    }
    return out;
  }

  function pearson(a, b) {
    const n = a.length; let ma = 0, mb = 0;
    for (let i = 0; i < n; i++) { ma += a[i]; mb += b[i]; }
    ma /= n; mb /= n;
    let sab = 0, saa = 0, sbb = 0;
    for (let i = 0; i < n; i++) { const x = a[i] - ma, y = b[i] - mb; sab += x * y; saa += x * x; sbb += y * y; }
    return saa > 1e-24 && sbb > 1e-24 ? sab / Math.sqrt(saa * sbb) : null;
  }

  function metrics(D, tgt, n) {
    const d = Float64Array.from(D);
    let se = 0, ink = 0;
    for (let i = 0; i < d.length; i++) { const q = d[i] - tgt[i]; se += q * q; ink += d[i]; }
    const b1 = box(d, n, 4), b2 = box(tgt, n, 4);
    let s4 = 0; for (let i = 0; i < b1.length; i++) { const q = b1[i] - b2[i]; s4 += q * q; }
    return { maxrun_h: maxrun(D, n, n, 0), maxrun_v: maxrun(D, n, n, 1),
             rmse_1to1: Math.sqrt(se / d.length), rmse_blur4: Math.sqrt(s4 / b1.length),
             pearson_blur4: pearson(b1, b2), ink: ink / d.length };
  }

  // Solve + verify. Fails closed: status FAIL carries no structure to export.
  function run(tgt, n, L, solver = solve) {
    if (!(L >= 1)) return { status: 'FAIL', reasons: ['L must be >= 1'] };
    let res;
    try { res = solver(tgt, n, n, L); }
    catch (e) { if (e instanceof Infeasible) return { status: 'FAIL', reasons: [`infeasible: ${e.message}`] }; throw e; }
    const m = metrics(res.D, tgt, n);
    const reasons = [];
    if (m.maxrun_h > L) reasons.push(`maxrun_h ${m.maxrun_h} > L ${L}`);
    if (m.maxrun_v > L) reasons.push(`maxrun_v ${m.maxrun_v} > L ${L}`);
    if (res.forcedDropped) reasons.push(`forced_dropped ${res.forcedDropped}: a column constraint was relaxed, guarantee void`);
    if (reasons.length) return { status: 'FAIL', reasons, measured: m };
    return { status: 'OK', D: res.D, measured: m, forcedDropped: 0 };
  }

  // Honest interlacement, same drawing rule as weave.render (s=4 profile). Returns Uint8ClampedArray gray.
  function render(D, n, s = 4) {
    const W = n * s, out = new Uint8ClampedArray(W * W);
    const prof = s === 4 ? [0.72, 1.0, 1.0, 0.72]
      : Array.from({ length: s }, (_, i) => 0.72 + 0.28 * Math.sin(Math.PI * (i + 0.5) / s));
    for (let Y = 0; Y < W; Y++) for (let X = 0; X < W; X++) {
      const r = (Y / s) | 0, c = (X / s) | 0, ix = X % s, iy = Y % s;
      const up = D[r * n + c] === 1;
      let v = up ? 236 * prof[ix] : 34 + 34 * prof[iy];
      const nbV = D[((r - 1 + n) % n) * n + c] !== D[r * n + c];
      const nbH = D[r * n + (c - 1 + n) % n] !== D[r * n + c];
      if (up && nbV && iy === 0) v *= 0.80;
      if (!up && nbH && ix === 0) v *= 0.80;
      out[Y * W + X] = Math.max(0, Math.min(255, Math.trunc(v)));
    }
    return out;
  }

  // ---- exports (only ever called with an OK structure). Lift convention: 1 = warp up/lifted = white.
  function bmp1(D, n) {
    const rowBytes = Math.ceil(n / 32) * 4, img = rowBytes * n, off = 14 + 40 + 8, size = off + img;
    const b = new Uint8Array(size), dv = new DataView(b.buffer);
    b[0] = 0x42; b[1] = 0x4d; dv.setUint32(2, size, true); dv.setUint32(10, off, true);
    dv.setUint32(14, 40, true); dv.setInt32(18, n, true); dv.setInt32(22, n, true);
    dv.setUint16(26, 1, true); dv.setUint16(28, 1, true); dv.setUint32(34, img, true);
    dv.setUint32(46, 2, true);
    b.set([0, 0, 0, 0, 255, 255, 255, 0], 54);                    // palette: 0 black, 1 white
    for (let r = 0; r < n; r++) {                                   // BMP rows are bottom-up
      const base = off + (n - 1 - r) * rowBytes;
      for (let c = 0; c < n; c++) if (D[r * n + c]) b[base + (c >> 3)] |= 0x80 >> (c & 7);
    }
    return b;
  }

  function tif1(D, n) {
    const rowBytes = Math.ceil(n / 8), img = rowBytes * n, ifdOff = 8 + img, nTags = 9;
    const size = ifdOff + 2 + nTags * 12 + 4;
    const b = new Uint8Array(size), dv = new DataView(b.buffer);
    b.set([0x49, 0x49, 42, 0]); dv.setUint32(4, ifdOff, true);
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++)
      if (D[r * n + c]) b[8 + r * rowBytes + (c >> 3)] |= 0x80 >> (c & 7);
    dv.setUint16(ifdOff, nTags, true);
    const tags = [[256, 3, n], [257, 3, n], [258, 3, 1], [259, 3, 1], [262, 3, 1],   // BlackIsZero
                  [273, 4, 8], [277, 3, 1], [278, 3, n], [279, 4, img]];
    tags.forEach(([tag, type, val], i) => {
      const p = ifdOff + 2 + i * 12;
      dv.setUint16(p, tag, true); dv.setUint16(p + 2, type, true); dv.setUint32(p + 4, 1, true);
      if (type === 3) dv.setUint16(p + 8, val, true); else dv.setUint32(p + 8, val, true);
    });
    return b;
  }

  // WIF 1.1, straight-draw liftplan: warp end i (1-based) = lift-bitmap column i-1 (left->right)
  // on shaft i; pick j (1-based) = lift-bitmap row j-1 (top->bottom); a listed shaft is raised.
  function wif(D, n, L) {
    const lines = ['[WIF]', 'Version=1.1', 'Date=' + new Date().toISOString().slice(0, 10),
      'Developers=FLOAT wedge (private)', 'Source Program=FLOAT', 'Source Version=wedge',
      '', '[CONTENTS]', 'WEAVING=true', 'WARP=true', 'WEFT=true', 'THREADING=true', 'LIFTPLAN=true', 'TEXT=true',
      '', '[TEXT]', `Title=FLOAT L=${L} ${n}x${n}`,
      'Note1=float-legal at L by construction; not a woven or weavable claim',
      'Note2=warp end i = lift bitmap column i (left to right); pick j = lift bitmap row j (top to bottom)',
      '', '[WEAVING]', `Shafts=${n}`, 'Treadles=0', 'Rising Shed=true',
      '', '[WARP]', `Threads=${n}`, '', '[WEFT]', `Threads=${n}`, '', '[THREADING]'];
    for (let i = 1; i <= n; i++) lines.push(`${i}=${i}`);
    lines.push('', '[LIFTPLAN]');
    for (let r = 0; r < n; r++) {
      const up = [];
      for (let c = 0; c < n; c++) if (D[r * n + c]) up.push(c + 1);
      lines.push(`${r + 1}=${up.join(',')}`);
    }
    return lines.join('\r\n') + '\r\n';
  }

  const api = { solve, run, metrics, maxrun, render, bmp1, tif1, wif, Infeasible };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.FloatCore = api;
})(typeof self !== 'undefined' ? self : this);
