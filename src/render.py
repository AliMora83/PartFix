"""Render a .scad file to .stl and .png with the OpenSCAD CLI (headless)."""
import shutil
import subprocess
from pathlib import Path

MAC_BIN = "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"


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


def render(scad_path, out_dir=None):
    """Return (stl_path, png_path). Raises RenderError with OpenSCAD's stderr."""
    scad = Path(scad_path)
    out = Path(out_dir) if out_dir else scad.parent
    out.mkdir(parents=True, exist_ok=True)
    stl, png = out / f"{scad.stem}.stl", out / f"{scad.stem}.png"
    exe = _bin()
    _run([exe, "-o", str(stl), str(scad)])
    _run([exe, "-o", str(png), "--imgsize=1024,768", "--autocenter", "--viewall",
          "--colorscheme=Tomorrow", str(scad)])
    return stl, png
