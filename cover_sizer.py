"""
KDP Full-Cover Sizer
Fits any image to a KDP paperback spread (back + spine + front + bleed).

Usage:
  python cover_sizer.py --image path/to/img.png --pages 120
  python cover_sizer.py --image img.png --pages 200 --paper color --trim 6x9 --no-guides
  python cover_sizer.py --image img.png --pages 120 --info
"""

import argparse
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps, ImageChops

DPI = 300

SPINE_PER_PAGE = {
    "bw_white": 0.002252,
    "bw_cream":  0.002347,
    "color":     0.002347,
}

TRIM_SIZES = {
    "6x9":   (6.0, 9.0),
    "5x8":   (5.0, 8.0),
    "5.5x8.5": (5.5, 8.5),
    "7x10":  (7.0, 10.0),
    "8.5x11": (8.5, 11.0),
}

BLEED = 0.125         # inches, outer bleed
LIVE_INSET = 0.125    # inches, KDP safe-area margin from each trim edge
SPINE_MARGIN = 0.0625 # inches, margin each side inside the spine (KDP ~0.062)
BARCODE_W = 2.0       # inches, KDP barcode reserved area
BARCODE_H = 1.2
BARCODE_MARGIN = 0.25 # inches, barcode clearance from trim/spine


def px(inches: float) -> int:
    return round(inches * DPI)


def calc_dims(trim_w: float, trim_h: float, pages: int, paper: str) -> dict:
    spine_in = round(pages * SPINE_PER_PAGE[paper], 4)
    bleed    = BLEED

    panel_w  = px(trim_w)
    panel_h  = px(trim_h)
    spine_px = px(spine_in)
    bleed_px = px(bleed)
    live_px  = px(LIVE_INSET)

    total_w  = bleed_px + panel_w + spine_px + panel_w + bleed_px
    total_h  = bleed_px + panel_h + bleed_px

    # x-offsets (left to right)
    back_x   = bleed_px
    spine_x  = bleed_px + panel_w
    front_x  = bleed_px + panel_w + spine_px
    y0       = bleed_px

    # spine safe area (inside the spine, inset by spine margin)
    spine_margin_px = px(SPINE_MARGIN)
    spine_safe_x = spine_x + spine_margin_px
    spine_safe_w = max(0, spine_px - 2 * spine_margin_px)

    # barcode reserved area: bottom-RIGHT of the back cover (spine side), per KDP
    bc_w = px(BARCODE_W)
    bc_h = px(BARCODE_H)
    bcm  = px(BARCODE_MARGIN)
    bc_x = spine_x - bcm - bc_w
    bc_y = y0 + panel_h - bcm - bc_h

    # combined safe/live area spanning both panels + spine: inset only on the
    # two OUTER edges (left of back cover, right of front cover, top, bottom);
    # the spine-adjacent edges stay flush, matching KDP's live-area diagram.
    safe_x = back_x + live_px
    safe_y = y0 + live_px
    safe_w = (front_x + panel_w - live_px) - safe_x
    safe_h = panel_h - 2 * live_px

    return dict(
        trim_w=trim_w, trim_h=trim_h, spine_in=spine_in, pages=pages, paper=paper,
        panel_w=panel_w, panel_h=panel_h,
        spine_px=spine_px, bleed_px=bleed_px, live_px=live_px,
        total_w=total_w, total_h=total_h,
        back_x=back_x, spine_x=spine_x, front_x=front_x, y0=y0,
        spine_margin_px=spine_margin_px, spine_safe_x=spine_safe_x, spine_safe_w=spine_safe_w,
        bc_x=bc_x, bc_y=bc_y, bc_w=bc_w, bc_h=bc_h,
        safe_x=safe_x, safe_y=safe_y, safe_w=safe_w, safe_h=safe_h,
    )


def print_info(d: dict):
    print(f"\nKDP Cover Dimensions @ {DPI} DPI")
    print(f"  Trim:   {d['trim_w']}\" × {d['trim_h']}\"  ({d['panel_w']} × {d['panel_h']} px)")
    print(f"  Spine:  {d['spine_in']}\" ({d['spine_px']} px)  [{d['pages']} pp, {d['paper']}]")
    print(f"  Bleed:  {BLEED}\" ({d['bleed_px']} px)")
    print(f"  Canvas: {d['total_w']} × {d['total_h']} px  "
          f"({d['total_w']/DPI:.3f}\" × {d['total_h']/DPI:.3f}\")\n")


def autocrop(img: Image.Image, threshold: int = 245) -> Image.Image:
    """Crop off uniform near-white padding around the real artwork."""
    gray = img.convert("L")
    # mask: content = darker than threshold (i.e. not near-white)
    mask = gray.point(lambda p: 255 if p < threshold else 0)
    bbox = mask.getbbox()
    if not bbox:
        return img  # all white — nothing to crop
    return img.crop(bbox)


