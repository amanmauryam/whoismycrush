"""Generate the static social share card (static/img/og-default.png).

Run once after editing the brand copy:

    python scripts/make_og_image.py

Kept in the repo so the share image is reproducible and never drifts from the
brand palette in design.md.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
OUT = BASE_DIR / "static" / "img" / "og-default.png"

PAPER = (247, 246, 241)
INK = (17, 17, 17)
RED = (255, 92, 92)
YELLOW = (255, 240, 90)

WIDTH, HEIGHT = 1200, 630


def _font(size: int, bold: bool = True):
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(img)

    # faint graph-paper grid
    for x in range(0, WIDTH, 44):
        for y in range(0, HEIGHT, 44):
            draw.point((x, y), fill=(225, 222, 212))

    # thick notice-board border
    for offset in range(3):
        draw.rectangle(
            [24 + offset, 24 + offset, WIDTH - 24 - offset, HEIGHT - 24 - offset],
            outline=INK,
        )

    draw.text((70, 90), "WHO IS MY", font=_font(120), fill=INK)
    draw.text((70, 220), "CRUSH?", font=_font(150), fill=INK)

    draw.text((74, 400), "You might be someone's crush too.", font=_font(44, False), fill=INK)

    # brand chip
    draw.rectangle([70, 470, 470, 545], fill=YELLOW, outline=INK, width=3)
    draw.text((95, 487), "whoismycrush", font=_font(40), fill=INK)

    # red circle with a question mark, right side
    cx, cy, r = 950, 250, 150
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED, outline=INK, width=4)
    draw.text((cx - 45, cy - 95), "?", font=_font(190), fill=(255, 255, 255))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
