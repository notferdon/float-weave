"""FLOAT fatal proof: binary two-shed image -> weave structure with hard max float L
in BOTH directions. Scratch only. No loom claim."""
import numpy as np
from PIL import Image

SRC = '/usr/share/wallpapers/Altai/contents/images/5120x2880.png'

def target(n):
    im = Image.open(SRC).convert('L')
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w-s)//2, (h-s)//2, (w-s)//2+s, (h-s)//2+s)).resize((n, n), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float64)/255.0
    a = (a - a.min())/(a.max()-a.min())          # full-range, both media hit black & white
    return a

# ---------- solver ----------
def solve(tgt, L, diffuse=True):
    """Row-exact DP (max run <= L along the row) with hard per-column forcing from the
    rows already placed (max run <= L down the column). Error diffused row->row."""
    h, w = tgt.shape
    D = np.zeros((h, w), dtype=np.int8)
    colval = np.full(w, -1, dtype=np.int8)   # value of current vertical run
    colrun = np.zeros(w, dtype=np.int32)     # its length
    err = np.zeros(w)
    forced_dropped = 0
    for r in range(h):
        t = np.clip(tgt[r] + err, -0.5, 1.5) if diffuse else tgt[r]
        forced = np.full(w, -1, dtype=np.int8)
        at_limit = (colrun >= L)
        forced[at_limit] = 1 - colval[at_limit]          # must break the column run
        # infeasible iff L+1 consecutive columns are forced to the same value
        for c in range(w - L):
            blk = forced[c:c+L+1]
            if blk[0] != -1 and np.all(blk == blk[0]):
                forced[c+L] = -1; forced_dropped += 1
        # DP over states (value v, run length k in 1..L)
        INF = 1e18
        cost = np.full((2, L+1), INF); back = np.zeros((w, 2, L+1, 2), dtype=np.int16)
        for v in (0, 1):
            if forced[0] in (-1, v): cost[v, 1] = (t[0]-v)**2
        for c in range(1, w):
            nc = np.full((2, L+1), INF); nb = np.zeros((2, L+1, 2), dtype=np.int16)
            for v in (0, 1):
                if forced[c] not in (-1, v): continue
                d = (t[c]-v)**2
                # extend a run of v
                for k in range(1, L):
                    if cost[v, k] < INF and cost[v, k]+d < nc[v, k+1]:
                        nc[v, k+1] = cost[v, k]+d; nb[v, k+1] = (v, k)
                # start a new run of v (previous cell was 1-v, any length)
                o = 1-v; kb = int(np.argmin(cost[o, 1:L+1]))+1
                if cost[o, kb] < INF and cost[o, kb]+d < nc[v, 1]:
                    nc[v, 1] = cost[o, kb]+d; nb[v, 1] = (o, kb)
            cost, back[c] = nc, nb
        if cost.min() >= INF: raise RuntimeError(f'row {r} infeasible at L={L}')
        fv, fk = np.unravel_index(np.argmin(cost), cost.shape)
        row = np.zeros(w, dtype=np.int8); v, k = int(fv), int(fk)
        for c in range(w-1, -1, -1):
            row[c] = v
            if c: v, k = (int(x) for x in back[c, v, k])
        D[r] = row
        same = (row == colval)
        colrun = np.where(same, colrun+1, 1); colval = row.copy()
        if diffuse:
            e = t - row
            err = np.zeros(w)
            err[:-1] += 0.3125*e[1:]; err += 0.3125*e; err[1:] += 0.125*e[:-1]
    return D, forced_dropped

def floyd(tgt):
    h, w = tgt.shape; a = tgt.copy(); D = np.zeros((h, w), dtype=np.int8)
    for r in range(h):
        for c in range(w):
            v = 1 if a[r, c] >= 0.5 else 0; D[r, c] = v; e = a[r, c]-v
            if c+1 < w: a[r, c+1] += e*7/16
            if r+1 < h:
                if c: a[r+1, c-1] += e*3/16
                a[r+1, c] += e*5/16
                if c+1 < w: a[r+1, c+1] += e*1/16
    return D

# ---------- verification ----------
def maxrun(D, axis):
    m = 0; A = D if axis == 0 else D.T
    for line in A:
        k = 1
        for i in range(1, len(line)):
            k = k+1 if line[i] == line[i-1] else 1
            m = max(m, k)
        m = max(m, k)
    return m

def runhist(D):
    h = {}
    for A in (D, D.T):
        for line in A:
            k = 1
            for i in range(1, len(line)):
                if line[i] == line[i-1]: k += 1
                else: h[k] = h.get(k, 0)+1; k = 1
            h[k] = h.get(k, 0)+1
    return h

