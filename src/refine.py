"""Refine loop: render views, compare to the photo, ask the model for a better SCAD."""
import re
import shutil
import time
from pathlib import Path

from src.llm import ask
from src.prompts import CLEARANCE_RULES, hints_block
from src.render import RenderError, extract_scad, render, render_views

ROOT = Path(__file__).resolve().parent.parent
STOP_SCORE = 8
FIX_ATTEMPTS = 2

CRITIQUE_PROMPT = """You are refining a parametric OpenSCAD model of a real part so it matches the photo(s).

Images, in order: the original photo(s) of the real part, then three renders of the CURRENT model:
top-down, side, isometric. Renders use fixed cameras and plain flat colour; judge shape, not colour.

{hints}
{rules}

Current SCAD:
```openscad
{scad}
```

Curved/organic surfaces are expected. When the photo shows curves, do not use flat primitives:
build them with hull() of spheres/cylinders, rotate_extrude, minkowski, or polyhedron sweeps.

Reply in exactly this format:
DIFFERENCES:
- <one concrete difference per line: shape, curvature, proportions, missing features>
(write `- none` if there are no meaningful differences)
SCORE: <similarity of the render to the photo, integer 0-10>
{revise}"""

REVISE_PART = """Then ONE fenced ```openscad block with the full revised model. Keep parametric variables
at the top. Fix the differences you listed; do not change things that already match."""

SCORE_ONLY_PART = "Do not return any code."

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


def _no_changes(diffs):
    return not diffs or all(d.lower().rstrip(".") in ("none", "no differences") for d in diffs)


def _render_fixing(code, out_dir, stem, usage):
    """Render views for code; on OpenSCAD error ask the model to fix, up to FIX_ATTEMPTS times."""
    history = []
    for attempt in range(FIX_ATTEMPTS + 1):
        scad = out_dir / f"{stem}.scad"
        scad.write_text(code)
        try:
            return code, render_views(scad, out_dir)
        except RenderError as e:
            if attempt == FIX_ATTEMPTS:
                raise
            print(f"  {stem}: OpenSCAD error, asking model to fix (attempt {attempt + 1})")
            history += [{"role": "user", "content": "Return the OpenSCAD model."},
                        {"role": "assistant", "content": f"```openscad\n{code}```"}]
            text, rec = ask(FIX_PROMPT.format(err=e), history=history)
            usage.append(rec)
            code = extract_scad(text)


def refine(photo_paths, scad_code, hints="", max_iters=3, run_id=None):
    """Run the loop. Returns dict: run_dir, iterations [{n, score, diffs}], best, usage."""
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / "output" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    usage, iters, critique_md = [], [], ["# Critique log\n"]
    code, views = _render_fixing(scad_code, run_dir, "iter_0", usage)

    for n in range(max_iters + 1):
        last = n == max_iters
        prompt = CRITIQUE_PROMPT.format(
            hints=hints_block(hints), rules=CLEARANCE_RULES, scad=code,
            revise=SCORE_ONLY_PART if last else REVISE_PART)
        text, rec = ask(prompt, [*photo_paths, views["top"], views["side"], views["iso"]])
        usage.append(rec)
        diffs, score = parse_critique(text)
        iters.append({"n": n, "score": score, "diffs": diffs})
        print(f"iter_{n}: score={score} differences={len(diffs)}")
        critique_md.append(f"## iter_{n}: score {score}\n\n" + "\n".join(f"- {d}" for d in diffs) + "\n")
        (run_dir / "critique.md").write_text("\n".join(critique_md))

        if last or (score is not None and score >= STOP_SCORE) or _no_changes(diffs):
            break
        try:
            new_code = extract_scad(text)
        except ValueError:
            print("  no code in reply, stopping")
            break
        code, views = _render_fixing(new_code, run_dir, f"iter_{n + 1}", usage)

    scored = [i for i in iters if i["score"] is not None]
    best = max(scored, key=lambda i: (i["score"], i["n"])) if scored else iters[-1]
    final = run_dir / "final.scad"
    shutil.copy(run_dir / f"iter_{best['n']}.scad", final)
    render(final, run_dir)
    return {"run_dir": run_dir, "iterations": iters, "best": best["n"], "usage": usage}
