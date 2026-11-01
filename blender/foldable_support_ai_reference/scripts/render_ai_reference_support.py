#!/usr/bin/env python3
"""Render assembled, clamp-detail, strut-detail, and folded views."""

from pathlib import Path

import bpy

REPO = Path(__file__).resolve().parents[3]
PROJECT = REPO / "blender/foldable_support_ai_reference"
BLEND = PROJECT / "source/foldable_leaning_support.blend"
OUT = PROJECT / "exports/renders"
VIEWS = (
    ("AIREF_Camera_Overview", "POSE — Deployed support", "deployed_overview", False),
    ("AIREF_Camera_PartA_Clamp_Detail", "POSE — Deployed support", "part_a_clamp_detail", True),
    ("AIREF_Camera_PartB_Strut_Detail", "POSE — Deployed support", "part_b_strut_detail", True),
    ("AIREF_Camera_Folded_Overview", "POSE — Folded panel", "folded_overview", False),
)
POSES = ("POSE — Deployed support", "POSE — Folded panel")


def main():
    if not BLEND.exists():
        raise FileNotFoundError(BLEND)
    OUT.mkdir(parents=True, exist_ok=True)
    for camera_name, active_pose, filename, hide_cart in VIEWS:
        bpy.ops.wm.open_mainfile(filepath=str(BLEND))
        scene = bpy.context.scene
        cart = bpy.data.objects.get("Shopping Cart")
        if cart is None:
            raise RuntimeError("Missing cart context object: Shopping Cart")
        cart.hide_render = hide_cart
        for name in POSES:
            pose = bpy.data.collections.get(name)
            if pose is None:
                raise RuntimeError(f"Missing pose collection: {name}")
            visible = name == active_pose
            pose.hide_viewport = not visible
            pose.hide_render = not visible
        camera = bpy.data.objects.get(camera_name)
        if camera is None:
            raise RuntimeError(f"Missing camera: {camera_name}")
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
    print(f"\nAI-render-reference previews in {OUT}")


if __name__ == "__main__":
    main()
