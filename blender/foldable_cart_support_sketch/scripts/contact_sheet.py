#!/usr/bin/env python3
"""Create a labeled sheet for the support's deployed, mount, and folded views."""

from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
RENDERS = REPO / "blender/foldable_cart_support_sketch/exports/renders"
VIEWS = (
    ("deployed_overview", "Deployed · cart context and leaning panel"),
    ("handle_mount_detail", "Part B · clamp, hinge, and adjustment strut"),
    ("folded_overview", "Folded · alternate stow pose"),
)


def main():
    missing = [name for name, _ in VIEWS if not (RENDERS / f"{name}.png").exists()]
    if missing:
        raise SystemExit("Missing renders: " + ", ".join(missing))
    cell_w, cell_h = 600, 429
    gap, header, footer = 12, 46, 34
    cols, rows = 2, 2
    width = cols * cell_w + (cols + 1) * gap
    height = header + rows * (cell_h + footer) + (rows + 1) * gap
    sheet = Image.new("RGB", (width, height), (25, 29, 34))
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 14), "Foldable cart leaning support · sketch-proportion concept", fill=(239, 241, 243))
    for i, (name, label) in enumerate(VIEWS):
        image = Image.open(RENDERS / f"{name}.png").convert("RGB").resize((cell_w, cell_h))
        x = gap + (i % cols) * (cell_w + gap)
        y = header + gap + (i // cols) * (cell_h + footer + gap)
        sheet.paste(image, (x, y))
        draw.text((x + 5, y + cell_h + 8), label, fill=(230, 233, 236))
    path = RENDERS / "foldable_support_comparison.png"
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
