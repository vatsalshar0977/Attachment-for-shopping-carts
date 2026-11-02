#!/usr/bin/env python3
"""Tile the deployed, folding, and stowed renders for quick review.

Usage:
    python3 blender/scripts/contact_sheet.py [output.png] [cell_width]
"""

import os
import sys

from PIL import Image, ImageDraw

RENDERS = "blender/exports/renders"
ORDER = ["01_deployed_hero", "02_deployed_front", "03_hinge_detail",
         "04_deployed_on_cart", "05_stowed_in_basket", "06_stowed_context",
         "07_mid_fold", "08_stowed_top"]
LABELS = {
    "01_deployed_hero": "deployed · padded leaning face",
    "02_deployed_front": "deployed · full width",
    "03_hinge_detail": "handle clamps and hinge locks",
    "04_deployed_on_cart": "deployed · on cart",
    "05_stowed_in_basket": "stowed · inside basket",
    "06_stowed_context": "stowed · cart context",
    "07_mid_fold": "mid-fold animation pose",
    "08_stowed_top": "stowed · basket top view",
}


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    source = os.path.join(root, RENDERS)
    cell = int(sys.argv[2]) if len(sys.argv) > 2 else 480
    output = sys.argv[1] if len(sys.argv) > 1 else os.path.join(source, "contact_sheet.png")
    names = [name for name in ORDER if os.path.exists(os.path.join(source, name + ".png"))]
    if not names:
        sys.exit(f"no renders found in {source}")

    first = Image.open(os.path.join(source, names[0] + ".png"))
    aspect = first.height / first.width
    cw, ch = cell, int(cell * aspect)
    columns = min(2, len(names))
    rows = (len(names) + columns - 1) // columns
    pad, label_height = 8, 30
    sheet = Image.new("RGB", (columns * (cw + pad) + pad,
                               rows * (ch + label_height + pad) + pad), (28, 30, 34))
    draw = ImageDraw.Draw(sheet)
    for index, name in enumerate(names):
        image = Image.open(os.path.join(source, name + ".png")).convert("RGB").resize((cw, ch))
        x = pad + (index % columns) * (cw + pad)
        y = pad + (index // columns) * (ch + label_height + pad)
        sheet.paste(image, (x, y))
        draw.text((x + 4, y + ch + 7), LABELS.get(name, name), fill=(215, 218, 224))
    sheet.save(output)
    print(f"{output} ({sheet.width}×{sheet.height}, {len(names)} views)")


if __name__ == "__main__":
    main()
