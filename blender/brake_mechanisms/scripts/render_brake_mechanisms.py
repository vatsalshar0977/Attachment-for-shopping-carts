#!/usr/bin/env python3
"""Render each alternative separately from the shared cart reference scene."""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[3]
BLEND = REPO / "blender/brake_mechanisms/source/cart brake alternatives.blend"
OUT = REPO / "blender/brake_mechanisms/exports/renders"
VIEWS = [
    ("BRK Variant 01 — 01 — Spring-applied cable / dead-man grip", "M1_spring_applied_cable", "side"),
    ("BRK Variant 02 — 02 — Push-rod with bell cranks", "M2_push_rod_bell_cranks", "side"),
    ("BRK Variant 03 — 03 — Over-centre toggle at handle", "M3_overcentre_toggle", "handle"),
    ("BRK Variant 04 — 04 — Pad-linked lock", "M4_pad_linked_lock", "side"),
    ("BRK Variant 05 — 05 — Cross-bar cam lock", "M5_crossbar_cam_lock", "wheel"),
]
DETAIL_VIEWS = [
    (VIEWS[0][0], "M1_spring_applied_cable_detail", "wheel"),
    (VIEWS[1][0], "M2_push_rod_bell_cranks_detail", "wheel"),
    (VIEWS[3][0], "M4_pad_linked_lock_detail", "pad"),
]
WIDTH, HEIGHT, SAMPLES = 1200, 900, 48


def srgb(hex_color):
    value = hex_color.lstrip("#")
    rgb = []
    for i in (0, 2, 4):
        c = int(value[i:i + 2], 16) / 255.0
        rgb.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return rgb + [1.0]


def material(name, color, roughness=0.7, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = srgb(color)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    rgba = srgb(color)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def look_at(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def area_light(name, target, offset, energy, size, color):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = target + Vector(offset)
    look_at(obj, target)
    return obj


def camera_for(name, target, kind):
    data = bpy.data.cameras.new(name + "_Data")
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    if kind == "side":
        data.type = "ORTHO"
        data.ortho_scale = 1.62
        obj.location = target + Vector((0.03, -2.8, 0.36))
    elif kind == "handle":
        data.type = "PERSP"
        data.lens = 74
        obj.location = target + Vector((-0.24, -0.82, 0.22))
    elif kind == "pad":
        data.type = "PERSP"
        data.lens = 66
        obj.location = target + Vector((0.85, -1.0, 0.28))
    else:  # wheel / cross-bar cam detail
        data.type = "PERSP"
        data.lens = 72
        obj.location = target + Vector((-0.48, -0.85, 0.25))
    look_at(obj, target)
    return obj


def setup_scene(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.35
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes.clear()
    background = world.node_tree.nodes.new("ShaderNodeBackground")
    output = world.node_tree.nodes.new("ShaderNodeOutputWorld")
    background.inputs["Color"].default_value = srgb("#202830")
    background.inputs["Strength"].default_value = 0.40
    world.node_tree.links.new(background.outputs["Background"], output.inputs["Surface"])


def main():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    setup_scene(scene)

    # Render-only rig and a muted cart material keep the actuation parts readable.
    for obj in list(bpy.data.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.mesh.primitive_plane_add(size=100, location=(0.0, 0.0, -0.004))
    floor = bpy.context.object
    floor.name = "BrakeRender_Floor"
    floor.data.materials.append(material("BrakeRender_Floor_Material", "#343D47", 0.9))
    cart = bpy.data.objects["Shopping Cart"]
    cart.data.materials.clear()
    cart.data.materials.append(material("BrakeRender_Cart_Material", "#56616B", 0.64, 0.24))

    out = OUT
    out.mkdir(parents=True, exist_ok=True)
    handle = Vector((-0.4944, 0.0, 1.0917))
    rear_wheel = Vector((-0.398, -0.246, 0.076))

    for collection_name, filename, kind in VIEWS + DETAIL_VIEWS:
        active = bpy.data.collections[collection_name]
        for name, _, _ in VIEWS:
            col = bpy.data.collections[name]
            col.hide_viewport = False
            col.hide_render = col != active
        if kind == "handle":
            target = handle + Vector((0.04, -0.18, 0.02))
        elif kind == "wheel":
            target = rear_wheel
        elif kind == "pad":
            target = handle + Vector((-0.052, 0.0, -0.235))
        else:
            target = Vector((-0.435, -0.205, 0.565))
        cam = camera_for("BrakeRender_Camera_" + filename, target, kind)
        lights = [
            area_light("BrakeRender_Key", target, (-0.75, -1.0, 1.25), 78, 1.15, (1.0, 0.88, 0.73)),
            area_light("BrakeRender_Fill", target, (0.55, 0.9, 0.65), 44, 1.5, (0.76, 0.86, 1.0)),
            area_light("BrakeRender_Rim", target, (0.8, -0.1, 1.45), 86, 0.85, (0.78, 0.88, 1.0)),
        ]
        sun_data = bpy.data.lights.new("BrakeRender_Sun_Data", "SUN")
        sun_data.energy = 0.72
        sun_data.angle = math.radians(8)
        sun = bpy.data.objects.new("BrakeRender_Sun", sun_data)
        scene.collection.objects.link(sun)
        sun.location = target + Vector((1.8, -2.5, 2.6))
        look_at(sun, target)
        lights.append(sun)
        scene.camera = cam
        scene.render.filepath = str(out / (filename + ".png"))
        bpy.ops.render.render(write_still=True)
        print(f"  {filename}.png")
        for obj in [cam, *lights]:
            bpy.data.objects.remove(obj, do_unlink=True)

    print(f"\nAlternative renders in {out}")


if __name__ == "__main__":
    main()
