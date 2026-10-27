"""Silhouette score: IoU between the part's mask in a top-down photo and the top-down render.

The photo mask comes from SAM 3.1 (Meta Model API) and is cached per photo + prompt, so it
is computed once. The render mask is a background threshold of the OpenSCAD top view.
"""
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "output" / "sam_cache"
SIDE = 256          # both masks are scaled into a SIDE x SIDE square before IoU
ROT_STEP = 5        # degrees; the knob's rotation about its axis is arbitrary
BG_TOL = 12         # max per-channel distance from the corner colour to count as background


def _cache_path(photo, prompt):
    digest = hashlib.sha1(Path(photo).read_bytes() + prompt.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{Path(photo).stem}-{digest}.png"


def segment_photo(photo, prompt):
    """SAM 3.1 mask of `prompt` in `photo` as a bool array. Not wired up yet: the request
    shape is waiting on confirmation."""
    raise NotImplementedError("SAM 3.1 call not implemented yet")


def photo_mask(photo, prompt="stove knob"):
    """Cached SAM mask (bool HxW) for a photo."""
    path = _cache_path(photo, prompt)
    if path.exists():
        return np.array(Image.open(path).convert("L")) > 127
    mask = segment_photo(photo, prompt)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask.astype(np.uint8) * 255).save(path)
    return mask


def render_mask(png):
    """Foreground of an OpenSCAD render: anything not close to the corner (background) colour."""
    im = np.asarray(Image.open(png).convert("RGB")).astype(int)
    bg = np.median(np.stack([im[0, 0], im[0, -1], im[-1, 0], im[-1, -1]]), axis=0)
    return np.abs(im - bg).max(axis=2) > BG_TOL


def _normalise(mask):
    """Crop to the bounding box, pad to a square around it, scale to SIDE x SIDE."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return np.zeros((SIDE, SIDE), bool)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    n = max(h, w)
    sq = np.zeros((n, n), bool)
    sq[(n - h) // 2:(n - h) // 2 + h, (n - w) // 2:(n - w) // 2 + w] = crop
    im = Image.fromarray(sq.astype(np.uint8) * 255).resize((SIDE, SIDE), Image.BILINEAR)
    return np.asarray(im) > 127


def iou(a, b):
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def silhouette_iou(photo_m, render_m):
    """Best IoU over rotations of the render about its centre (bbox-aligned, same size).

    Returns (iou, degrees)."""
    target = _normalise(photo_m)
    src = Image.fromarray(render_m.astype(np.uint8) * 255)
    best = (0.0, 0)
    for deg in range(0, 360, ROT_STEP):
        rot = np.asarray(src.rotate(deg, expand=True)) > 127
        best = max(best, (iou(target, _normalise(rot)), deg))
    return best
