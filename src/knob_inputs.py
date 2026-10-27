"""Stove knob inputs shared by the spike and refine scripts."""
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

# Primary (top-down, used for the silhouette score) first, then context views.
PRIMARY = SAMPLES / "Knob top.jpeg"
CONTEXT = [SAMPLES / n for n in
           ("Knob under.jpeg", "Knob under 2.jpeg", "Knob side side.jpeg", "Knob side top.jpeg")]
PHOTOS = [PRIMARY, *CONTEXT]

HINTS = (
    "Stove knob, rim Ø ~42 mm, total height ~16 mm, rim ~5 mm thick with rounded edge.\n"
    "Grip: ~35 mm long bow-tie ridge across the face; BOTH long sides are concave, ends flare "
    "wider and blend down into the rim; domed top.\n"
    "Face slightly dished between grip and rim. Small round indicator dot on the rim at one grip end.\n"
    "Underside: hollow shell with two curved internal ribs; central round boss (~13 mm OD) with a "
    "D-shaft socket.\n"
    "Shaft: Ø6.0 mm D-shaft, 4.6 mm across the flat (estimated, not measured). "
    "Socket = shaft + clearance 0.3."
)
SAM_PROMPT = "stove knob"


def check_photos():
    missing = [str(p) for p in PHOTOS if not p.exists()]
    if missing:
        raise SystemExit("missing photos:\n  " + "\n  ".join(missing))
