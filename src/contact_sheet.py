"""Contact sheet: photo + iso (row 1), SAM mask + top (row 2) renders of every iteration."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CELL = (480, 360)
LABEL_H = 34
BG = (248, 248, 248)


def _fit(path):
    im = Image.open(path).convert("RGB")
    im.thumbnail(CELL)
    cell = Image.new("RGB", CELL, BG)
    cell.paste(im, ((CELL[0] - im.width) // 2, (CELL[1] - im.height) // 2))
    return cell


def _scores(it):
    if not it["printable"].ok:
        return "NOT PRINTABLE  score 0"
    iou = "n/a" if it["iou"] is None else f"{it['iou']:.2f}"
    return f"final {it['score']}  IoU {iou}  model {it['model']}"


def make_sheet(photo, run_dir, iterations, best=None, mask=None, out_path=None):
    """iterations from refine(); best: its best n; mask: SAM mask PNG of the photo.

    Returns the PNG path."""
    run_dir = Path(run_dir)
    font = ImageFont.load_default(size=17)
    cols = 1 + len(iterations)
    w, h = CELL[0], CELL[1] + LABEL_H
    sheet = Image.new("RGB", (cols * w, 2 * h), BG)
    d = ImageDraw.Draw(sheet)

    def put(col, row, path, label):
        sheet.paste(_fit(path), (col * w, row * h + LABEL_H))
        d.text((col * w + 10, row * h + 6), label, fill=(20, 20, 20), font=font)

    put(0, 0, photo, "photo")
    if mask:
        put(0, 1, mask, "SAM mask")
    for i, it in enumerate(iterations, start=1):
        tag = "  [BEST]" if it["n"] == best else ""
        put(i, 0, run_dir / f"iter_{it['n']}_iso.png", f"iter_{it['n']}{tag}  {_scores(it)}")
        put(i, 1, run_dir / f"iter_{it['n']}_top.png", f"iter_{it['n']} top")
    out = Path(out_path) if out_path else run_dir / "contact_sheet.png"
    sheet.save(out)
    return out
