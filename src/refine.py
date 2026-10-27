"""Refine loop: render, judge, then revise the best model so far with one fix per round.

Each iteration is judged by:
- printability gate: the STL must be watertight with volume > 0, else score 0 and never best;
- silhouette IoU against a SAM mask of the top-down photo (when one is given);
- the model's own 0-10 similarity score.
final = 0.6 * IoU * 10 + 0.4 * model score (model score alone without a silhouette photo).
"""
import re
import shutil
import time
from pathlib import Path

from src.llm import ask
from src.printability import check_printable
from src.prompts import CLEARANCE_RULES, hints_block
from src.render import RenderError, extract_scad, render, render_stl, render_views
from src.silhouette import photo_mask, render_mask, silhouette_iou

ROOT = Path(__file__).resolve().parent.parent
STOP_SCORE = 8
FIX_ATTEMPTS = 2
IOU_WEIGHT = 0.6

SCORE_PROMPT = """You are judging a parametric OpenSCAD model of a real part against photos of the part.

Images, in order: the original photo(s) of the real part, then three renders of the model:
top-down, side, isometric. Renders use fixed cameras and plain flat colour; judge shape, not colour.

{hints}
Model SCAD:
```openscad
{scad}
```

Reply in exactly this format, and do not return any code:
DIFFERENCES:
- <one concrete difference per line: shape, curvature, proportions, missing features>
(write `- none` if there are no meaningful differences)
SCORE: <similarity of the render to the photo, integer 0-10>"""

REVISE_PROMPT = """You are refining a parametric OpenSCAD model of a real part so it matches the photo(s).

Images, in order: the original photo(s) of the real part, then three renders of the model below:
top-down, side, isometric. This is the best version so far, so keep what already works.

{hints}
{rules}

Model SCAD:
```openscad
{scad}
```

Known differences from the photo:
{diffs}
{rejected}
Pick the SINGLE most important difference and fix only that one. Do not rewrite the model:
make the smallest change that fixes it and leave every other line as it is. Curved/organic
surfaces need hull() of spheres/cylinders, rotate_extrude, minkowski or polyhedron sweeps, not
flat primitives. The result must stay a closed, printable solid.

Reply in exactly this format:
FIX: <one line: what you changed>
Then ONE fenced ```openscad block with the full model."""

REJECTED_PART = """These fixes were already tried on this model and did NOT improve it; pick a different
fix, or the same goal by a clearly different method:
{items}
"""

FIX_PROMPT = """OpenSCAD failed on your code with this error:

{err}

Return the corrected full model as ONE fenced ```openscad block."""


def parse_critique(text):
    """Return (differences list, score or None)."""
    diffs = []
    m = re.search(r"DIFFERENCES:\s*(.*?)(?:\nSCORE:|\Z)", text, re.S)
    if m:
        diffs = [ln.lstrip("- ").strip() for ln in m.group(1).splitlines() if ln.strip().startswith("-")]
    s = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)", text)
    return diffs, (float(s.group(1)) if s else None)


def parse_fix(text):
    m = re.search(r"FIX:\s*(.+)", text)
    return m.group(1).strip() if m else "(no FIX line)"


def _no_changes(diffs):
    return not diffs or all(d.lower().rstrip(".") in ("none", "no differences") for d in diffs)


def combine(iou, model_score):
    """Final score 0-10. None if the model gave no score."""
    if model_score is None:
        return None
    if iou is None:
        return model_score
    return round(IOU_WEIGHT * iou * 10 + (1 - IOU_WEIGHT) * model_score, 2)


def _render_fixing(code, out_dir, stem, usage):
    """Render views + STL; on OpenSCAD error ask the model to fix, up to FIX_ATTEMPTS times."""
    history = []
    for attempt in range(FIX_ATTEMPTS + 1):
        scad = out_dir / f"{stem}.scad"
        scad.write_text(code)
        try:
            views = render_views(scad, out_dir)
            return code, views, render_stl(scad, out_dir)
        except RenderError as e:
            if attempt == FIX_ATTEMPTS:
                raise
            print(f"  {stem}: OpenSCAD error, asking model to fix (attempt {attempt + 1})")
            history += [{"role": "user", "content": "Return the OpenSCAD model."},
                        {"role": "assistant", "content": f"```openscad\n{code}```"}]
            text, rec = ask(FIX_PROMPT.format(err=e), history=history)
            usage.append(rec)
            code = extract_scad(text)


