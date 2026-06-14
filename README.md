# KDP Cover Editor

A lightweight web tool for building **print-ready Amazon KDP paperback cover spreads**
(back + spine + front, with bleed). Upload your artwork, set your book's page count, paper,
and trim size, position it against live KDP guides, and export a correctly-sized PNG or PDF
at 300 DPI.

Built with a small Flask backend + Pillow for rendering, and a vanilla JS / Konva canvas
front end. No build step, no framework.

## Features

- **Accurate KDP sizing** — computes the full cover canvas (bleed + back + spine + front)
  from trim size, page count, and paper type, at 300 DPI.
- **Live guides** — trim lines, spine fold lines, safe/live area, spine-safe + barcode reference.
- **Two image slots** with full transform: move, scale, rotate, flip, and layer ordering
  (bring forward / send backward).
- **Fit presets** — Fit to Safe Area, Fit to Front Cover, Overall Fit, Reset.
- **Ctrl-drag** to constrain movement to one axis.
- **Resolution check** — warns when a placed image would print below 300 DPI.
- **Optimize to 300 DPI** — optional AI upscaling (Real-ESRGAN) for low-res artwork, with a
  live progress bar.
- **Export** — print-ready PNG or PDF (guides off by default for print).
- Clean, responsive UI with a collapsible control panel.

## Requirements

- Python 3.10+
- The packages in [`requirements.txt`](requirements.txt). The "Optimize to 300 DPI" feature
  pulls in PyTorch + Real-ESRGAN, which are large; everything else is lightweight.

## Install

Windows:

```bat
setup.bat
```

Or manually (any OS):

```bash
pip install -r requirements.txt
```

## Run

Windows:

```bat
run_app.bat
```

Or:

```bash
python app.py
```

Then open <http://127.0.0.1:5050>.

## Usage

1. **Images** — upload Image 1 (and optionally Image 2).
2. **Book Setup** — set Pages, Paper (`B&W White`, `B&W Cream`, `Color`), and Trim
   (`6x9`, `5x8`, `5.5x8.5`, `7x10`, `8.5x11`). The canvas resizes to match.
3. **Transform** — drag to position; resize with the corner handles; rotate; flip; or use a
   fit preset. Hold **Ctrl** while dragging to lock to one axis.
4. **Layers** — reorder which image sits on top.
5. **Optimize** (optional) — if the resolution warning shows, upscale the selected image to
   ~300 DPI. The first run downloads a small model into `weights/`.
6. **Export** — PNG or PDF. Leave "Bake guides into export" **off** for a print-ready file.

### Command-line

`cover_sizer.py` also works standalone to fit a single image to a full cover:

```bash
python cover_sizer.py --image art.png --pages 120 --paper bw_white --trim 6x9
python cover_sizer.py --pages 200 --trim 6x9 --info   # print dimensions only
```

## How it works

KDP requires the full cover as one image: `bleed | back | spine | front | bleed`. Spine width
is derived from page count × a per-paper constant. `cover_sizer.py` computes every dimension at
300 DPI; the front end mirrors that math to show guides and to map your on-screen placement back
to full-resolution pixels at export time.

## Project structure

```
app.py            Flask server + API (dimensions, render, upscale)
cover_sizer.py    KDP dimension math + Pillow rendering (also a CLI)
upscaler.py       Real-ESRGAN x4 super-resolution (lazy-loaded)
static/           index.html, style.css, app.js, konva.min.js
tests/            pytest suite
```

## Credits

- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — super-resolution model (BSD-3-Clause)
- [Konva](https://konvajs.org/) — 2D canvas library (MIT)
- [Pillow](https://python-pillow.org/) and [Flask](https://flask.palletsprojects.com/)

## License

[MIT](LICENSE)
