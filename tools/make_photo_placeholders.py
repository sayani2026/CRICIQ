"""Create the 'Player Image' folder: one placeholder PDF per ranked player, named exactly as the dashboard expects.

    python tools/make_photo_placeholders.py

Each placeholder (e.g.  viratkohliimage.pdf ) contains only text, so the card keeps its monogram. Replace it with
the player's photo under the same name — viratkohliimage.jpg / .png / .webp, or a PDF that contains the picture —
and the card shows the photo. Existing files are never overwritten. Run again after the pipeline to add new players.
"""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A6
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))
logging.getLogger("streamlit").setLevel(logging.ERROR)
from components.cards import file_name, key_of  # noqa: E402

FOLDER = ROOT / "Player Image"
EXTS = (".jpg", ".jpeg", ".png", ".webp", ".pdf")
HOWTO = """HOW TO ADD PLAYER PHOTOS
========================

1. Find the player's file in this folder, e.g.  viratkohliimage.pdf  (a placeholder with no picture).
2. Save a photo of that player that you have the right to use, with the SAME name:
       viratkohliimage.jpg    (or .jpeg / .png / .webp)
   A PDF that contains the photo also works: viratkohliimage.pdf
3. Delete the placeholder PDF if you saved a .jpg/.png/.webp (an image always wins over a PDF anyway).
4. Refresh the dashboard. The photo appears on the player's card (square-cropped, faces kept near the top).

Tips
- Name = the player's name in lower case, no spaces, then "image":  Tim David -> timdavidimage.jpg
  (player_list.csv has every exact file name.)
- Portrait photos with the face in the upper half look best. Up to 15 MB per file.
- No photo? The card shows an animated monogram instead.
"""


def placeholder(path: Path, name: str, team: str):
    c = canvas.Canvas(str(path), pagesize=A6)
    w, h = A6
    c.setFillColorRGB(0.04, 0.08, 0.2)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setFillColorRGB(0.92, 0.1, 0.52)
    c.rect(0, h - 8, w, 8, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(w / 2, h - 60, name)
    c.setFont("Helvetica", 9)
    c.drawCentredString(w / 2, h - 76, team)
    c.setFont("Helvetica", 8.5)
    lines = [
        "CRICQ photo placeholder",
        "",
        "Replace this file with the player's photo",
        "using the same name:",
        file_name(name, ".jpg"),
        "(.jpeg, .png, .webp or a PDF with the picture",
        "also work). Then refresh the dashboard.",
    ]
    y = h / 2 + 20
    for ln in lines:
        c.drawCentredString(w / 2, y, ln)
        y -= 13
    c.save()


def main():
    out = ROOT / "outputs"
    frames = [pd.read_csv(out / f) for f in ("batting_scores.csv", "bowling_scores.csv") if (out / f).exists()]
    if not frames:
        sys.exit("Run the pipeline first (outputs/*_scores.csv not found).")
    t = pd.concat(frames)
    t = t[t["rank"].notna()].sort_values("clutch_score", ascending=False).drop_duplicates("player_id")
    FOLDER.mkdir(exist_ok=True)
    (FOLDER / "HOW_TO_ADD_PHOTOS.txt").write_text(HOWTO, encoding="utf-8")
    have = {key_of(p.stem) for p in FOLDER.iterdir() if p.suffix.lower() in EXTS}
    made = 0
    rows = []
    for r in t.itertuples():
        team = str(r.team_label) if pd.notna(r.team_label) else ""
        rows.append([r.display_name, team, file_name(r.display_name, ".jpg"), file_name(r.display_name, ".pdf")])
        if key_of(r.display_name) not in have:
            placeholder(FOLDER / file_name(r.display_name, ".pdf"), r.display_name, team)
            made += 1
    with open(FOLDER / "player_list.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["player", "team", "save_photo_as", "or_pdf_as"])
        w.writerows(sorted(rows))
    print(f"'Player Image' folder: {len(rows)} players, {made} new placeholder(s), existing files left untouched.")


if __name__ == "__main__":
    main()
