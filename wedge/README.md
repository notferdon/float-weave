# FLOAT — wedge

Local image → binary two-shed structure whose maximum float is **≤ L in both the warp and the
weft direction**, with an honest interlacement preview, a lift bitmap, and a machine-readable
receipt.

**Claim ceiling: float-legal at L by construction.** Nothing here says a structure is weavable
or has been through a loom; yarn, tension, sett and loom behaviour are outside what this measures.

## Run

```bash
cd wedge
python3 weave.py <image-path> -L 3 -n 240 -o out/my_run
python3 weave.py pattern:blocks -L 2 -n 240 -o out/blocks_L2   # built-in test patterns
xdg-open out/my_run/view.html                                   # preview + baseline toggle
```

Requires `numpy` and `Pillow`. No install, no server, no account, no network.

| flag | meaning | default |
|---|---|---|
| `source` | image path, or `pattern:rings` / `pattern:blocks` | required |
| `-L` | maximum float length, enforced in both directions | required |
| `-n, --size` | structure size in threads (n × n) | 240 |
| `-o, --out` | output directory | required |
| `--scale` | preview pixels per thread | 4 if n ≤ 120 else 2 |

## Outputs

| file | what it is |
|---|---|
| `preview.png` | the bounded structure drawn as interlacement |
| `preview_baseline.png` | the same image dithered with **no** float bound, same renderer |
| `view.html` | the two previews with a toggle (space / button) and the measured runs |
| `lift.png`, `lift.bmp`, `lift.tif` | 1-bit lift bitmap, one pixel per intersection |
| `lift.wif` | WIF 1.1 straight-draw liftplan of the same structure: one shaft per warp end, so `Shafts = n` (240 at the default size). A representation of the structure in WIF form, not a statement about any loom. |
| `target.png` | the grayscale target after crop and contrast stretch |
| `receipt.json` | dimensions, L, measured `maxrun_h` / `maxrun_v`, forced/failed constraints, fidelity, baseline, sha256 of every other output |

Lift bitmap convention: **white (1) = warp up / lifted, black (0) = weft up.** One pixel per
intersection, no scaling.

## The baseline is not decoration

`preview_baseline.png` is plain Floyd–Steinberg on the same target with the bound removed. It is
there to show what the bound costs and what it buys: without the bound, runs can grow to a large
fraction of the structure's width or height, which is exactly what the bound prevents. The
`receipt.json` of every run records the baseline's measured maximum runs next to the bounded ones.

## Fails closed

The solver's output is re-measured independently before anything is written. If the measured
maximum run exceeds `L` in either direction, or if any column constraint had to be relaxed
(`forced_dropped > 0`), the run **writes only a FAIL receipt** — no preview, no lift bitmap — and
exits non-zero. An infeasible row does the same. Verified by `test_failclosed.py`.

```bash
python3 test_failclosed.py     # feeds run() deliberately violating structures
```

## Method

Copied from the frozen proof at `../float_proof.py`, unchanged in behaviour:

- **Rows: exact.** Dynamic programming over (current value × run length), so horizontal floats
  ≤ L are optimal per row.
- **Columns: hard, greedy.** A column whose vertical run has reached L has its next value forced
  to flip; the row DP treats that as a domain restriction and plans around it rather than
  repairing afterwards.
- Error diffused row → row.
- **Not jointly optimal.** The result satisfies L; it is not proven minimum-error. Multi-row
  coupling is what makes the true optimum intractable.

## Scope

Grayscale, two sheds, square structure, one float bound. No colour, no multi-layer, no loom
simulation, no material styling, no shaft-loom threading constraints, no account or server.
