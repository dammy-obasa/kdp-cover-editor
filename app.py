import io
import json
import threading
import uuid
from pathlib import Path

from flask import (Flask, request, jsonify, send_file,
                   send_from_directory, abort)
from PIL import Image, ImageOps

from cover_sizer import (calc_dims, render_with_transforms,
                         TRIM_SIZES, SPINE_PER_PAGE, DPI)

BASE = Path(__file__).parent
STATIC = BASE / "static"
app = Flask(__name__, static_folder=None)


def _dims_from_params(pages: int, paper: str, trim: str) -> dict:
    if trim not in TRIM_SIZES:
        abort(400, f"unknown trim: {trim}")
    if paper not in SPINE_PER_PAGE:
        abort(400, f"unknown paper: {paper}")
    if pages <= 0:
        abort(400, "pages must be > 0")
    tw, th = TRIM_SIZES[trim]
    return calc_dims(tw, th, pages, paper)


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/static/<path:fn>")
def static_files(fn):
    return send_from_directory(STATIC, fn)


@app.after_request
def _no_cache(resp):
    # dev server: never serve stale HTML/JS/CSS so edits show up on plain reload
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/dimensions")
def dimensions():
    try:
        pages = int(request.args.get("pages", 120))
    except ValueError:
        abort(400, "pages must be an integer")
    paper = request.args.get("paper", "bw_white")
    trim = request.args.get("trim", "6x9")
    return jsonify(_dims_from_params(pages, paper, trim))


# in-memory upscale jobs: id -> {progress: int, result: bytes|None, error: str|None}
UPSCALE_JOBS = {}
_upscale_lock = threading.Lock()  # serialize: one upscale at a time (avoid CPU thrash)


def _run_upscale(job_id, im):
    job = UPSCALE_JOBS[job_id]
    if not _upscale_lock.acquire(blocking=False):
        job["error"] = "another optimization is already running — wait for it to finish"
        return
    try:
        from upscaler import upscale_4x
        out = upscale_4x(im, progress=lambda p: job.update(progress=p))
        buf = io.BytesIO()
        out.save(buf, format="PNG", dpi=(DPI, DPI))
        job["result"] = buf.getvalue()
        job["progress"] = 100
    except ImportError as e:
        job["error"] = (f"super-resolution dependencies not installed ({e}). "
                        f"Run setup.bat to install them.")
    except Exception as e:
        job["error"] = f"upscale failed: {e}"
    finally:
        _upscale_lock.release()


@app.post("/api/upscale")
def upscale():
    file = request.files.get("image")
    if not file:
        abort(400, "missing image file")
    try:
        im = Image.open(file.stream)
        im.load()
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception:
        abort(415, "unsupported or invalid image")

    job_id = uuid.uuid4().hex
    UPSCALE_JOBS[job_id] = {"progress": 0, "result": None, "error": None}
    threading.Thread(target=_run_upscale, args=(job_id, im), daemon=True).start()
    return jsonify({"job": job_id})


@app.get("/api/upscale/status")
def upscale_status():
    job = UPSCALE_JOBS.get(request.args.get("job", ""))
    if job is None:
        abort(404, "unknown job")
    return jsonify({"progress": job["progress"],
                    "done": job["result"] is not None,
                    "error": job["error"]})


@app.get("/api/upscale/result")
def upscale_result():
    job_id = request.args.get("job", "")
    job = UPSCALE_JOBS.get(job_id)
    if job is None or job["result"] is None:
        abort(404, "result not ready")
    buf = io.BytesIO(UPSCALE_JOBS.pop(job_id)["result"])  # free memory once fetched
    buf.seek(0)
    return send_file(buf, mimetype="image/png", as_attachment=False,
                     download_name="optimized.png")


@app.post("/api/render")
def render():
    files = request.files.getlist("image")
    if not files:
        abort(400, "missing image file")
    images = []
    for file in files:
        try:
            im = Image.open(file.stream)
            im.load()
            im = ImageOps.exif_transpose(im)  # honor EXIF orientation (matches browser preview)
        except Exception:
            abort(415, "unsupported or invalid image")
        images.append(im)

    try:
        transform = json.loads(request.form.get("transform", "[]"))
    except json.JSONDecodeError:
        abort(400, "invalid transform JSON")
    # accept a single transform dict (legacy) or a list, one per image
    transforms = transform if isinstance(transform, list) else [transform]
    if len(transforms) != len(images):
        abort(400, "transform count must match image count")

    try:
        pages = int(request.form.get("pages", 120))
    except ValueError:
        abort(400, "pages must be an integer")
    paper = request.form.get("paper", "bw_white")
    trim = request.form.get("trim", "6x9")
    guides = request.form.get("guides", "false").lower() == "true"
    blank = request.form.get("blank", "false").lower() == "true"
    fmt = request.form.get("format", "png").lower()
    if fmt not in ("png", "pdf"):
        abort(400, "format must be png or pdf")

    d = _dims_from_params(pages, paper, trim)
    out = render_with_transforms(images, d, transforms, guides, blank_outside=blank)
    assert out.size == (d["total_w"], d["total_h"]), "render size mismatch"

    buf = io.BytesIO()
    if fmt == "pdf":
        # resolution sets the PDF physical page size (px / dpi = inches)
        out.save(buf, format="PDF", resolution=float(DPI))
        mimetype, name = "application/pdf", "cover_spread.pdf"
    else:
        out.save(buf, format="PNG", dpi=(DPI, DPI))
        mimetype, name = "image/png", "cover_spread.png"
    buf.seek(0)
    return send_file(buf, mimetype=mimetype, as_attachment=True, download_name=name)


if __name__ == "__main__":
    # use_reloader=False: the reloader restarts the worker mid-request and
    # aborts long upscale calls (connection reset). Keep debug error pages.
    app.run(host="127.0.0.1", port=5050, debug=True, use_reloader=False)
