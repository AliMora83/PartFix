"""Render a .scad file to .stl and .png with the OpenSCAD CLI (headless)."""
import re
import shutil
import subprocess
from pathlib import Path

MAC_BIN = "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"

# Fixed cameras: translate x,y,z, rotate x,y,z (OpenSCAD --camera form). --viewall sets distance.
VIEWS = {
    "top": "0,0,0,0,0,0,200",
    "side": "0,0,0,90,0,0,200",
    "iso": "0,0,0,55,0,25,200",
}
IMG_ARGS = ["--imgsize=1024,768", "--projection=o", "--autocenter", "--viewall",
            "--colorscheme=Tomorrow"]


class RenderError(RuntimeError):
    pass


def _bin():
    exe = shutil.which("openscad") or (MAC_BIN if Path(MAC_BIN).exists() else None)
    if not exe:
        raise RenderError("OpenSCAD not found: install it or put `openscad` on PATH")
    return exe


def _run(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        raise RenderError(f"OpenSCAD failed ({p.returncode}):\n{p.stderr.strip()}")
    return p.stderr


def extract_scad(text):
    """First fenced code block in a model reply."""
    m = re.findall(r"```(?:openscad|scad)?\s*\n(.*?)```", text, re.S)
    if not m:
        raise ValueError("no fenced code block in model reply")
    return m[0].strip() + "\n"


def render(scad_path, out_dir=None):
    """Return (stl_path, png_path). Raises RenderError with OpenSCAD's stderr."""
    scad = Path(scad_path)
    out = Path(out_dir) if out_dir else scad.parent
    out.mkdir(parents=True, exist_ok=True)
    stl, png = render_stl(scad, out), out / f"{scad.stem}.png"
    _run([_bin(), "-o", str(png), *IMG_ARGS, str(scad)])
    return stl, png


def render_stl(scad_path, out_dir=None):
    """Return the stl path. Raises RenderError with OpenSCAD's stderr."""
    scad = Path(scad_path)
    out = Path(out_dir) if out_dir else scad.parent
    out.mkdir(parents=True, exist_ok=True)
    stl = out / f"{scad.stem}.stl"
    _run([_bin(), "-o", str(stl), str(scad)])
    return stl


def render_views(scad_path, out_dir=None):
    """Render top/side/iso PNGs with identical lighting and background.

    Returns {view: png_path}, files named <stem>_<view>.png.
    """
    scad = Path(scad_path)
    out = Path(out_dir) if out_dir else scad.parent
    out.mkdir(parents=True, exist_ok=True)
    exe = _bin()
    paths = {}
    for view, cam in VIEWS.items():
        png = out / f"{scad.stem}_{view}.png"
        _run([exe, "-o", str(png), f"--camera={cam}", *IMG_ARGS, str(scad)])
        paths[view] = png
    return paths
