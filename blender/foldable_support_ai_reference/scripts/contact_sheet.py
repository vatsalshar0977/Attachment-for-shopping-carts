#!/usr/bin/env python3
"""Create a comparison sheet for the revised AI-render-reference support."""

from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
RENDERS = REPO / "blender/foldable_support_ai_reference/exports/renders"
VIEWS = (
    ("deployed_overview", "Assembled · deployed on cart"),
    ("part_a_clamp_detail", "PART A · C-clamp, cam lever, and pivot"),
    ("part_b_strut_detail", "PART B · slotted telescopic angle stay"),
    ("folded_overview", "Folded · alternate panel position"),
)


def main():
    missing = [name for name, _ in VIEWS if not (RENDERS / f"{name}.png").exists()]
    if missing:
        raise SystemExit("Missing renders: " + ", ".join(missing))
    cell_w, cell_h = 560, 400
    gap, header, footer = 12, 46, 34
    cols, rows = 2, 2
    width = cols * cell_w + (cols + 1) * gap
    height = header + rows * (cell_h + footer) + (rows + 1) * gap
    sheet = Image.new("RGB", (width, height), (25, 29, 34))
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 14), "Foldable cart leaning support · revised to AI render reference", fill=(239, 241, 243))
    for i, (name, label) in enumerate(VIEWS):
        image = Image.open(RENDERS / f"{name}.png").convert("RGB").resize((cell_w, cell_h))
        x = gap + (i % cols) * (cell_w + gap)
        y = header + gap + (i // cols) * (cell_h + footer + gap)
        sheet.paste(image, (x, y))
        draw.text((x + 5, y + cell_h + 8), label, fill=(230, 233, 236))
    path = RENDERS / "ai_reference_support_comparison.png"
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
