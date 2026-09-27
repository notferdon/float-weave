#!/usr/bin/env python3
"""FLOAT wedge — image -> binary two-shed structure with max float <= L in BOTH directions.

Claim ceiling: float-legal at L by construction. Nothing here is a woven or weavable claim.

Solver kernel is copied from the frozen proof (../float_proof.py) unchanged in behaviour.
What is added here: hard verification, fail-closed on any unmet constraint, exports, receipt.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

import numpy as np
from PIL import Image

# ---------------------------------------------------------------- input

def load_target(src, n):
    """Grayscale, centre-cropped square, resized to n, contrast-stretched to full range."""
    if src.startswith('pattern:'):
        a = synth(src.split(':', 1)[1], n)
    else:
        im = Image.open(src).convert('L')
        w, h = im.size
        s = min(w, h)
        im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
        im = im.resize((n, n), Image.LANCZOS)
        a = np.asarray(im, dtype=np.float64) / 255.0
    lo, hi = a.min(), a.max()
    if hi - lo < 1e-9:
        raise SystemExit('FAIL: target has no tonal range')
    return (a - lo) / (hi - lo)


def synth(name, n):
    """Deterministic test patterns. Flat fields and hard edges are the worst case for a float bound."""
    y, x = np.mgrid[0:n, 0:n] / (n - 1.0)
    if name == 'rings':
        r = np.hypot(x - 0.5, y - 0.5)
        a = 0.5 + 0.5 * np.cos(r * 38)
        return a * (0.25 + 0.75 * (1 - y))          # rings under a vertical ramp
    if name == 'blocks':
        a = np.zeros((n, n))
        a[: n // 2, : n // 2] = 1.0                 # flat white quadrant: hardest case
        a[n // 2 :, n // 2 :] = 0.5
        a[: n // 2, n // 2 :] = x[: n // 2, n // 2 :]
        return a
    raise SystemExit(f'FAIL: unknown pattern {name!r} (have: rings, blocks)')

# ---------------------------------------------------------------- kernel (from frozen proof)

def solve(tgt, L, diffuse=True):
    """Row-exact DP (max run <= L along the row) with hard per-column forcing from the
    rows already placed (max run <= L down the column). Error diffused row->row."""
    h, w = tgt.shape
    D = np.zeros((h, w), dtype=np.int8)
    colval = np.full(w, -1, dtype=np.int8)
    colrun = np.zeros(w, dtype=np.int32)
    err = np.zeros(w)
    forced_dropped = 0
    for r in range(h):
        t = np.clip(tgt[r] + err, -0.5, 1.5) if diffuse else tgt[r]
        forced = np.full(w, -1, dtype=np.int8)
        at_limit = (colrun >= L)
        forced[at_limit] = 1 - colval[at_limit]
        for c in range(w - L):
            blk = forced[c:c + L + 1]
            if blk[0] != -1 and np.all(blk == blk[0]):
                forced[c + L] = -1
                forced_dropped += 1
        INF = 1e18
        cost = np.full((2, L + 1), INF)
        back = np.zeros((w, 2, L + 1, 2), dtype=np.int16)
        for v in (0, 1):
            if forced[0] in (-1, v):
                cost[v, 1] = (t[0] - v) ** 2
        for c in range(1, w):
            nc = np.full((2, L + 1), INF)
            nb = np.zeros((2, L + 1, 2), dtype=np.int16)
            for v in (0, 1):
                if forced[c] not in (-1, v):
                    continue
                d = (t[c] - v) ** 2
                for k in range(1, L):
                    if cost[v, k] < INF and cost[v, k] + d < nc[v, k + 1]:
                        nc[v, k + 1] = cost[v, k] + d
                        nb[v, k + 1] = (v, k)
                o = 1 - v
                kb = int(np.argmin(cost[o, 1:L + 1])) + 1
                if cost[o, kb] < INF and cost[o, kb] + d < nc[v, 1]:
                    nc[v, 1] = cost[o, kb] + d
                    nb[v, 1] = (o, kb)
            cost, back[c] = nc, nb
        if cost.min() >= INF:
            raise Infeasible(f'row {r} infeasible at L={L}')
        fv, fk = np.unravel_index(np.argmin(cost), cost.shape)
        row = np.zeros(w, dtype=np.int8)
        v, k = int(fv), int(fk)
        for c in range(w - 1, -1, -1):
            row[c] = v
            if c:
                v, k = (int(z) for z in back[c, v, k])
        D[r] = row
        same = (row == colval)
        colrun = np.where(same, colrun + 1, 1)
        colval = row.copy()
        if diffuse:
            e = t - row
            err = np.zeros(w)
            err[:-1] += 0.3125 * e[1:]
            err += 0.3125 * e
            err[1:] += 0.125 * e[:-1]
    return D, forced_dropped


class Infeasible(RuntimeError):
    pass


def floyd(tgt):
    """Unconstrained baseline: plain Floyd-Steinberg. No float bound. Present to show the cost."""
    h, w = tgt.shape
    a = tgt.copy()
    D = np.zeros((h, w), dtype=np.int8)
    for r in range(h):
        for c in range(w):
            v = 1 if a[r, c] >= 0.5 else 0
            D[r, c] = v
            e = a[r, c] - v
            if c + 1 < w:
                a[r, c + 1] += e * 7 / 16
            if r + 1 < h:
                if c:
                    a[r + 1, c - 1] += e * 3 / 16
                a[r + 1, c] += e * 5 / 16
                if c + 1 < w:
                    a[r + 1, c + 1] += e * 1 / 16
    return D

# ---------------------------------------------------------------- measurement

def maxrun(D, axis):
    m = 0
    A = D if axis == 0 else D.T
    for line in A:
        k = 1
        for i in range(1, len(line)):
            k = k + 1 if line[i] == line[i - 1] else 1
            m = max(m, k)
        m = max(m, k)
    return m


def box(a, f):
    n = a.shape[0] // f
    return a[:n * f, :n * f].reshape(n, f, n, f).mean(axis=(1, 3))


def metrics(D, tgt):
    d = D.astype(float)
    out = {'maxrun_h': maxrun(D, 0), 'maxrun_v': maxrun(D, 1),
           'rmse_1to1': float(np.sqrt(((d - tgt) ** 2).mean())), 'ink': float(d.mean())}
    for f in (2, 4):
        b1, b2 = box(d, f), box(tgt, f)
        out[f'rmse_blur{f}'] = float(np.sqrt(((b1 - b2) ** 2).mean()))
        sd = b1.std() * b2.std()
        out[f'pearson_blur{f}'] = float(np.corrcoef(b1.ravel(), b2.ravel())[0, 1]) if sd > 1e-12 else None
    return out

# ---------------------------------------------------------------- render / export

def render(D, s=4):
    """Honest interlacement: v=1 warp (vertical) over, v=0 weft (horizontal) over."""
    h, w = D.shape
    H, W = h * s, w * s
    yy, xx = np.mgrid[0:H, 0:W]
    ix, iy = xx % s, yy % s
    prof = np.array([0.72, 1.0, 1.0, 0.72]) if s == 4 else 0.72 + 0.28 * np.sin(np.pi * (np.arange(s) + 0.5) / s)
    warp = 236 * prof[ix]
    weft = 34 + 34 * prof[iy]
    up = np.repeat(np.repeat(D, s, 0), s, 1).astype(bool)
    img = np.where(up, warp, weft)
    nb_v = np.repeat(np.repeat(np.roll(D, 1, 0) != D, s, 0), s, 1)
    nb_h = np.repeat(np.repeat(np.roll(D, 1, 1) != D, s, 0), s, 1)
    img = np.where(up & nb_v & (iy == 0), img * 0.80, img)
    img = np.where((~up) & nb_h & (ix == 0), img * 0.80, img)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), 'L')


def lift_bitmap(D):
    """One pixel per intersection. White = warp up (lifted), black = weft up."""
    return Image.fromarray((D.astype(np.uint8) * 255), 'L').convert('1')


def wif_liftplan(D, L):
    """WIF 1.1, straight-draw liftplan: warp end i (1-based) = column i-1 (left->right) on shaft
    i; pick j (1-based) = row j-1 (top->bottom); a listed shaft is raised. Port of float-core.js
    wif(), kept byte-for-byte equivalent in structure (verified against it on a 6x6 case).
    Honest limit: Shafts=n here can reach n=240, spec-valid but beyond what real shaft-loom
    software (Fiberworks, WeavePoint) typically supports (~40-60); this targets a digital-Jacquard
    bitmap loader, not a physical shaft loom, per the wedge's own claim ceiling."""
    n = D.shape[0]
    lines = ['[WIF]', 'Version=1.1', 'Date=' + time.strftime('%Y-%m-%d', time.gmtime()),
             'Developers=FLOAT wedge (private)', 'Source Program=FLOAT', 'Source Version=wedge',
             '', '[CONTENTS]', 'WEAVING=true', 'WARP=true', 'WEFT=true', 'THREADING=true',
             'LIFTPLAN=true', 'TEXT=true',
             '', '[TEXT]', f'Title=FLOAT L={L} {n}x{n}',
             'Note1=float-legal at L by construction; not a woven or weavable claim',
             'Note2=warp end i = lift bitmap column i (left to right); pick j = lift bitmap row j (top to bottom)',
             '', '[WEAVING]', f'Shafts={n}', 'Treadles=0', 'Rising Shed=true',
             '', '[WARP]', f'Threads={n}', '', '[WEFT]', f'Threads={n}', '', '[THREADING]']
    lines += [f'{i}={i}' for i in range(1, n + 1)]
    lines += ['', '[LIFTPLAN]']
    for r in range(n):
        up = ','.join(str(c + 1) for c in range(n) if D[r, c])
        lines.append(f'{r + 1}={up}')
    return '\r\n'.join(lines) + '\r\n'


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

