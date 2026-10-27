"""Printability gate: an STL must be a closed solid with positive volume."""
from dataclasses import dataclass

import trimesh


@dataclass
class Printability:
    watertight: bool
    volume: float

    @property
    def ok(self):
        return self.watertight and self.volume > 0

    def __str__(self):
        verdict = "PASS" if self.ok else "FAIL"
        return f"{verdict} (watertight={self.watertight}, volume={self.volume:.1f} mm³)"


def check_printable(stl_path):
    try:
        mesh = trimesh.load(str(stl_path), force="mesh")
    except Exception:  # unreadable/empty STL is not printable
        return Printability(False, 0.0)
    if mesh.is_empty:
        return Printability(False, 0.0)
    return Printability(bool(mesh.is_watertight), float(mesh.volume))