def _evaluate(n, code, photo_paths, hints, run_dir, photo_m, usage):
    """Render and judge one iteration. Returns the iteration dict."""
    code, views, stl = _render_fixing(code, run_dir, f"iter_{n}", usage)
    it = {"n": n, "code": code, "views": views, "printable": check_printable(stl),
          "iou": None, "rot": None, "model": None, "diffs": [], "score": None}
    if not it["printable"].ok:
        it["score"] = 0.0  # gate failed: no model call, never best
        return it
    if photo_m is not None:
        it["iou"], it["rot"] = silhouette_iou(photo_m, render_mask(views["top"]))
    text, rec = ask(SCORE_PROMPT.format(hints=hints_block(hints), scad=code),
                    [*photo_paths, views["top"], views["side"], views["iso"]])
    usage.append(rec)
    it["diffs"], it["model"] = parse_critique(text)
    it["score"] = combine(it["iou"], it["model"])
    return it


def _critique_entry(it, best_n):
    iou = "n/a" if it["iou"] is None else f"{it['iou']:.3f} (render rotated {it['rot']}°)"
    lines = [f"## iter_{it['n']}: final {it['score']}" + ("  ← best" if it["n"] == best_n else ""), ""]
    if "base" in it:
        lines.append(f"- revised from: iter_{it['base']}")
        lines.append(f"- fix: {it['fix']}")
    lines += [f"- printability: {it['printable']}",
              f"- silhouette IoU: {iou}",
              f"- model score: {it['model']}", ""]
    lines += [f"- {d}" for d in it["diffs"]]
    return "\n".join(lines) + "\n"


def _is_better(it, best):
    if not it["printable"].ok or it["score"] is None:
        return False
    return best is None or it["score"] > best["score"]


def refine(photo_paths, scad_code, hints="", max_iters=3, run_id=None,
           silhouette_photo=None, sam_prompt="stove knob"):
    """Run the loop. Each round revises the best-scoring iteration so far.

    photo_paths: all photos shown to the model (put the silhouette photo first).
    silhouette_photo: top-down photo for the SAM IoU score, or None to skip it.
    Returns dict: run_dir, iterations [{n, score, iou, model, printable, diffs, ...}], best, usage.
    """
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / "output" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    usage, iters, rejected = [], [], []
    photo_m = photo_mask(silhouette_photo, sam_prompt) if silhouette_photo else None

    best = None
    for n in range(max_iters + 1):
        if n == 0:
            it = _evaluate(0, scad_code, photo_paths, hints, run_dir, photo_m, usage)
        else:
            base = best or iters[-1]  # nothing printable yet: keep working on the latest
            diffs = "\n".join(f"- {d}" for d in base["diffs"]) or (
                "- the STL is not a closed solid (not watertight); make it one" if not base["printable"].ok
                else "- (none listed)")
            rej = REJECTED_PART.format(items="\n".join(f"- {r}" for r in rejected)) if rejected else ""
            text, rec = ask(
                REVISE_PROMPT.format(hints=hints_block(hints), rules=CLEARANCE_RULES,
                                     scad=base["code"], diffs=diffs, rejected=rej),
                [*photo_paths, base["views"]["top"], base["views"]["side"], base["views"]["iso"]])
            usage.append(rec)
            try:
                new_code = extract_scad(text)
            except ValueError:
                print("  no code in reply, stopping")
                break
            fix = parse_fix(text)
            it = _evaluate(n, new_code, photo_paths, hints, run_dir, photo_m, usage)
            it.update(base=base["n"], fix=fix)

        iters.append(it)
        if _is_better(it, best):
            best, rejected = it, []
        elif "fix" in it:
            rejected.append(it["fix"])
        print(f"iter_{n}: final={it['score']} iou={it['iou']} model={it['model']} "
              f"printable={it['printable'].ok} best=iter_{best['n'] if best else None}")
        (run_dir / "critique.md").write_text(
            "# Critique log\n\n" + "\n".join(_critique_entry(i, best and best["n"]) for i in iters))

        if best and (best["score"] >= STOP_SCORE or _no_changes(best["diffs"])):
            break

    if best is None:
        raise RuntimeError(f"no printable iteration; see {run_dir / 'critique.md'}")
    final = run_dir / "final.scad"
    shutil.copy(run_dir / f"iter_{best['n']}.scad", final)
    render(final, run_dir)
    return {"run_dir": run_dir, "iterations": iters, "best": best["n"], "usage": usage}
