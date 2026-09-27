# Third-party notices

This project's own code is licensed under MIT (see `LICENSE`). The following bundled assets are under separate, different terms.

## TeX Gyre Heros

Font files (`TeXGyreHeros-Regular.woff2`, `TeXGyreHeros-Bold.woff2`) are bundled unmodified under the **GUST Font License**. The controlling license text ships alongside the fonts at `wedge/interface/assets/fonts/LICENSE.txt` (and its copy in `docs/assets/fonts/LICENSE.txt`). The GUST Font License is not this project's license — it applies only to these font files.

## Altai specimen image

- **Title:** Altai
- **Author:** Alesya Khoteeva
- **License:** CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/
- **Source:** KDE Plasma wallpaper package (upstream: https://invent.kde.org/plasma/plasma-workspace-wallpapers)

`wedge/interface/assets/specimen-source.png` (and its copy `docs/assets/specimen-source.png`) is the unmodified 5120×2880 original.

The following files are **adaptations** of it (changes were made), shared under the same CC BY-SA 4.0 license:

- `proof_target.png` — centre-cropped to a square, converted to grayscale, contrast-stretched, resampled to 100×100 and enlarged.
- `proof_L3.png`, `proof_twin.png` — binary structures computed from that resampled target (bounded at L=3, and an unbounded dither), rendered as images.
- `docs/float.png` — a screenshot of the browser view: a square crop of the image, converted to grayscale, resampled to 104×104, solved into a bounded binary structure and drawn as marks, beside a small grayscale thumbnail of the crop.
- The browser view generates the same kind of crop, resample and structure at runtime.

These image assets remain under CC BY-SA 4.0, separate from this project's MIT code license.
