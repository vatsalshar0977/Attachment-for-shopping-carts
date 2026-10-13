#!/usr/bin/env python3
"""Render the HCD attachment with a studio lighting rig.

Cycles + CPU is the only renderer available in this container (EEVEE and
Workbench both need a real EGL/OpenGL driver), so renders are slow. Quality is
therefore adjustable, and exposure is set automatically: the script renders a
tiny probe, measures its mean luminance and nudges the scene exposure until the
frame sits in a sensible range.

Usage:
    LD_LIBRARY_PATH=$HOME/tools/bpy-stubs python3 scripts/render_studio.py
    LD_LIBRARY_PATH=$HOME/tools/bpy-stubs python3 scripts/render_studio.py hero front
"""

from __future__ import annotations

import math
import os
import sys

import bpy

# --------------------------------------------------------------------------- #
# PARAMS
# --------------------------------------------------------------------------- #

BLEND = "blender/source/hcd mockup.blend"
OUT_DIR = "blender/exports/renders"

WIDTH, HEIGHT = 1200, 820
SAMPLES = 64
DENOISE = True
TARGET_LUMINANCE = 0.12      # mean brightness the auto-exposure aims for
TARGET_HIGHLIGHT = 0.86      # keep the pad/metal away from clipping
BACKGROUND = "#171A1E"       # near-black, so the product separates from it
FLOOR = "#8E949C"

# Distances are to the *near* face of the part: the pad is 300 mm long, so a
# 62 cm pull-back on an 85 mm lens crops it. These leave ~40% margin.
# name            distance  azimuth  elevation  lens   rig      target
VIEWS = [
    ("01_hero",        1.00,  38,  16, 65,  "studio", "pad"),
    ("02_contact",     0.90,   0,   2, 65,  "studio", "pad"),
    ("03_profile",     0.75,  90,   4, 85,  "studio", "pad"),
    ("04_top",         0.80,  25,  58, 65,  "studio", "pad"),
    ("05_underside",   0.75,  25, -48, 65,  "studio", "pad"),
    ("06_detail",      0.52,  45,  18, 100, "studio", "pad"),
    ("07_on_cart",     1.30,  12,  10, 50,  "sun",    "pad"),
    ("08_cart_wide",   2.60,  32,  14, 40,  "sun",    "cart"),
]

# --------------------------------------------------------------------------- #


