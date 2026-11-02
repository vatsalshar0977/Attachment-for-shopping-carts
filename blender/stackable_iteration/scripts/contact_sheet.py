#!/usr/bin/env python3
"""Build a preview sheet for the stackable iteration's animation poses."""

from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
RENDERS = REPO / "blender/stackable_iteration/exports/renders"
ORDER = (
    ("01_stackable_deployed", "deployed leaning rest"),
    ("02_lift_over_handle", "folds up and over handle"),
    ("03_above_basket", "moves above basket mouth"),
    ("04_childseat_stowed", "upright at child-seat plane"),
    ("05_stowed_cart_context", "stowed · cart context"),
)


def main():
    names = [(stem, label) for stem, label in ORDER if (RENDERS / (stem + ".png")).exists()]
    if not names:
        raise SystemExit(f"No renders in {RENDERS}; run render_stackable.py first")
    first = Image.open(RENDERS / (names[0][0] + ".png"))
    width = 520
    height = round(width * first.height / first.width)
    columns, gap, footer = 2, 10, 32
    rows = (len(names) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * width + (columns + 1) * gap,
                               rows * (height + footer) + (rows + 1) * gap),
                      (28, 31, 35))
    draw = ImageDraw.Draw(sheet)
    for i, (stem, label) in enumerate(names):
        image = Image.open(RENDERS / (stem + ".png")).convert("RGB").resize((width, height))
        x = gap + (i % columns) * (width + gap)
        y = gap + (i // columns) * (height + footer + gap)
        sheet.paste(image, (x, y))
        draw.text((x + 5, y + height + 8), label, fill=(225, 229, 234))
    output = RENDERS / "contact_sheet.png"
    sheet.save(output)
    print(f"{output} ({len(names)} views)")


if __name__ == "__main__":
    main()
