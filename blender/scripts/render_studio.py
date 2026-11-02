#!/usr/bin/env python3
"""Render deployed and stowed views of the fold-out leaning support.

Run from the repository root:
    LD_LIBRARY_PATH=$HOME/tools/bpy-stubs python3 blender/scripts/render_studio.py

Optional arguments select view names by substring (for example ``stowed`` or
``hinge``). The render rig is temporary and is not saved back into the source
blend file.
"""

from __future__ import annotations

import math
import os
import sys

import bpy
from mathutils import Vector

BLEND = "blender/source/hcd mockup.blend"
OUT_DIR = "blender/exports/renders"
WIDTH, HEIGHT = 1200, 820
SAMPLES = 64
DENOISE = True
TARGET_LUMINANCE = 0.30
TARGET_HIGHLIGHT = 0.86
BACKGROUND = "#171A1E"
FLOOR = "#929AA3"
DEPLOYED = 1
MID_FOLD = 18
STOWED = 35

# name, frame, distance, azimuth, elevation, lens, lighting rig, aim point
VIEWS = [
    ("01_deployed_hero",     DEPLOYED, 1.48,  32,  14, 52, "studio", "panel"),
    ("02_deployed_front",    DEPLOYED, 1.26,   0,   3, 56, "studio", "panel"),
    ("03_hinge_detail",      DEPLOYED, 0.72,  54,  34, 82, "studio", "hinge"),
    ("04_deployed_on_cart",  DEPLOYED, 1.50,  27,  16, 48, "sun",    "panel"),
    ("05_stowed_in_basket",  STOWED,   1.20,  32,  54, 56, "sun",    "basket"),
    ("06_stowed_context",    STOWED,   2.55,  33,  17, 42, "sun",    "cart"),
    ("07_mid_fold",          MID_FOLD, 1.70,  32,  25, 48, "sun",    "cart"),
    ("08_stowed_top",        STOWED,   1.12,  24,  72, 62, "sun",    "basket"),
]


def srgb_hex_to_linear(value: str) -> list[float]:
    value = value.lstrip("#")
    result = []
    for i in (0, 2, 4):
        channel = int(value[i:i + 2], 16) / 255.0
        result.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    return result + [1.0]