# ---------------------------------------------------------------- view

VIEW = """<!doctype html><meta charset="utf-8"><title>{title}</title>
<style>
body{{margin:0;background:#111;color:#ccc;font:13px/1.5 ui-monospace,monospace}}
main{{display:flex;flex-direction:column;align-items:center;gap:10px;padding:16px}}
img{{image-rendering:pixelated;max-width:92vw}}
button{{font:inherit;padding:6px 12px;background:#222;color:#ccc;border:1px solid #555;cursor:pointer}}
table{{border-collapse:collapse}} td{{padding:2px 10px;border:1px solid #333}}
.bad{{color:#e66}} .ok{{color:#6d6}}
</style>
<main>
<div id="cap"></div>
<img id="v">
<button id="t">toggle (or press space)</button>
<table>
<tr><td>structure</td><td>{w} x {h}</td><td>L</td><td>{L}</td></tr>
<tr><td>bounded max run h / v</td><td class="ok">{ch} / {cv}</td>
    <td>unconstrained max run h / v</td><td class="bad">{bh} / {bv}</td></tr>
</table>
<div>float-legal at L by construction. not a woven or weavable claim.</div>
</main>
<script>
const A=['preview.png','preview_baseline.png'],
      C=['bounded  L={L}  max run {ch}/{cv}','unconstrained baseline  max run {bh}/{bv}'];
let i=0;const v=document.getElementById('v'),c=document.getElementById('cap');
function draw(){{v.src=A[i];c.textContent=C[i];}}
document.getElementById('t').onclick=()=>{{i=1-i;draw();}};
addEventListener('keydown',e=>{{if(e.code==='Space'){{e.preventDefault();i=1-i;draw();}}}});
draw();
</script>
"""

