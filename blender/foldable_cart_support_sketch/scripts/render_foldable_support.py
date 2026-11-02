#!/usr/bin/env python3
"""Render deployed, handle-mount, and folded views of the new support study."""

from pathlib import Path

import bpy

REPO = Path(__file__).resolve().parents[3]
PROJECT = REPO / "blender/foldable_cart_support_sketch"
BLEND = PROJECT / "source/foldable_cart_leaning_support.blend"
OUT = PROJECT / "exports/renders"
VIEWS = (
    ("FOLD_Camera_Deployed_Overview", "POSE — Deployed leaning support", "deployed_overview"),
    ("FOLD_Camera_Handle_Mount_Detail", "POSE — Deployed leaning support", "handle_mount_detail"),
    ("FOLD_Camera_Folded_Overview", "POSE — Folded / stowed", "folded_overview"),
)


def main():
    if not BLEND.exists():
        raise FileNotFoundError(BLEND)
    OUT.mkdir(parents=True, exist_ok=True)
    for camera_name, active_pose, filename in VIEWS:
        bpy.ops.wm.open_mainfile(filepath=str(BLEND))
        scene = bpy.context.scene
        for pose_name in ("POSE — Deployed leaning support", "POSE — Folded / stowed"):
            pose = bpy.data.collections.get(pose_name)
            if pose is None:
                raise RuntimeError(f"Missing pose collection: {pose_name}")
            visible = pose.name == active_pose
            pose.hide_viewport = not visible
            pose.hide_render = not visible
        camera = bpy.data.objects.get(camera_name)
        if camera is None:
            raise RuntimeError(f"Missing saved camera: {camera_name}")
        scene.camera = camera
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 40
        scene.cycles.use_denoising = True
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.025
        scene.render.resolution_x, scene.render.resolution_y = 1400, 1000
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
        scene.view_settings.exposure = -0.15
        scene.render.filepath = str(OUT / f"{filename}.png")
        bpy.ops.render.render(write_still=True)
        print(f"  {filename}.png")
    print(f"\nFoldable cart-support renders in {OUT}")


if __name__ == "__main__":
    main()
