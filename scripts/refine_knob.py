"""Refine the knob: render, judge (printability, SAM silhouette IoU, model score), revise the best."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.contact_sheet import make_sheet  # noqa: E402
from src.knob_inputs import HINTS, PHOTOS, PRIMARY, SAM_PROMPT, check_photos  # noqa: E402
from src.refine import refine  # noqa: E402
from src.silhouette import _cache_path  # noqa: E402

START = ROOT / "output" / "spike_knob.scad"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hints", default=HINTS, help="your own description of the part")
    ap.add_argument("--iters", type=int, default=3)
    ap.add_argument("--start", type=Path, default=START, help="starting SCAD (run spike_knob.py first)")
    ap.add_argument("--no-silhouette", action="store_true", help="skip the SAM IoU score")
    args = ap.parse_args()
    check_photos()

    sil = None if args.no_silhouette else PRIMARY
    res = refine(PHOTOS, args.start.read_text(), args.hints, max_iters=args.iters,
                 silhouette_photo=sil, sam_prompt=SAM_PROMPT)
    mask = _cache_path(PRIMARY, SAM_PROMPT) if sil else None
    sheet = make_sheet(PRIMARY, res["run_dir"], res["iterations"], best=res["best"], mask=mask)
    tin = sum(u["input_tokens"] or 0 for u in res["usage"])
    tout = sum(u["output_tokens"] or 0 for u in res["usage"])
    for i in res["iterations"]:
        print(f"iter_{i['n']}: final={i['score']} iou={i['iou']} model={i['model']} "
              f"printable={i['printable']}")
    print(f"best: iter_{res['best']}  final: {res['run_dir']}/final.scad (+ .stl)")
    print(f"contact sheet: {sheet}")
    print(f"tokens: input={tin} output={tout} over {len(res['usage'])} calls")


if __name__ == "__main__":
    main()
