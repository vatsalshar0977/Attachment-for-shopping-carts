#!/usr/bin/env python3
"""Create a labeled sheet for the handle-brake overview and detail renders."""

from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
RENDERS = REPO / "blender/handle_brake_study/exports/renders"
VIEWS = (
    ("handle_brake_overview", "Full system · handle lever to rear shoes"),
    ("handle_brake_handle_detail", "Handle-mounted squeeze lever and cable entry"),
    ("handle_brake_wheel_detail", "Rear shoe, equalizer, and cable interface"),
)


def main():
    missing = [name for name, _ in VIEWS if not (RENDERS / f"{name}.png").exists()]
    if missing:
        raise SystemExit("Missing renders: " + ", ".join(missing))
    cell_w, cell_h = 560, 420
    gap, header, footer = 12, 46, 32
    cols, rows = 2, 2
    width = cols * cell_w + (cols + 1) * gap
    height = header + rows * (cell_h + footer) + (rows + 1) * gap
    sheet = Image.new("RGB", (width, height), (25, 29, 34))
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 14), "Handle-operated cart brake · handle control, rear-wheel braking", fill=(239, 241, 243))
    for i, (name, label) in enumerate(VIEWS):
        image = Image.open(RENDERS / f"{name}.png").convert("RGB").resize((cell_w, cell_h))
        x = gap + (i % cols) * (cell_w + gap)
        y = header + gap + (i // cols) * (cell_h + footer + gap)
        sheet.paste(image, (x, y))
        draw.text((x + 5, y + cell_h + 8), label, fill=(230, 233, 236))
    path = RENDERS / "handle_brake_study_comparison.png"
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