def simple_material(name: str, colour: str, roughness: float = 0.8,
                    metallic: float = 0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = srgb_hex_to_linear(colour)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = srgb_hex_to_linear(colour)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def area_light(name, energy, size_x, size_y, colour=(1.0, 1.0, 1.0)):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "RECTANGLE"
    data.size = size_x
    data.size_y = size_y
    data.energy = energy
    data.color = colour
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def aim_point(obj: bpy.types.Object) -> Vector:
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return Vector(((min(p.x for p in points) + max(p.x for p in points)) * 0.5,
                   (min(p.y for p in points) + max(p.y for p in points)) * 0.5,
                   (min(p.z for p in points) + max(p.z for p in points)) * 0.5))


def make_targets(cart: bpy.types.Object):
    rest = bpy.data.objects["HCD_Rest_Cushion"]
    hinge = bpy.data.objects["HCD_Hinge_Mount_Left"]
    cart_pts = [cart.matrix_world @ Vector(corner) for corner in cart.bound_box]
    cart_center = Vector(((min(p.x for p in cart_pts) + max(p.x for p in cart_pts)) * 0.5,
                          (min(p.y for p in cart_pts) + max(p.y for p in cart_pts)) * 0.5,
                          (min(p.z for p in cart_pts) + max(p.z for p in cart_pts)) * 0.5))
    deployed_center = aim_point(rest)
    stowed_center = aim_point(rest)
    return {"panel": deployed_center, "hinge": aim_point(hinge),
            "cart": Vector((cart_center.x, cart_center.y, 0.55)),
            "basket": stowed_center, "stowed": stowed_center}


def camera_for(name: str, target: Vector, distance: float,
               azimuth: float, elevation: float, lens: float):
    camera_data = bpy.data.cameras.new(name + "_Data")
    camera_data.lens = lens
    camera = bpy.data.objects.new(name, camera_data)
    bpy.context.scene.collection.objects.link(camera)
    az, el = math.radians(azimuth), math.radians(elevation)
    camera.location = (target.x - distance * math.cos(el) * math.cos(az),
                       target.y - distance * math.cos(el) * math.sin(az),
                       target.z + distance * math.sin(el))
    look_at(camera, target)
    return camera


def set_track(light, target: Vector):
    look_at(light, target)


def build_handle_stub(cart: bpy.types.Object):
    import numpy as np

    mw = np.array(cart.matrix_world)
    verts = np.array([tuple(v.co) for v in cart.data.vertices])
    world = (np.c_[verts, np.ones(len(verts))] @ mw.T)[:, :3]
    zmax = world[:, 2].max()
    ymax, ymin = world[:, 1].max(), world[:, 1].min()
    ymid = (ymax + ymin) / 2.0
    top = world[world[:, 2] > zmax - 0.05]
    band = top[np.abs(top[:, 1] - ymid) < 0.10]
    hx, hz = float(np.median(band[:, 0])), float(np.median(band[:, 2]))
    bpy.ops.mesh.primitive_cylinder_add(radius=0.0233 / 2.0, depth=0.54,
                                        vertices=64, location=(hx, ymid, hz),
                                        rotation=(math.pi / 2.0, 0.0, 0.0))
    bar = bpy.context.object
    bar.name = "Render_Handle_Bar_Stub"
    bar.data.materials.append(simple_material("Render_Bar_Material", "#BAC1C8", 0.28, 0.88))
    bevel = bar.modifiers.new("Tiny_Edge_Radius", "BEVEL")
    bevel.width = 0.001
    bevel.segments = 2
    return bar


def build_studios(target: Vector):
    # Large, soft product lights. The close studio renders keep the cart hidden
    # but show a real handle-bar segment and all of the attachment hardware.
    studio_lights = []
    for name, offset, energy, sx, sy, colour in (
        ("Render_Key", Vector((-0.55, -0.75, 0.65)), 70, 0.90, 0.60, (1.0, 0.84, 0.68)),
        ("Render_Fill", Vector((-1.05, 0.55, 0.30)), 22, 1.20, 0.90, (0.70, 0.82, 1.0)),
        ("Render_Rim", Vector((0.72, 0.65, 0.62)), 55, 0.72, 0.52, (0.66, 0.79, 1.0)),
        ("Render_Bounce", Vector((-0.25, -0.10, -0.42)), 12, 0.95, 0.65, (1.0, 0.94, 0.84)),
    ):
        light = area_light(name, energy, sx, sy, colour)
        light.location = target + offset
        set_track(light, target)
        studio_lights.append(light)

    sun_data = bpy.data.lights.new("Render_Sun_Data", "SUN")
    sun_data.energy = 2.6
    sun_data.angle = math.radians(8)
    sun = bpy.data.objects.new("Render_Sun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.location = target + Vector((-2.3, -3.0, 3.6))
    set_track(sun, target)
    sky = area_light("Render_Sky", 36, 5.0, 5.0, (0.82, 0.88, 1.0))
    sky.location = target + Vector((0.0, 0.0, 3.0))
    set_track(sky, target)
    return studio_lights, [sun, sky]


def probe_luminance(path: str):
    import numpy as np

    image = bpy.data.images.load(path)
    pixels = np.asarray(image.pixels[:], dtype=np.float32).reshape(-1, 4)
    luminance = pixels[:, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    bpy.data.images.remove(image)
    return float(luminance.mean()), float(np.percentile(luminance, 99.5))


def auto_expose(scene, camera, tmp_path, target=TARGET_LUMINANCE, rounds=3):
    width, height, percentage = (scene.render.resolution_x, scene.render.resolution_y,
                                scene.render.resolution_percentage)
    samples, denoise = scene.cycles.samples, scene.cycles.use_denoising
    scene.render.resolution_x, scene.render.resolution_y = 220, 150
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    scene.camera = camera
    for _ in range(rounds):
        bpy.ops.render.render(write_still=True)
        mean, p99 = probe_luminance(tmp_path)
        delta = math.log2(target / max(mean, 1e-4))
        if p99 > TARGET_HIGHLIGHT:
            delta = min(delta, math.log2(TARGET_HIGHLIGHT / p99))
        delta = max(-1.5, min(1.5, delta))
        print(f"    exposure probe: mean={mean:.3f}, p99={p99:.3f}, adjustment={delta:+.2f} EV")
        if abs(delta) < 0.15:
            break
        scene.view_settings.exposure = max(-6.0, min(6.0, scene.view_settings.exposure + delta * 0.75))
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = percentage
    scene.cycles.samples, scene.cycles.use_denoising = samples, denoise
    return scene.view_settings.exposure


def main():
    requested = set(sys.argv[1:])
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    blend_path = os.path.join(root_dir, BLEND)
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    scene = bpy.context.scene

    # Remove stale temporary studio objects if the script is rerun in-process.
    for obj in list(bpy.data.objects):
        if obj.type in {"LIGHT", "CAMERA"} or obj.name.startswith(("Render_", "cam_", "TGT_", "Studio_Floor")):
            bpy.data.objects.remove(obj, do_unlink=True)

    cart = bpy.data.objects["Shopping Cart"]
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = DENOISE
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.max_bounces = 7
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.cycles.adaptive_min_samples = 16
    scene.render.use_persistent_data = True
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()
    background = nodes.new("ShaderNodeBackground")
    output = nodes.new("ShaderNodeOutputWorld")
    background.inputs["Color"].default_value = srgb_hex_to_linear(BACKGROUND)
    background.inputs["Strength"].default_value = 0.9
    links.new(background.outputs["Background"], output.inputs["Surface"])

    bpy.ops.mesh.primitive_plane_add(size=12, location=(0.0, 0.0, -0.002))
    floor = bpy.context.object
    floor.name = "Render_Studio_Floor"
    floor.data.materials.append(simple_material("Render_Floor_Material", FLOOR, 0.85))
    bar = build_handle_stub(cart)

    out_dir = os.path.join(root_dir, OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    scene.render.filepath = os.path.join(out_dir, "_probe.png")

    for name, frame, dist, az, el, lens, rig, target_name in VIEWS:
        if requested and not any(part in name for part in requested):
            continue
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        targets = make_targets(cart)
        target = targets[target_name]
        studio_lights, sun_lights = build_studios(target)
        camera = camera_for("cam_" + name, target, dist, az, el, lens)
        scene.camera = camera

        is_studio = rig == "studio"
        cart.hide_render = is_studio
        bar.hide_render = not is_studio
        floor.hide_render = is_studio
        for light in studio_lights:
            light.hide_render = not is_studio
        for light in sun_lights:
            light.hide_render = is_studio

        scene.view_settings.exposure = 0.0
        scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
        scene.render.resolution_percentage = 100
        probe_path = os.path.join(out_dir, "_probe.png")
        scene.render.filepath = probe_path
        exposure = auto_expose(scene, camera, probe_path)
        scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
        scene.render.resolution_percentage = 100
        scene.render.filepath = os.path.join(out_dir, name + ".png")
        bpy.ops.render.render(write_still=True)
        print(f"  {name:<22} frame {frame:>2}  exposure {exposure:+.2f} EV -> {name}.png")

        # Keep the temporary scene light on memory while the next set is added.
        for obj in [camera, *studio_lights, *sun_lights]:
            bpy.data.objects.remove(obj, do_unlink=True)

    try:
        os.remove(os.path.join(out_dir, "_probe.png"))
    except OSError:
        pass
    print(f"\nDeployed and stowed renders saved under {OUT_DIR}")


if __name__ == "__main__":
    main()
