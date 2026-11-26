#!/usr/bin/env python3
"""Render overview, handle-control, and rear-wheel views of the handle-brake study."""

from pathlib import Path

import bpy

REPO = Path(__file__).resolve().parents[3]
STUDY = REPO / "blender/handle_brake_study"
BLEND = STUDY / "source/handle_lever_rear_brake.blend"
OUT = STUDY / "exports/renders"
VIEWS = (
    ("STUDY_Camera_Overview", "handle_brake_overview"),
    ("STUDY_Camera_Handle_Detail", "handle_brake_handle_detail"),
    ("STUDY_Camera_Wheel_Detail", "handle_brake_wheel_detail"),
)


def main():
    if not BLEND.exists():
        raise FileNotFoundError(BLEND)
    OUT.mkdir(parents=True, exist_ok=True)
    for camera_name, filename in VIEWS:
        bpy.ops.wm.open_mainfile(filepath=str(BLEND))
        scene = bpy.context.scene
        camera = bpy.data.objects.get(camera_name)
        if camera is None:
            raise RuntimeError(f"Missing saved camera: {camera_name}")
        scene.camera = camera
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
        scene.render.filepath = str(OUT / f"{filename}.png")
        bpy.ops.render.render(write_still=True)
        print(f"  {filename}.png")
    print(f"\nHandle-operated brake renders in {OUT}")


if __name__ == "__main__":
    main()
