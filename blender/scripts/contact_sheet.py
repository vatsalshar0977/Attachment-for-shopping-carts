#!/usr/bin/env python3
"""Tile the rendered views into one contact sheet for quick review.

Usage:
    python3 scripts/contact_sheet.py [output.png] [cell_width]
"""

import os
import sys

from PIL import Image, ImageDraw

RENDERS = "blender/exports/renders"
ORDER = ["01_hero", "02_contact", "03_profile", "04_top",
         "05_underside", "06_detail", "07_on_cart", "08_cart_wide"]
LABELS = {
    "01_hero": "hero 3/4",
    "02_contact": "contact face",
    "03_profile": "end profile",
    "04_top": "top",
    "05_underside": "underside / snap slot",
    "06_detail": "detail",
    "07_on_cart": "mounted on cart",
    "08_cart_wide": "cart context",
}


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = os.path.join(root, RENDERS)
    cell = int(sys.argv[2]) if len(sys.argv) > 2 else 480
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(src, "contact_sheet.png")

    names = [n for n in ORDER if os.path.exists(os.path.join(src, n + ".png"))]
    if not names:
        sys.exit(f"no renders found in {src}")

    first = Image.open(os.path.join(src, names[0] + ".png"))
    aspect = first.height / first.width
    cw = cell
    ch = int(cell * aspect)
    cols = min(2, len(names))
    rows = (len(names) + cols - 1) // cols
    pad, bar = 8, 26

    sheet = Image.new("RGB", (cols * (cw + pad) + pad, rows * (ch + bar + pad) + pad), (28, 30, 34))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        im = Image.open(os.path.join(src, name + ".png")).resize((cw, ch))
        x = pad + (i % cols) * (cw + pad)
        y = pad + (i // cols) * (ch + bar + pad)
        sheet.paste(im, (x, y))
        draw.text((x + 4, y + ch + 6), LABELS.get(name, name), fill=(215, 218, 224))

    sheet.save(out)
    print(f"{out}  ({sheet.width}x{sheet.height}, {len(names)} views)")


if __name__ == "__main__":
    main()
