"""Spike: stove knob photo -> Muse Spark -> OpenSCAD -> STL + PNG."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.knob_inputs import HINTS, PHOTOS, check_photos  # noqa: E402
from src.llm import ask  # noqa: E402
from src.prompts import CLEARANCE_RULES, hints_block  # noqa: E402
from src.render import RenderError, extract_scad, render  # noqa: E402

SCAD = ROOT / "output" / "spike_knob.scad"
MAX_ATTEMPTS = 2

PROMPT = """These photos show a stove knob (first: top-down; then underside and side views). Do three things:
(a) Describe the knob's geometry (body shape, grip, skirt, pointer/indicator, shaft socket).
(b) Estimate dimensions in mm, using the user's dimensions above where given.
(c) Return ONE fenced ```openscad code block that models the knob. It must be parametric, with
    all dimensions as variables at the top, including `shaft_d` and `shaft_flat` (the
    across-the-flat distance of the D). Use only built-in OpenSCAD."""

FIX = """OpenSCAD failed on your code with this error:

{err}

Return the corrected full model as ONE fenced ```openscad block."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hints", default=HINTS, help="your own description of the part")
    check_photos()
    prompt = hints_block(ap.parse_args().hints) + PROMPT + "\n\n" + CLEARANCE_RULES
    total_in = total_out = 0
    text, rec = ask(prompt, PHOTOS)
    history = [{"role": "user", "content": prompt}]  # images omitted from retries
    print(text.split("```")[0].strip(), "\n")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        total_in += rec["input_tokens"] or 0
        total_out += rec["output_tokens"] or 0
        SCAD.parent.mkdir(exist_ok=True)
        SCAD.write_text(extract_scad(text))
        try:
            stl, png = render(SCAD)
            break
        except RenderError as e:
            print(f"attempt {attempt} failed:\n{e}\n")
            if attempt == MAX_ATTEMPTS:
                sys.exit(1)
            history.append({"role": "assistant", "content": text})
            text, rec = ask(FIX.format(err=e), history=history)
    print(f"scad: {SCAD}\nstl:  {stl}\npng:  {png}")
    print(f"tokens: input={total_in} output={total_out} (see logs/usage.jsonl)")


if __name__ == "__main__":
    main()