def srgb_hex_to_linear(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out + [1.0]


def clear_all(type_):
    for obj in list(getattr(bpy.data, type_)):
        if obj.users == 0:
            getattr(bpy.data, type_).remove(obj)


def simple_material(name, hex_color, roughness=0.8):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = srgb_hex_to_linear(hex_color)
    bsdf.inputs["Roughness"].default_value = roughness
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    out.location, bsdf.location = (300, 0), (0, 0)
    return mat


def area_light(name, size_x, size_y, watts, colour=(1, 1, 1, 1)):
    data = bpy.data.lights.new(name, "AREA")
    data.size, data.size_y = size_x, size_y
    data.energy = watts
    data.color = colour[:3]
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def build_bar_stub(pad, cart, dia=0.0233, length=0.44):
    """A short length of handle bar, so close-ups show the pad mounted on something.

    The full cart is too busy a backdrop for a product shot, but the pad on its
    own reads as a floating blob -- a stub of the real bar fixes both.
    """
    import numpy as np

    mw = np.array(cart.matrix_world)
    v = np.array([tuple(p.co) for p in cart.data.vertices])
    w = (np.c_[v, np.ones(len(v))] @ mw.T)[:, :3]
    zmax = w[:, 2].max()
    top = w[w[:, 2] > zmax - 0.05]
    ymid = (w[:, 1].min() + w[:, 1].max()) / 2.0
    band = top[np.abs(top[:, 1] - ymid) < 0.10]
    cx, cz = float(np.median(band[:, 0])), float(np.median(band[:, 2]))

    bpy.ops.mesh.primitive_cylinder_add(radius=dia / 2, depth=length, vertices=48,
                                        location=(cx, 0.0, cz), rotation=(math.pi / 2, 0, 0))
    bar = bpy.context.active_object
    bar.name = "Handle_Bar_Stub"
    bar.data.materials.append(simple_material("Bar_Steel", "#B4BAC1", 0.34))
    mat = bar.data.materials[-1]
    mat.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    bar.data.materials[0] = mat
    return bar


def build_rigs(pad, cart):
    """Two lighting rigs: a tight studio setup and a broad outdoor one."""
    studio = bpy.data.objects.new("StudioRig", None)
    sunrig = bpy.data.objects.new("SunRig", None)
    for o in (studio, sunrig):
        bpy.context.scene.collection.objects.link(o)
    studio.location = pad.location      # pad is the aim empties, already in world space
    sunrig.location = (0, 0, 0)

    # --- studio: key / fill / rim / bounce
    def place(light, rig, dx, dy, dz, look_at):
        light.parent = rig
        light.location = (dx, dy, dz)
        light.matrix_parent_inverse = rig.matrix_world.inverted()
        light.rotation_euler = (0, 0, 0)
        c = light.constraints.new("TRACK_TO")
        c.target = look_at
        c.track_axis = "TRACK_NEGATIVE_Z"
        c.up_axis = "UP_Y"

    key = area_light("Key", 0.9, 0.55, 60)
    fill = area_light("Fill", 1.4, 1.0, 18)
    rim = area_light("Rim", 0.8, 0.5, 48)
    bounce = area_light("Bounce", 1.2, 0.8, 10)
    place(key, studio, -0.55, -0.75, 0.62, pad)
    place(fill, studio, -1.10, 0.55, 0.28, pad)
    place(rim, studio, 0.85, 0.70, 0.55, pad)
    place(bounce, studio, -0.30, 0.10, -0.45, pad)

    # --- sun rig for the wide, on-cart shots
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 3.4
    sun_data.angle = math.radians(4)
    sun_obj = bpy.data.objects.new("Sun", sun_data)
    bpy.context.scene.collection.objects.link(sun_obj)
    sun_obj.parent = sunrig
    sun_obj.location = (-2.2, -2.6, 3.2)
    c = sun_obj.constraints.new("TRACK_TO")
    c.target = pad
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"

    sky = area_light("Sky", 6.0, 6.0, 45, (0.85, 0.90, 1.0))
    sky.parent = sunrig
    sky.location = (0, 0, 4.0)
    sky.rotation_euler = (0, 0, 0)

    return studio, sunrig


def world_centre(obj):
    """Centre of an object's world-space bounding box.

    The attachment's parts are parented to an empty, so their own .location is
    (0,0,0) -- aiming a camera at that points it at the floor.
    """
    import mathutils

    pts = [obj.matrix_world @ mathutils.Vector(v) for v in obj.bound_box]
    return mathutils.Vector((
        (min(p.x for p in pts) + max(p.x for p in pts)) / 2,
        (min(p.y for p in pts) + max(p.y for p in pts)) / 2,
        (min(p.z for p in pts) + max(p.z for p in pts)) / 2,
    ))


def target_empty(name, obj):
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 0.05
    empty.location = world_centre(obj)
    bpy.context.scene.collection.objects.link(empty)
    return empty


def camera_for(name, target_obj, dist, az, el, lens):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam)

    az, el = math.radians(az), math.radians(el)
    # +X is the front of the cart, -X is where the user stands, so azimuth is
    # measured from the -X axis (looking at the contact face).
    cam.location = (
        target_obj.location[0] - dist * math.cos(el) * math.cos(az),
        target_obj.location[1] - dist * math.cos(el) * math.sin(az),
        target_obj.location[2] + dist * math.sin(el),
    )
    c = cam.constraints.new("TRACK_TO")
    c.target = target_obj
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return cam


