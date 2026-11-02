#!/usr/bin/env python3
"""Render the separate stackable-lean-rest iteration at key animation poses."""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[3]
BLEND = REPO / "blender/stackable_iteration/source/stackable leaning support.blend"
OUT = REPO / "blender/stackable_iteration/exports/renders"
WIDTH, HEIGHT, SAMPLES = 1200, 820, 40
VIEWS = (
    ("01_stackable_deployed", 1, "panel", 1.55, (-1.0, -0.72, 0.38), 52),
    ("02_lift_over_handle", 16, "panel", 1.85, (-0.85, -0.75, 0.65), 48),
    ("03_above_basket", 22, "panel", 2.0, (-0.72, -0.82, 0.76), 46),
    ("04_childseat_stowed", 35, "panel", 1.65, (1.15, -0.90, 0.72), 52),
    ("05_stowed_cart_context", 35, "cart", 2.55, (1.0, -0.95, 0.56), 43),
)


def srgb(value: str):
    value = value.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(value[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out + [1.0]


def simple_mat(name, colour, roughness=0.8):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = srgb(colour)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = srgb(colour)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def object_center(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return Vector(tuple((min(p[i] for p in corners) + max(p[i] for p in corners)) / 2.0
                        for i in range(3)))


def light(name, position, target, watts, size, color=(1.0, 1.0, 1.0)):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = watts
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def camera(name, target, distance, direction, lens):
    data = bpy.data.cameras.new(name + "_Data")
    data.lens = lens
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    direction = Vector(direction).normalized()
    obj.location = target + direction * distance
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def setup_scene(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.025
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.25
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    bg = nodes.new("ShaderNodeBackground")
    out = nodes.new("ShaderNodeOutputWorld")
    bg.inputs["Color"].default_value = srgb("#515963")
    bg.inputs["Strength"].default_value = 0.70
    world.node_tree.links.new(bg.outputs["Background"], out.inputs["Surface"])


def main():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 35
    setup_scene(scene)

    # Render-only rig; it is not saved over the stackable source scene.
    for obj in list(bpy.data.objects):
        if obj.type in {"CAMERA", "LIGHT"} or obj.name.startswith("StackRender_"):
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, -0.004))
    floor = bpy.context.object
    floor.name = "StackRender_Floor"
    floor.data.materials.append(simple_mat("StackRender_FloorMat", "#77818A", 0.86))

    cart = bpy.data.objects["Shopping Cart"]
    panel = bpy.data.objects["HCD_Stackable_Cushion"]
    out = OUT
    out.mkdir(parents=True, exist_ok=True)

    for name, frame, target_kind, distance, direction, lens in VIEWS:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        target = object_center(panel) if target_kind == "panel" else Vector((0.0, 0.0, 0.62))
        cam = camera("StackRender_Camera_" + name, target, distance, direction, lens)
        key = light("StackRender_Key", target + Vector((-1.2, -1.7, 1.8)), target,
                    190, 1.65, (1.0, 0.86, 0.72))
        fill = light("StackRender_Fill", target + Vector((1.6, 0.8, 0.9)), target,
                     125, 2.2, (0.75, 0.85, 1.0))
        rim = light("StackRender_Rim", target + Vector((0.8, -0.5, 2.0)), target,
                    260, 1.2, (0.75, 0.84, 1.0))
        sun_data = bpy.data.lights.new("StackRender_SunData", "SUN")
        sun_data.energy = 2.2
        sun_data.angle = math.radians(7)
        sun = bpy.data.objects.new("StackRender_Sun", sun_data)
        scene.collection.objects.link(sun)
        sun.location = target + Vector((2.3, -3.0, 3.6))
        sun.rotation_euler = (target - sun.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam
        scene.render.filepath = str(out / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        print(f"  {name:<28} frame {frame} -> {scene.render.filepath}")
        for obj in (cam, key, fill, rim, sun):
            bpy.data.objects.remove(obj, do_unlink=True)

    print(f"\nRenders saved to {out}")


if __name__ == "__main__":
    main()
