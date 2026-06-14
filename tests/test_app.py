from app import app


def test_dimensions_120():
    client = app.test_client()
    r = client.get("/api/dimensions?pages=120&paper=bw_white&trim=6x9")
    assert r.status_code == 200
    j = r.get_json()
    assert j["total_w"] == 3757 and j["total_h"] == 2776
    assert j["spine_px"] == 81


def test_dimensions_250_wider_spine():
    client = app.test_client()
    r = client.get("/api/dimensions?pages=250&paper=bw_white&trim=6x9")
    j = r.get_json()
    assert j["spine_px"] == 169


def test_dimensions_bad_trim():
    client = app.test_client()
    r = client.get("/api/dimensions?trim=9x9")
    assert r.status_code == 400


import io
import json
from PIL import Image


def test_render_endpoint_returns_png_at_canvas_size():
    client = app.test_client()
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (10, 20, 30)).save(buf, format="PNG")
    buf.seek(0)
    data = {
        "transform": json.dumps({"cx": 1878, "cy": 1388, "scale": 5.0}),
        "pages": "120", "paper": "bw_white", "trim": "6x9", "guides": "false",
        "image": (buf, "x.png"),
    }
    r = client.post("/api/render", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    assert r.mimetype == "image/png"
    out = Image.open(io.BytesIO(r.data))
    assert out.size == (3757, 2776)


def test_render_endpoint_missing_image():
    client = app.test_client()
    r = client.post("/api/render", data={"transform": "{}"},
                    content_type="multipart/form-data")
    assert r.status_code == 400
