#!/usr/bin/env python3
"""Build a labeled overview of the four additional brake mechanism studies."""

from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
RENDERS = REPO / "blender/brake_mechanism_studies/exports/renders"
VIEWS = (
    ("M6_foot_treadle_cable", "M6 · Foot treadle with twin cables"),
    ("M7_ratchet_pawl_lock", "M7 · Ratchet ring and spring pawl"),
    ("M8_hydraulic_dual_caliper", "M8 · Hydraulic master cylinder and calipers"),
    ("M9_external_band_brake", "M9 · External band brake on rear drums"),
)


def main():
    missing = [slug for slug, _ in VIEWS if not (RENDERS / f"{slug}.png").exists()]
    if missing:
        raise SystemExit("Missing renders: " + ", ".join(missing))
    cell_w, cell_h = 560, 420
    gap, header, footer = 12, 46, 32
    cols, rows = 2, 2
    width = cols * cell_w + (cols + 1) * gap
    height = header + rows * (cell_h + footer) + (rows + 1) * gap
    sheet = Image.new("RGB", (width, height), (25, 29, 34))
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 14), "Additional cart brake concepts · M6–M9", fill=(239, 241, 243))
    for i, (slug, label) in enumerate(VIEWS):
        image = Image.open(RENDERS / f"{slug}.png").convert("RGB").resize((cell_w, cell_h))
        x = gap + (i % cols) * (cell_w + gap)
        y = header + gap + (i // cols) * (cell_h + footer + gap)
        sheet.paste(image, (x, y))
        draw.text((x + 5, y + cell_h + 8), label, fill=(230, 233, 236))
    path = RENDERS / "additional_brake_mechanisms_comparison.png"
    sheet.save(path)
    print(f"{path}")


if __name__ == "__main__":
    main()
