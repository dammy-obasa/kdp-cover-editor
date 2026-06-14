from PIL import Image
from cover_sizer import calc_dims, render_with_transform

DIMS = calc_dims(6.0, 9.0, 120, "bw_white")  # total 3757 x 2776
CX, CY = DIMS["total_w"] / 2, DIMS["total_h"] / 2


def test_render_fills_canvas_size():
    img = Image.new("RGB", (DIMS["total_w"], DIMS["total_h"]), (200, 30, 30))
    out = render_with_transform(img, DIMS, {"cx": CX, "cy": CY, "scale": 1.0}, guides=False)
    assert out.size == (DIMS["total_w"], DIMS["total_h"])
    assert out.getpixel((int(CX), int(CY))) == (200, 30, 30)


def test_render_scale_half_leaves_white_corner():
    img = Image.new("RGB", (DIMS["total_w"], DIMS["total_h"]), (0, 0, 0))
    out = render_with_transform(img, DIMS, {"cx": CX, "cy": CY, "scale": 0.5}, guides=False)
    assert out.getpixel((0, 0)) == (255, 255, 255)          # uncovered -> white
    assert out.getpixel((int(CX), int(CY))) == (0, 0, 0)    # center covered


def test_render_fliph_swaps_sides():
    w, h = DIMS["total_w"], DIMS["total_h"]
    img = Image.new("RGB", (w, h), (255, 255, 255))
    img.paste(Image.new("RGB", (w // 2, h), (0, 0, 0)), (0, 0))  # black left half
    out = render_with_transform(img, DIMS, {"cx": CX, "cy": CY, "scale": 1.0, "flipH": True}, guides=False)
    assert out.getpixel((w - 5, h // 2)) == (0, 0, 0)        # black now on right
    assert out.getpixel((5, h // 2)) == (255, 255, 255)


def test_blank_outside_whites_perimeter_keeps_safe_area():
    img = Image.new("RGB", (DIMS["total_w"], DIMS["total_h"]), (200, 30, 30))
    out = render_with_transform(img, DIMS, {"cx": CX, "cy": CY, "scale": 1.0},
                                guides=False, blank_outside=True)
    # corner (outside safe area) blanked to white
    assert out.getpixel((0, 0)) == (255, 255, 255)
    # center of safe area still shows the image
    sx, sy = DIMS["safe_x"], DIMS["safe_y"]
    assert out.getpixel((sx + DIMS["safe_w"] // 2, sy + DIMS["safe_h"] // 2)) == (200, 30, 30)


def test_guides_change_output():
    img = Image.new("RGB", (DIMS["total_w"], DIMS["total_h"]), (255, 255, 255))
    base = {"cx": CX, "cy": CY, "scale": 1.0}
    a = render_with_transform(img, DIMS, base, guides=False)
    b = render_with_transform(img, DIMS, base, guides=True)
    assert list(a.getdata()) != list(b.getdata())