def probe_luminance(path):
    import numpy as np

    img = bpy.data.images.load(path)
    px = np.asarray(img.pixels[:], dtype=np.float32).reshape(-1, 4)
    lum = px[:, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    bpy.data.images.remove(img)
    return float(lum.mean()), float(np.percentile(lum, 99.5))


def auto_expose(scene, cam, tmp_path, target=TARGET_LUMINANCE, rounds=3):
    w, h, pct, s, dn = (scene.render.resolution_x, scene.render.resolution_y,
                        scene.render.resolution_percentage, scene.cycles.samples,
                        scene.cycles.use_denoising)
    # low-res, low-sample probes keep a complete 8-view session practical
    scene.render.resolution_x, scene.render.resolution_y = 220, 150
    scene.render.resolution_percentage = 100
    scene.cycles.samples, scene.cycles.use_denoising = 8, False
    scene.camera = cam
    for _ in range(rounds):
        bpy.ops.render.render(write_still=True)
        mean, p99 = probe_luminance(tmp_path)
        delta = math.log2(target / max(mean, 1e-4))
        if p99 > TARGET_HIGHLIGHT:
            delta = min(delta, math.log2(TARGET_HIGHLIGHT / p99))
        delta = max(-1.5, min(1.5, delta))
        print(f"    exposure probe: mean={mean:.3f} p99={p99:.3f} -> {delta:+.2f} EV")
        if abs(delta) < 0.15:
            break
        scene.view_settings.exposure = max(-6.0, min(6.0, scene.view_settings.exposure + delta * 0.75))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = pct
    scene.cycles.samples, scene.cycles.use_denoising = s, dn
    return scene.view_settings.exposure


def main() -> None:
    want = set(sys.argv[1:])
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(root, BLEND))

    # wipe anything a previous run left behind so re-runs are idempotent
    for obj in list(bpy.data.objects):
        if obj.type in {"LIGHT", "CAMERA"} or obj.name.startswith(("TGT_", "StudioRig", "SunRig", "Studio_Floor", "HCD_Studio_Floor", "cam_")):
            bpy.data.objects.remove(obj, do_unlink=True)

    scene = bpy.context.scene
    pad_obj = bpy.data.objects["HCD_Pad"]
    cart_obj = bpy.data.objects["Shopping Cart"]
    pad = target_empty("TGT_pad", pad_obj)   # aim points from here on
    cart = target_empty("TGT_cart", cart_obj)

    # ---------------------------------------------------------------- world --
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = DENOISE
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 4
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15
    scene.render.use_persistent_data = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.015
    scene.cycles.adaptive_min_samples = 16
    scene.cycles.sample_clamp_indirect = 10.0
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg.inputs["Color"].default_value = srgb_hex_to_linear(BACKGROUND)
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    # ---------------------------------------------------------------- floor --
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, -0.002))
    floor = bpy.context.active_object
    floor.name = "Studio_Floor"
    floor.data.materials.append(simple_material("Studio_Floor_Mat", FLOOR, 0.85))

    bar = build_bar_stub(pad, cart_obj)
    studio, sunrig = build_rigs(pad, cart)

    out_dir = os.path.join(root, OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    scene.render.filepath = os.path.join(out_dir, "_probe.png")

    for name, dist, az, el, lens, rig, target_name in VIEWS:
        if want and not any(w in name for w in want):
            continue
        target = pad if target_name == "pad" else cart
        cam = camera_for("cam_" + name, target, dist, az, el, lens)
        scene.camera = cam

        studio.hide_render = rig != "studio"
        sunrig.hide_render = rig != "sun"
        for child in studio.children:
            child.hide_render = studio.hide_render
        for child in sunrig.children:
            child.hide_render = sunrig.hide_render
        # close-ups: pad on the bar stub, cart hidden. Wide shots: the reverse.
        cart_obj.hide_render = rig == "studio"
        bar.hide_render = rig != "studio"
        floor.hide_render = rig == "studio"

        scene.view_settings.exposure = 0.0
        scene.render.resolution_percentage = 100
        probe_path = os.path.join(out_dir, "_probe.png")
        scene.render.filepath = probe_path
        ev = auto_expose(scene, cam, probe_path)
        scene.render.resolution_percentage = 100
        scene.render.filepath = os.path.join(out_dir, name + ".png")
        bpy.ops.render.render(write_still=True)
        print(f"  {name:<14} exposure {ev:+.2f} EV  -> {name}.png")

    try:
        os.remove(os.path.join(out_dir, "_probe.png"))
    except OSError:
        pass
    # deliberately not saved: lights/cameras/floor are render-only scaffolding
    print(f"\nrenders in {OUT_DIR}")


if __name__ == "__main__":
    main()
