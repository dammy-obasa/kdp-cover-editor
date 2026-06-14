"""Real-ESRGAN x4 super-resolution, isolated so its heavy deps (torch,
basicsr, realesrgan) load lazily on first use — the web app boots without them.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image

TILE = 512  # tile edge in px; also the unit of progress reporting

# realesr-general-x4v3: compact SRVGG net, far faster than RRDBNet x4plus on CPU
WEIGHTS_URL = ("https://github.com/xinntao/Real-ESRGAN/releases/download/"
               "v0.2.5.0/realesr-general-x4v3.pth")
WEIGHTS_DIR = Path(__file__).parent / "weights"

_upsampler = None  # built once, then reused


def _get_upsampler():
    global _upsampler
    if _upsampler is not None:
        return _upsampler

    # basicsr (a realesrgan dependency) imports
    # torchvision.transforms.functional_tensor, which was removed in
    # torchvision >= 0.17. Alias it to functional before importing basicsr.
    import sys
    import torchvision.transforms.functional as _F
    sys.modules.setdefault("torchvision.transforms.functional_tensor", _F)

    from basicsr.archs.srvgg_arch import SRVGGNetCompact
    from basicsr.utils.download_util import load_file_from_url
    from realesrgan import RealESRGANer

    # SRVGGNetCompact = the realesr-general-x4v3 architecture (lightweight)
    model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64,
                            num_conv=32, upscale=4, act_type="prelu")
    WEIGHTS_DIR.mkdir(exist_ok=True)
    model_path = load_file_from_url(WEIGHTS_URL, model_dir=str(WEIGHTS_DIR))
    # tile keeps memory bounded on large covers; half precision needs CUDA, so off.
    _upsampler = RealESRGANer(scale=4, model_path=model_path, model=model,
                              tile=TILE, tile_pad=10, pre_pad=0, half=False)
    return _upsampler


def upscale_4x(im: Image.Image, progress=None) -> Image.Image:
    """Return a 4x super-resolved RGB copy of `im`.

    `progress`, if given, is called with an integer percent 0..100. The model
    runs once per tile, so we count those calls against the estimated tile total.
    """
    up = _get_upsampler()
    arr = np.array(im.convert("RGB"))

    if progress is None:
        out, _ = up.enhance(arr, outscale=4)
        return Image.fromarray(out)

    h, w = arr.shape[:2]
    total = max(1, math.ceil(w / TILE) * math.ceil(h / TILE))
    model = up.model
    orig_forward = model.forward
    state = {"n": 0}

    def counting_forward(*a, **k):
        state["n"] += 1
        progress(min(99, round(100 * state["n"] / total)))  # 100 set by caller on success
        return orig_forward(*a, **k)

    model.forward = counting_forward
    try:
        out, _ = up.enhance(arr, outscale=4)
    finally:
        model.forward = orig_forward
    progress(100)
    return Image.fromarray(out)
