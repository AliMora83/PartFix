"""Refine the spike knob: render, compare to photo, revise."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.contact_sheet import make_sheet  # noqa: E402
from src.refine import refine  # noqa: E402

PHOTO = ROOT / "samples" / "knob.jpeg"
START = ROOT / "output" / "spike_knob.scad"

HINTS = (
    "Stove knob. The grip is NOT a straight bar: it is a curved, sweeping ridge that arcs across "
    "the face like a wave/crescent, with a domed top and one concave curved side. The grip ends "
    "blend down into the rim. The knob face is slightly dished between the grip and the rim. The "
    "rim has a rounded edge. Small round indicator dot on the rim. 6 mm D-shaft socket underneath."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hints", default=HINTS, help="your own description of the part")
    ap.add_argument("--iters", type=int, default=3)
    args = ap.parse_args()

    res = refine([PHOTO], START.read_text(), args.hints, max_iters=args.iters)
    sheet = make_sheet(PHOTO, res["run_dir"], res["iterations"])
    tin = sum(u["input_tokens"] or 0 for u in res["usage"])
    tout = sum(u["output_tokens"] or 0 for u in res["usage"])
    print("scores:", {f"iter_{i['n']}": i["score"] for i in res["iterations"]})
    print(f"best: iter_{res['best']}  final: {res['run_dir']}/final.scad (+ .stl)")
    print(f"contact sheet: {sheet}")
    print(f"tokens: input={tin} output={tout} over {len(res['usage'])} calls")


if __name__ == "__main__":
    main()
