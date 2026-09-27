"""Exercise the real guard: hand run() a structure that violates L and confirm it fails closed."""
import json, numpy as np, weave
from pathlib import Path

REAL = weave.solve
out = Path('out/_failclosed'); ok = True

def bad(tgt, L):
    D = np.zeros(tgt.shape, dtype=np.int8)
    D[:, : L + 4] = 1                      # a run of L+4 in both directions
    return D, 0

def dropped(tgt, L):
    D, _ = REAL(tgt, L)
    return D, 7                            # pretend a column constraint was relaxed

for label, fn in (('violates_L', bad), ('forced_dropped', dropped)):
    weave.solve = fn
    d = out / label
    try:
        weave.run('pattern:rings', 3, 48, str(d))
        print(f'{label}: NOT CAUGHT  <-- FAIL'); ok = False
    except SystemExit:
        r = json.loads((d / 'receipt.json').read_text())
        wrote = sorted(p.name for p in d.iterdir())
        clean = wrote == ['receipt.json']
        print(f'{label}: caught, status={r["status"]}, reason={r["reason"]}')
        print(f'   files written: {wrote}  (only receipt: {clean})')
        ok &= r['status'] == 'FAIL' and clean
    finally:
        weave.solve = REAL
print('FAIL-CLOSED SELFTEST:', 'PASS' if ok else 'FAIL')
raise SystemExit(0 if ok else 1)
