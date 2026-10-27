"""Shaft fit coupon: 2 mm plate with D-holes of different sizes, each labelled. No API calls."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.printability import check_printable  # noqa: E402
from src.render import render  # noqa: E402

OUT = ROOT / "output" / "shaft_coupon.scad"

# (diameter, across-flat) in mm, printed as labelled.
HOLES = [(6.2, 4.6), (6.3, 4.7), (6.4, 4.8), (6.3, 4.6), (6.4, 4.7), (6.5, 4.9)]

SCAD = """// Shaft fit coupon: print, then try each D-hole on the stove shaft.
// Label = hole diameter / across-flat distance, in mm, as modelled (no extra clearance).
plate_t = 2;        // plate thickness
engrave = 0.6;      // text depth
pitch_x = 17;       // hole spacing
pitch_y = 19;
cols = 3;
margin = 3;
text_size = 3;
text_gap = 6.5;     // hole centre to label baseline
$fn = 96;

holes = [{holes}];

module d_hole(d, flat) {{
    // circle of diameter d, cut flat so that flat-to-far-side = flat
    intersection() {{
        circle(d = d);
        translate([-d / 2, -d / 2]) square([d, flat]);
    }}
}}

rows = len(holes) / cols;
// hole centre; its label sits text_gap below it in the same cell
function pos(i) = [margin + (i % cols) * pitch_x + pitch_x / 2,
                   margin + (rows - floor(i / cols)) * pitch_y - 7];

plate_w = 2 * margin + cols * pitch_x;
plate_h = 2 * margin + rows * pitch_y;

difference() {{
    cube([plate_w, plate_h, plate_t]);
    for (i = [0 : len(holes) - 1]) {{
        d = holes[i][0];
        f = holes[i][1];
        translate([pos(i)[0], pos(i)[1], -1])
            linear_extrude(plate_t + 2) d_hole(d, f);
        translate([pos(i)[0], pos(i)[1] - text_gap - text_size / 2, plate_t - engrave])
            linear_extrude(engrave + 1)
                text(str(d, "/", f), size = text_size, halign = "center", valign = "center",
                     font = "Liberation Sans:style=Bold");
    }}
}}
"""


def main():
    holes = ", ".join(f"[{d}, {f}]" for d, f in HOLES)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(SCAD.format(holes=holes))
    stl, png = render(OUT)
    ok = check_printable(stl)
    print(f"scad: {OUT}\nstl:  {stl}\npng:  {png}\nprintable: {ok}")


if __name__ == "__main__":
    main()
