#!/usr/bin/env python3
"""Create labeled overview and detail sheets from the brake-mechanism renders."""

from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
RENDERS = REPO / "blender/brake_mechanisms/exports/renders"
OVERVIEWS = (
    ("M1_spring_applied_cable", "1 · spring-applied cable / dead-man grip"),
    ("M2_push_rod_bell_cranks", "2 · push-rod with bell cranks"),
    ("M3_overcentre_toggle", "3 · over-centre toggle lever"),
    ("M4_pad_linked_lock", "4 · pad-linked lock"),
    ("M5_crossbar_cam_lock", "5 · cross-bar cam lock"),
)
DETAILS = (
    ("M1_spring_applied_cable_detail", "1 · spring-applied brake / wheel detail"),
    ("M2_push_rod_bell_cranks_detail", "2 · push-rod bell crank / wheel detail"),
    ("M3_overcentre_toggle", "3 · over-centre toggle / handle detail"),
    ("M4_pad_linked_lock_detail", "4 · pad-linked lock / plunger detail"),
    ("M5_crossbar_cam_lock", "5 · cross-bar cam / wheel detail"),
)


def create_sheet(views, filename):
    images = [(stem, label) for stem, label in views if (RENDERS / (stem + ".png")).exists()]
    if len(images) != len(views):
        missing = sorted(set(stem for stem, _ in views) - set(stem for stem, _ in images))
        raise SystemExit(f"Missing renders for {filename}: {', '.join(missing)}")
    first = Image.open(RENDERS / (images[0][0] + ".png"))
    cell_w = 560
    cell_h = round(cell_w * first.height / first.width)
    cols, gap, footer = 2, 10, 32
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new(
        "RGB",
        (cols * cell_w + (cols + 1) * gap, rows * (cell_h + footer) + (rows + 1) * gap),
        (28, 31, 35),
    )
    draw = ImageDraw.Draw(sheet)
    for i, (stem, label) in enumerate(images):
        img = Image.open(RENDERS / (stem + ".png")).convert("RGB").resize((cell_w, cell_h))
        x = gap + (i % cols) * (cell_w + gap)
        y = gap + (i // cols) * (cell_h + footer + gap)
        sheet.paste(img, (x, y))
        draw.text((x + 5, y + cell_h + 8), label, fill=(230, 232, 235))
    path = RENDERS / filename
    sheet.save(path)
    print(f"{path} ({len(images)} renders)")


def main():
    create_sheet(OVERVIEWS, "brake_mechanism_comparison.png")
    create_sheet(DETAILS, "brake_mechanism_details.png")


if __name__ == "__main__":
    main()