def box(a, f):
    n = a.shape[0]//f
    return a[:n*f, :n*f].reshape(n, f, n, f).mean(axis=(1, 3))

def metrics(D, tgt):
    d = D.astype(float)
    out = {'maxrun_weft_horizontal': maxrun(D, 0), 'maxrun_warp_vertical': maxrun(D, 1),
           'rmse_1to1': float(np.sqrt(((d-tgt)**2).mean())), 'ink': float(d.mean())}
    for f in (2, 4):
        b1, b2 = box(d, f), box(tgt, f)
        out[f'rmse_blur{f}'] = float(np.sqrt(((b1-b2)**2).mean()))
        out[f'pearson_blur{f}'] = float(np.corrcoef(b1.ravel(), b2.ravel())[0, 1])
    return out

# ---------- interlacement renderer ----------
def render(D, s=4):
    """v=1 -> warp (vertical thread) passes OVER; v=0 -> weft (horizontal) passes over."""
    h, w = D.shape
    H, W = h*s, w*s
    yy, xx = np.mgrid[0:H, 0:W]
    ix, iy = xx % s, yy % s
    # round-ish thread profiles across each thread's width
    prof = np.array([0.72, 1.0, 1.0, 0.72][:s] if s == 4 else
                    0.72+0.28*np.sin(np.pi*(np.arange(s)+0.5)/s))
    warp = 236*prof[ix]                     # light warp
    weft = 34 + 34*prof[iy]                 # dark weft, lighter along its crown
    up = np.repeat(np.repeat(D, s, 0), s, 1).astype(bool)
    img = np.where(up, warp, weft)
    # crossing shadow: the thread going under is darkened where its neighbour rides over
    nb_v = np.repeat(np.repeat(np.roll(D, 1, 0) != D, s, 0), s, 1)
    nb_h = np.repeat(np.repeat(np.roll(D, 1, 1) != D, s, 0), s, 1)
    img = np.where(up & nb_v & (iy == 0), img*0.80, img)
    img = np.where((~up) & nb_h & (ix == 0), img*0.80, img)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), 'L')

if __name__ == '__main__':
    N = 100
    tgt = target(N)
    Image.fromarray((tgt*255).astype(np.uint8)).resize((400, 400), Image.NEAREST).save('proof_target.png')
    print(f'source {SRC}\ntarget {N}x{N} grayscale, contrast-stretched\n')
    print('=== L sweep (structure 100x100) ===')
    print(f"{'L':>4} {'maxrun_h':>9} {'maxrun_v':>9} {'rmse1:1':>8} {'rmse_b4':>8} {'pearson_b4':>11} {'ink':>6} {'forced_dropped':>15}")
    res = {}
    for L in (1, 2, 3, 4, 5, 8, 12):
        D, fd = solve(tgt, L); m = metrics(D, tgt); res[L] = (D, m)
        print(f"{L:>4} {m['maxrun_weft_horizontal']:>9} {m['maxrun_warp_vertical']:>9} "
              f"{m['rmse_1to1']:>8.4f} {m['rmse_blur4']:>8.4f} {m['pearson_blur4']:>11.4f} "
              f"{m['ink']:>6.3f} {fd:>15}")
        if L in (1, 3, 5): render(D).save(f'proof_L{L}.png')
    print('\n=== generic twin: unconstrained Floyd-Steinberg ===')
    T = floyd(tgt); mt = metrics(T, tgt); render(T).save('proof_twin.png')
    print(f"{'inf':>4} {mt['maxrun_weft_horizontal']:>9} {mt['maxrun_warp_vertical']:>9} "
          f"{mt['rmse_1to1']:>8.4f} {mt['rmse_blur4']:>8.4f} {mt['pearson_blur4']:>11.4f} {mt['ink']:>6.3f}")
    hc, ht = runhist(res[3][0]), runhist(T)
    print('\nrun-length histogram (both directions), L=3 vs twin:')
    for k in sorted(set(hc) | set(ht))[:14]:
        print(f'  run {k:>3}: constrained {hc.get(k,0):>6}   twin {ht.get(k,0):>6}')
    print('  twin runs longer than 3 :', sum(v for k, v in ht.items() if k > 3))
    print('  constrained runs > 3   :', sum(v for k, v in hc.items() if k > 3))
    print('\n=== realistic scale check, 240x240, L=3 ===')
    t2 = target(240); D2, fd2 = solve(t2, 3); m2 = metrics(D2, t2)
    print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in m2.items()}, 'forced_dropped', fd2)
    render(D2, s=2).save('proof_240_L3.png')
    T2 = floyd(t2); print('twin 240 maxrun h/v:', maxrun(T2, 0), maxrun(T2, 1))