# ---------------------------------------------------------------- main

def run(src, L, n, outdir, scale=None):
    if L < 1:
        raise SystemExit('FAIL: L must be >= 1')
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    tgt = load_target(src, n)
    s = scale or (4 if n <= 120 else 2)

    t0 = time.time()
    try:
        D, forced_dropped = solve(tgt, L)
    except Infeasible as e:
        (out / 'receipt.json').write_text(json.dumps(
            {'status': 'FAIL', 'reason': f'infeasible: {e}', 'source': src, 'L': L,
             'structure': [n, n]}, indent=1))
        raise SystemExit(f'FAIL (closed): {e}')
    solve_s = time.time() - t0

    m = metrics(D, tgt)
    B = floyd(tgt)
    mb = metrics(B, tgt)

    # --- hard verification. Any breach fails closed: no preview, no bitmap, no ok receipt.
    problems = []
    if m['maxrun_h'] > L:
        problems.append(f"maxrun_h {m['maxrun_h']} > L {L}")
    if m['maxrun_v'] > L:
        problems.append(f"maxrun_v {m['maxrun_v']} > L {L}")
    if forced_dropped:
        problems.append(f'forced_dropped {forced_dropped}: a column constraint was relaxed, '
                        'guarantee void')
    if problems:
        (out / 'receipt.json').write_text(json.dumps(
            {'status': 'FAIL', 'reason': problems, 'source': src, 'L': L,
             'structure': [n, n], 'measured': m}, indent=1))
        raise SystemExit('FAIL (closed): ' + '; '.join(problems))

    Image.fromarray((tgt * 255).astype(np.uint8)).save(out / 'target.png')
    render(D, s).save(out / 'preview.png')
    render(B, s).save(out / 'preview_baseline.png')
    lb = lift_bitmap(D)
    lb.save(out / 'lift.png')
    lb.save(out / 'lift.bmp')
    lb.save(out / 'lift.tif')
    (out / 'lift.wif').write_text(wif_liftplan(D, L))
    (out / 'view.html').write_text(VIEW.format(
        title=f'FLOAT L={L}', w=n, h=n, L=L,
        ch=m['maxrun_h'], cv=m['maxrun_v'], bh=mb['maxrun_h'], bv=mb['maxrun_v']))

    receipt = {
        'status': 'OK',
        'claim': 'float-legal at L by construction; NOT a woven or weavable claim',
        'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'source': src,
        'structure': {'warp_threads': n, 'weft_threads': n, 'total_intersections': n * n},
        'L': L,
        'measured': {'maxrun_h': m['maxrun_h'], 'maxrun_v': m['maxrun_v'],
                     'constraint_satisfied': True, 'forced_dropped': forced_dropped,
                     'infeasible_rows': 0},
        'fidelity': {k: m[k] for k in ('rmse_1to1', 'rmse_blur2', 'pearson_blur2',
                                       'rmse_blur4', 'pearson_blur4', 'ink')},
        'unconstrained_baseline': {'algorithm': 'floyd-steinberg', 'maxrun_h': mb['maxrun_h'],
                                   'maxrun_v': mb['maxrun_v'],
                                   'rmse_blur4': mb['rmse_blur4'],
                                   'pearson_blur4': mb['pearson_blur4'],
                                   'float_bound_respected': False},
        'lift_bitmap': {'convention': 'white(1) = warp up / lifted; black(0) = weft up',
                        'pixels_per_intersection': 1,
                        'files': ['lift.png', 'lift.bmp', 'lift.tif']},
        'wif': {'version': '1.1', 'convention': 'straight threading (1 shaft per warp end), '
                'explicit per-pick LIFTPLAN, no treadles', 'unambiguous': True,
                'honest_limit': f'Shafts={n} is spec-valid but exceeds typical shaft-loom '
                'software support (~40-60); targets a digital-Jacquard bitmap loader, not a '
                'physical shaft loom', 'files': ['lift.wif']},
        'preview': {'render_scale_px_per_thread': s, 'files': ['preview.png',
                                                               'preview_baseline.png']},
        'solver': {'rows': 'exact DP, max run <= L per row',
                   'columns': 'hard forcing from placed rows, greedy in the vertical direction',
                   'optimality': 'not jointly optimal; satisfies L, not proven minimum-error',
                   'seconds': round(solve_s, 3)},
    }
    receipt['sha256'] = {f.name: sha256(f) for f in sorted(out.iterdir())
                         if f.name != 'receipt.json'}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=1))

    p4 = f'{m["pearson_blur4"]:.4f}' if m['pearson_blur4'] is not None else 'nan (L=1: no variance)'
    print(f'OK  {src}  L={L}  {n}x{n}  maxrun h/v = {m["maxrun_h"]}/{m["maxrun_v"]}  '
          f'(baseline {mb["maxrun_h"]}/{mb["maxrun_v"]})  '
          f'pearson_b4 {p4}  -> {out}')
    return receipt


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='FLOAT: image -> float-bounded two-shed structure')
    ap.add_argument('source', help='image path, or pattern:rings / pattern:blocks')
    ap.add_argument('-L', type=int, required=True, help='max float length, both directions')
    ap.add_argument('-n', '--size', type=int, default=240, help='structure size in threads')
    ap.add_argument('-o', '--out', required=True, help='output directory')
    ap.add_argument('--scale', type=int, default=None, help='preview px per thread')
    a = ap.parse_args()
    try:
        run(a.source, a.L, a.size, a.out, a.scale)
    except SystemExit as e:
        print(e, file=sys.stderr)
        raise
