"""Contact sheet: photo + iso (row 1) and top (row 2) renders of every iteration."""
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


def make_sheet(photo, run_dir, iterations, out_path=None):
    """iterations: [{n, score}] from refine(). Returns the PNG path."""
    run_dir = Path(run_dir)
    font = ImageFont.load_default(size=20)
    cols = 1 + len(iterations)
    w, h = CELL[0], CELL[1] + LABEL_H
    sheet = Image.new("RGB", (cols * w, 2 * h), BG)
    d = ImageDraw.Draw(sheet)

    def put(col, row, path, label):
        sheet.paste(_fit(path), (col * w, row * h + LABEL_H))
        d.text((col * w + 10, row * h + 6), label, fill=(20, 20, 20), font=font)

    put(0, 0, photo, "photo")
    for i, it in enumerate(iterations, start=1):
        score = "n/a" if it["score"] is None else f"{it['score']:g}/10"
        put(i, 0, run_dir / f"iter_{it['n']}_iso.png", f"iter_{it['n']} iso  score {score}")
        put(i, 1, run_dir / f"iter_{it['n']}_top.png", f"iter_{it['n']} top")
    out = Path(out_path) if out_path else run_dir / "contact_sheet.png"
    sheet.save(out)
    return out