def check_image(img_path: str, d: dict, do_autocrop: bool) -> Image.Image:
    img = Image.open(img_path).convert("RGB")
    ow, oh = img.size

    if do_autocrop:
        img = autocrop(img)
        if img.size != (ow, oh):
            cw, ch = img.size
            print(f"Auto-cropped padding: {ow}×{oh} -> {cw}×{ch} px "
                  f"(removed {ow-cw} px W, {oh-ch} px H)")

    iw, ih = img.size
    rw, rh = d["total_w"], d["total_h"]

    in_ar  = iw / ih
    req_ar = rw / rh
    if abs(in_ar - req_ar) / req_ar > 0.02:
        print(f"  NOTE: artwork aspect {in_ar:.3f} differs from target {req_ar:.3f} "
              f"— edges will be cropped to fit (no distortion).")


    print(f"Image input:    {iw} × {ih} px  ({iw/DPI:.3f}\" × {ih/DPI:.3f}\")")
    print(f"Required canvas:{rw} × {rh} px  ({rw/DPI:.3f}\" × {rh/DPI:.3f}\")")

    if iw == rw and ih == rh:
        print("  Dimensions match exactly — no scaling needed.\n")
    else:
        dw = iw - rw
        dh = ih - rh
        print(f"  Mismatch: width {'+' if dw>=0 else ''}{dw} px, height {'+' if dh>=0 else ''}{dh} px")
        if iw < rw or ih < rh:
            print("  WARNING: Image is smaller than required — upscaling will reduce quality.")
        else:
            print("  Image will be cropped/scaled to fit exactly.")
        print(f"  Output will be enforced to {rw} × {rh} px @ {DPI} DPI.\n")

    return img


def fit_image(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)


def draw_guides(canvas: Image.Image, d: dict) -> Image.Image:
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    bleed = d["bleed_px"]
    live  = d["live_px"]
    pw    = d["panel_w"]
    ph    = d["panel_h"]
    sp    = d["spine_px"]
    bx    = d["back_x"]
    sx    = d["spine_x"]
    fx    = d["front_x"]
    y0    = d["y0"]
    W, H  = canvas.size

    # --- trim lines (black solid, 2px) ---
    trim_coords = [
        # back cover trim box
        (bx, y0, bx + pw, y0 + ph),
        # front cover trim box
        (fx, y0, fx + pw, y0 + ph),
    ]
    for box in trim_coords:
        draw.rectangle(box, outline=(0, 0, 0, 200), width=2)

    # --- spine fold lines (blue dashed) ---
    def dashed_vline(x, y_start, y_end, color, gap=12, seg=8):
        y = y_start
        while y < y_end:
            draw.line([(x, y), (x, min(y + seg, y_end))], fill=color, width=2)
            y += seg + gap

    dashed_vline(sx,      y0, y0 + ph, (30, 80, 220, 220))
    dashed_vline(sx + sp, y0, y0 + ph, (30, 80, 220, 220))

    # --- live area (green dashed) ---
    def dashed_rect(box, color, gap=10, seg=8):
        x1, y1, x2, y2 = box
        # top
        x = x1
        while x < x2:
            draw.line([(x, y1), (min(x + seg, x2), y1)], fill=color, width=2)
            x += seg + gap
        # bottom
        x = x1
        while x < x2:
            draw.line([(x, y2), (min(x + seg, x2), y2)], fill=color, width=2)
            x += seg + gap
        # left
        y = y1
        while y < y2:
            draw.line([(x1, y), (x1, min(y + seg, y2))], fill=color, width=2)
            y += seg + gap
        # right
        y = y1
        while y < y2:
            draw.line([(x2, y), (x2, min(y + seg, y2))], fill=color, width=2)
            y += seg + gap

    green = (0, 180, 60, 200)
    # safe area: inset 'live' from each TRIM edge; spine-fold edge stays flush (KDP)
    # back panel: inset left/top/bottom, flush right to spine
    dashed_rect((bx + live, y0 + live, bx + pw, y0 + ph - live), green)
    # front panel: flush left to spine, inset right/top/bottom
    dashed_rect((fx, y0 + live, fx + pw - live, y0 + ph - live), green)

    out = canvas.convert("RGBA")
    out = Image.alpha_composite(out, overlay)
    return out.convert("RGB")


