#!/usr/bin/env python3
"""Print an image as ASCII so its composition can be checked without a viewer.

Also reports exposure statistics, which is how the lighting gets judged in a
headless container.

Usage:
    python3 scripts/ascii_view.py blender/exports/renders/01_hero.png [width]
"""

import sys

from PIL import Image

RAMP = " .:-=+*#%@"


def main() -> None:
    path = sys.argv[1]
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 96
    im = Image.open(path).convert("RGB")
    w, h = im.size
    rows = max(1, int(cols * h / w * 0.5))
    small = im.resize((cols, rows))

    px = list(small.getdata())
    lum = [(0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0 for r, g, b in px]

    print(f"{path}  {w}x{h}")
    out = []
    for y in range(rows):
        line = "".join(RAMP[min(int(v * len(RAMP)), len(RAMP) - 1)] for v in lum[y * cols:(y + 1) * cols])
        out.append(line)
    print("\n".join(out))

    full = im.resize((320, int(320 * h / w)))
    fl = [(0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0 for r, g, b in full.getdata()]
    n = len(fl)
    mean = sum(fl) / n
    clipped = sum(1 for v in fl if v > 0.995) / n
    dark = sum(1 for v in fl if v < 0.02) / n
    ordered = sorted(fl)
    print(f"\nmean={mean:.3f}  clipped={clipped * 100:.2f}%  near-black={dark * 100:.1f}%  "
          f"p05={ordered[int(n * 0.05)]:.3f} p50={ordered[n // 2]:.3f} p95={ordered[int(n * 0.95)]:.3f}")


if __name__ == "__main__":
    main()
