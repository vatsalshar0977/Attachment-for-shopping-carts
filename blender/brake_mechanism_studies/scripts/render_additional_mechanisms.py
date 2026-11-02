#!/usr/bin/env python3
"""Render one focused preview from each additional Blender brake study."""

from pathlib import Path

import bpy

REPO = Path(__file__).resolve().parents[3]
STUDIES = REPO / "blender/brake_mechanism_studies"
SOURCE = STUDIES / "source"
OUT = STUDIES / "exports/renders"
VIEWS = (
    ("M6_foot_treadle_cable", "Foot treadle with twin cables"),
    ("M7_ratchet_pawl_lock", "Ratchet ring with spring pawl"),
    ("M8_hydraulic_dual_caliper", "Hydraulic master cylinder and calipers"),
    ("M9_external_band_brake", "External band brake on rear drums"),
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, label in VIEWS:
        blend = SOURCE / f"{slug}.blend"
        if not blend.exists():
            raise FileNotFoundError(blend)
        bpy.ops.wm.open_mainfile(filepath=str(blend))
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 36
        scene.cycles.use_denoising = True
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.03
        scene.render.resolution_x, scene.render.resolution_y = 1200, 900
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
        scene.view_settings.exposure = -0.20
        scene.render.filepath = str(OUT / f"{slug}.png")
        bpy.ops.render.render(write_still=True)
        print(f"  {slug}.png — {label}")
    print(f"\nAdditional mechanism previews in {OUT}")


if __name__ == "__main__":
    main()