def blank_outside_safe(canvas: Image.Image, d: dict) -> Image.Image:
    """Paint the perimeter band outside the combined safe/live-area rectangle
    white — i.e. erase whatever lands in the 'out of live area' zone."""
    draw = ImageDraw.Draw(canvas)
    white = (255, 255, 255)
    W, H = canvas.size
    sx, sy = d["safe_x"], d["safe_y"]
    sx2, sy2 = sx + d["safe_w"], sy + d["safe_h"]
    draw.rectangle((0, 0, W, sy), fill=white)              # top band
    draw.rectangle((0, sy2, W, H), fill=white)             # bottom band
    draw.rectangle((0, sy, sx, sy2), fill=white)           # left band
    draw.rectangle((sx2, sy, W, sy2), fill=white)          # right band
    return canvas


def _paste_transformed(canvas: "Image.Image", orig_img: "Image.Image",
                       transform: dict) -> None:
    """Composite one image onto an existing RGBA canvas under a center-anchored
    transform (full-res canvas px / degrees / bools):
      cx, cy   : where the image CENTER lands on the canvas
      scale    : multiplier on the image's natural pixel size (magnitude only)
      rotation : degrees, clockwise-positive (Konva); negated for PIL
      flipH, flipV : booleans
    Apply order: scale -> flip -> rotate -> place center at (cx, cy).
    """
    img = orig_img.convert("RGBA")

    # scale (magnitude)
    scale = abs(float(transform.get("scale", 1.0)))
    nw, nh = img.size
    img = img.resize((max(1, round(nw * scale)), max(1, round(nh * scale))),
                     Image.Resampling.LANCZOS)

    # flip
    if transform.get("flipH"):
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if transform.get("flipV"):
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

    # rotate (clockwise-positive -> PIL is counter-clockwise, so negate)
    rotation = float(transform.get("rotation", 0.0))
    if rotation:
        img = img.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)

    # place center
    cx = float(transform.get("cx", canvas.size[0] / 2))
    cy = float(transform.get("cy", canvas.size[1] / 2))
    x = round(cx - img.size[0] / 2)
    y = round(cy - img.size[1] / 2)
    canvas.alpha_composite(img, (x, y))


def render_with_transforms(images, d: dict, transforms,
                           guides: bool, blank_outside: bool = False) -> "Image.Image":
    """Composite one or more images onto the full KDP canvas. Images are pasted
    in order (first = bottom layer); transforms[i] applies to images[i]."""
    canvas = Image.new("RGBA", (d["total_w"], d["total_h"]), (255, 255, 255, 255))
    for img, t in zip(images, transforms):
        _paste_transformed(canvas, img, t)

    out = canvas.convert("RGB")
    if blank_outside:
        out = blank_outside_safe(out, d)
    if guides:
        out = draw_guides(out, d)
    return out


def render_with_transform(orig_img: "Image.Image", d: dict, transform: dict,
                          guides: bool, blank_outside: bool = False) -> "Image.Image":
    """Single-image convenience wrapper around render_with_transforms."""
    return render_with_transforms([orig_img], d, [transform], guides, blank_outside)


def build_cover(image_path: str, d: dict, guides: bool, output: str, do_autocrop: bool):
    img = check_image(image_path, d, do_autocrop)
    canvas = fit_image(img, (d["total_w"], d["total_h"]))
    assert canvas.size == (d["total_w"], d["total_h"]), "Canvas size mismatch after fit — aborting."

    if guides:
        canvas = draw_guides(canvas, d)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, dpi=(DPI, DPI))
    print(f"Saved: {output}  ({canvas.width}×{canvas.height} px @ {DPI} DPI)")


def main():
    parser = argparse.ArgumentParser(description="KDP Full-Cover Sizer")
    parser.add_argument("--image",  help="Input image path")
    parser.add_argument("--pages",  type=int, default=120, help="Page count (default 120)")
    parser.add_argument("--paper",  choices=SPINE_PER_PAGE.keys(), default="bw_white")
    parser.add_argument("--trim",   choices=TRIM_SIZES.keys(), default="6x9")
    parser.add_argument("--output", default=None, help="Output PNG path")
    parser.add_argument("--no-guides", action="store_true", help="Omit guide overlays")
    parser.add_argument("--no-autocrop", action="store_true",
                        help="Do not auto-crop white padding around the artwork")
    parser.add_argument("--info",   action="store_true", help="Print dimensions only")
    args = parser.parse_args()

    trim_w, trim_h = TRIM_SIZES[args.trim]
    d = calc_dims(trim_w, trim_h, args.pages, args.paper)
    print_info(d)

    if args.info:
        return

    if not args.image:
        parser.error("--image is required unless --info is used")

    output = args.output or str(
        Path(__file__).parent.parent / "output" / "cover_spread.png"
    )

    build_cover(args.image, d, guides=not args.no_guides, output=output,
                do_autocrop=not args.no_autocrop)


if __name__ == "__main__":
    main()
