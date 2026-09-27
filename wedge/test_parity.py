#!/usr/bin/env python3
"""FLOAT parity check: float-core.js (JS port) vs weave.py's solve() (frozen kernel), on the
SAME Python-generated targets. Verifies:
  1. D (the structure) is bit-for-bit identical between the two solvers.
  2. forced_dropped matches exactly.
  3. FloatCore.bmp1 / FloatCore.tif1 (never read back before) decode via PIL to the same
     bitmap as D, under the documented convention (1 = warp up / lifted = white).

Does not modify weave.py or float-core.js. Requires `node` on PATH.
"""
import atexit
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import weave  # noqa: E402  (local import after sys.path fix)

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='float-parity-'))
atexit.register(shutil.rmtree, TMP, ignore_errors=True)
CORE = json.dumps(str(HERE / 'float-core.js'))

# Node helpers, written to a temporary directory at run time.
NODE_SOLVE = TMP / 'node_solve.js'
NODE_SOLVE.write_text(f"""const fs = require('fs'), FloatCore = require({CORE});
const [inp, outp] = process.argv.slice(2), a = JSON.parse(fs.readFileSync(inp, 'utf8'));
const r = FloatCore.solve(Float64Array.from(a.tgt), a.n, a.n, a.L);
fs.writeFileSync(outp, JSON.stringify({{D: Array.from(r.D), forcedDropped: r.forcedDropped}}));
""")
NODE_EXPORT = TMP / 'node_export.js'
NODE_EXPORT.write_text(f"""const fs = require('fs'), FloatCore = require({CORE});
const [inp, bmpp, tifp] = process.argv.slice(2), a = JSON.parse(fs.readFileSync(inp, 'utf8'));
const D = Int8Array.from(a.D);
fs.writeFileSync(bmpp, FloatCore.bmp1(D, a.n));
fs.writeFileSync(tifp, FloatCore.tif1(D, a.n));
""")

SOURCES = {
    'altai': str(HERE / 'interface' / 'assets' / 'specimen-source.png'),
    'rings': 'pattern:rings',
    'blocks': 'pattern:blocks',
}
N = 240
LS = (2, 3, 5)


def node_solve(tgt, n, L):
    inp = TMP / 'p_in.json'
    outp = TMP / 'p_out.json'
    inp.write_text(json.dumps({'tgt': tgt.flatten().tolist(), 'n': n, 'L': L}))
    subprocess.run(['node', str(NODE_SOLVE), str(inp), str(outp)], check=True, cwd=HERE)
    res = json.loads(outp.read_text())
    inp.unlink(missing_ok=True)
    outp.unlink(missing_ok=True)
    return np.array(res['D'], dtype=np.int8).reshape(n, n), res['forcedDropped']


def node_export(D, n):
    inp = TMP / 'p_exp_in.json'
    bmpp = TMP / 'p_exp.bmp'
    tifp = TMP / 'p_exp.tif'
    inp.write_text(json.dumps({'D': D.flatten().tolist(), 'n': n}))
    subprocess.run(['node', str(NODE_EXPORT), str(inp), str(bmpp), str(tifp)], check=True, cwd=HERE)
    bmp_bits = np.array(Image.open(bmpp).convert('1'), dtype=np.uint8)
    tif_bits = np.array(Image.open(tifp).convert('1'), dtype=np.uint8)
    inp.unlink(missing_ok=True)
    bmpp.unlink(missing_ok=True)
    tifp.unlink(missing_ok=True)
    return bmp_bits, tif_bits


def main():
    rows = []
    all_pass = True
    for name, src in SOURCES.items():
        tgt = weave.load_target(src, N)
        for L in LS:
            D_py, fd_py = weave.solve(tgt, L)
            D_js, fd_js = node_solve(tgt, N, L)

            d_match = np.array_equal(D_py, D_js)
            fd_match = (fd_py == fd_js)

            bmp_bits, tif_bits = node_export(D_js, N)
            expect = (D_py.astype(np.uint8) * 255) > 0
            bmp_match = np.array_equal(bmp_bits.astype(bool), expect)
            tif_match = np.array_equal(tif_bits.astype(bool), expect)

            ok = d_match and fd_match and bmp_match and tif_match
            all_pass &= ok
            rows.append({
                'source': name, 'L': L, 'n': N,
                'D_bit_identical': bool(d_match),
                'forced_dropped_py': int(fd_py), 'forced_dropped_js': int(fd_js),
                'forced_dropped_match': bool(fd_match),
                'bmp1_matches_D': bool(bmp_match), 'tif1_matches_D': bool(tif_match),
                'verdict': 'PASS' if ok else 'FAIL',
            })
            print(f"{name:8s} L={L}  D_match={d_match}  fd {fd_py}=={fd_js} {fd_match}  "
                  f"bmp1={bmp_match}  tif1={tif_match}  -> {'PASS' if ok else 'FAIL'}")

    receipt = HERE / 'out' / 'TEST-PARITY.md'
    receipt.parent.mkdir(exist_ok=True)
    receipt.write_text(
        '# FLOAT parity check: float-core.js vs weave.py\n\n'
        'Same Python-generated targets (weave.load_target) fed to both solvers. '
        'D compared bit-for-bit; forced_dropped compared exactly; bmp1/tif1 read back via PIL '
        'and compared to D under the lift convention (1 = warp up = white).\n\n'
        'Does not modify weave.py or float-core.js.\n\n'
        '| source | L | n | D bit-identical | forced_dropped py/js | bmp1==D | tif1==D | verdict |\n'
        '|---|---|---|---|---|---|---|---|\n' +
        '\n'.join(
            f"| {r['source']} | {r['L']} | {r['n']} | {r['D_bit_identical']} | "
            f"{r['forced_dropped_py']}/{r['forced_dropped_js']} | {r['bmp1_matches_D']} | "
            f"{r['tif1_matches_D']} | **{r['verdict']}** |"
            for r in rows
        ) +
        f"\n\n**Overall: {'ALL PASS' if all_pass else 'FAIL — see rows above'}**\n\n"
        f"{len(rows)} / {len(rows)} cases run. "
        f"{sum(1 for r in rows if r['verdict']=='PASS')} passed.\n"
    )
    print(f"\n{'ALL PASS' if all_pass else 'FAIL'} — {receipt.relative_to(HERE)} written")
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
