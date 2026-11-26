#!/usr/bin/env python3
"""Build a separate handle-lever brake study on the supplied cart reference.

The hand lever is mounted at the cart handle. A Bowden cable routes down the
frame to an equalizer that applies both rear-wheel shoes. The friction parts
remain at the wheels; the control is at the handle. The source cart and all
other project scenes are read-only inputs.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[3]
CART_SOURCE = REPO / "blender/source/hcd mockup.blend"
STUDY_ROOT = REPO / "blender/handle_brake_study"
BLEND_OUT = STUDY_ROOT / "source/handle_lever_rear_brake.blend"
RENDER_OUT = STUDY_ROOT / "exports/renders"
sys.path.insert(0, str(REPO / "blender/scripts"))
sys.path.insert(0, str(REPO / "blender/brake_mechanisms/scripts"))
import build_attachment as geom  # noqa: E402
import build_brake_mechanisms as brk  # noqa: E402

HANDLE = Vector((-0.4944, 0.0, 1.0917))
WHEEL_X = -0.398
WHEEL_BASE_Z = 0.036
WHEEL_YS = {"Near": -0.246, "Far": 0.246}


def rod(name, start, end, radius, material, col):
    return brk.rod(name, start, end, radius, material, col)


def cable(name, points, radius, material, col):
    return brk.cable(name, points, radius, material, col)


def spring(name, start, end, radius, turns, wire, material, col):
    return brk.helix(name, start, end, radius, turns, wire, material, col)


def box(name, dimensions, location, material, col, bevel=0.0):
    return geom.add_box(name, tuple(dimensions), tuple(location), material, col, bevel=bevel)


def pivot(name, position, radius, depth, material, col):
    return brk.pivot(name, position, radius, depth, material, col)


def look_at(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_camera(name, target, location, lens=65, ortho_scale=None):
    data = bpy.data.cameras.new(name + "_Data")
    if ortho_scale is None:
        data.type = "PERSP"
        data.lens = lens
    else:
        data.type = "ORTHO"
        data.ortho_scale = ortho_scale
    camera = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = target + Vector(location)
    look_at(camera, target)
    return camera


def add_light(name, target, offset, energy, size, color):
    data = bpy.data.lights.new(name + "_Data", "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    light = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(light)
    light.location = target + Vector(offset)
    look_at(light, target)
    return light


def build():
    if not CART_SOURCE.exists():
        raise FileNotFoundError(CART_SOURCE)
    BLEND_OUT.parent.mkdir(parents=True, exist_ok=True)
    RENDER_OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(CART_SOURCE))
    scene = bpy.context.scene
    geom.clear_previous_build()
    cart = bpy.data.objects.get("Shopping Cart")
    if cart is None:
        raise RuntimeError("The supplied Shopping Cart mesh was not found")

    for obj in list(bpy.data.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)

    # All changes are in the new study scene; the original cart file remains untouched.
    frame = geom.material("HND_Frame_Metal", "#66737D", 0.58, 0.30)
    dark = geom.material("HND_Dark_Hardware", "#26323B", 0.52, 0.16)
    lever_blue = geom.material("HND_Handle_Control_Blue", "#347FBD", 0.38, 0.08)
    linkage_orange = geom.material("HND_Linkage_Orange", "#E39438", 0.36, 0.24)
    cable_cyan = geom.material("HND_Control_Cable_Cyan", "#28A9B5", 0.35, 0.12)
    brake_red = geom.material("HND_Applied_Brake_Red", "#D94D48", 0.42, 0.08)
    spring_silver = geom.material("HND_Return_Spring_Silver", "#BBC5C9", 0.30, 0.62)
    cart_material = geom.material("HND_Render_Cart_Metal", "#5F6B75", 0.62, 0.22)
    floor_material = geom.material("HND_Render_Floor", "#343D47", 0.88, 0.0)
    cart.data.materials.clear()
    cart.data.materials.append(cart_material)

    study = bpy.data.collections.new("Handle-operated rear brake study")
    scene.collection.children.link(study)
    study["Operating concept"] = (
        "Squeeze the hand lever at the cart handle; a Bowden cable and equalizer "
        "pull both rear-wheel shoes into the applied position."
    )
    study["Status"] = "Schematic only — not engineered, load-rated, or safety-validated"
    study["Cost estimate"] = "Not supplied"
    study["Design note"] = (
        "The control lever is at the handle; the friction shoes must still contact the wheels. "
        "Cable-break and return-spring behaviour require testing."
    )

    # Hand-lever clamp and squeeze lever on the near end of the cart handle.
    handle_y = -0.190
    lever_pivot = Vector((HANDLE.x + 0.008, handle_y, HANDLE.z - 0.004))
    lever_tip = Vector((HANDLE.x + 0.060, handle_y, HANDLE.z - 0.092))
    pivot("HND_Handle_Lever_Pivot", lever_pivot, 0.011, 0.026, dark, study)
    geom.add_axis_y_cylinder(
        "HND_Handlebar_Clamp", 0.018, 0.052,
        (HANDLE.x + 0.005, handle_y, HANDLE.z), frame, study, bevel=0.001,
    )
    lever = rod("HND_Squeeze_Lever", lever_pivot, lever_tip, 0.0065, lever_blue, study)
    lever["Input"] = "Hand squeeze at cart handle applies both rear brakes"
    box("HND_Lever_Finger_Paddle", (0.024, 0.040, 0.014),
        (lever_tip.x, lever_tip.y, lever_tip.z), lever_blue, study, bevel=0.004)
    # A short barrel adjuster makes the control/cable interface visible.
    geom.add_axis_y_cylinder(
        "HND_Cable_Adjuster", 0.007, 0.034,
        (lever_tip.x - 0.008, handle_y - 0.022, lever_tip.z + 0.008),
        linkage_orange, study, bevel=0.0008,
    )

    # Main Bowden cable follows the rear frame and terminates at a transverse equalizer.
    near_y = WHEEL_YS["Near"]
    cable_entry = (lever_tip.x - 0.008, handle_y - 0.025, lever_tip.z + 0.008)
    equalizer_z = WHEEL_BASE_Z + 0.103
    cable("HND_Main_Bowden_Cable", [
        cable_entry,
        (HANDLE.x + 0.030, near_y, HANDLE.z - 0.180),
        (HANDLE.x + 0.052, near_y, 0.77),
        (WHEEL_X + 0.035, near_y, 0.40),
        (WHEEL_X + 0.012, near_y, equalizer_z),
    ], 0.0038, cable_cyan, study)
    rod("HND_Rear_Cable_Equalizer", (WHEEL_X - 0.005, -0.260, equalizer_z),
        (WHEEL_X - 0.005, 0.260, equalizer_z), 0.0055, linkage_orange, study)

    for side, y in WHEEL_YS.items():
        shoe_position = Vector((WHEEL_X, y, WHEEL_BASE_Z + 0.034))
        shoe = box(f"HND_Applied_Brake_Shoe_{side}", (0.024, 0.026, 0.016),
                   shoe_position, brake_red, study, bevel=0.003)
        shoe["State"] = "Shown pressed against the rear wheel"
        hinge_position = Vector((WHEEL_X + 0.010, y, WHEEL_BASE_Z + 0.016))
        pivot(f"HND_Shoe_Hinge_{side}", hinge_position, 0.008, 0.018,
              dark, study)
        rod(f"HND_Shoe_Actuator_{side}",
            (WHEEL_X - 0.005, y, equalizer_z),
            (WHEEL_X + 0.004, y, WHEEL_BASE_Z + 0.047),
            0.0048, linkage_orange, study)
        spring(f"HND_Shoe_Return_Spring_{side}",
               (WHEEL_X + 0.016, y, WHEEL_BASE_Z + 0.084),
               (WHEEL_X + 0.016, y, WHEEL_BASE_Z + 0.045),
               0.0055, 4, 0.0017, spring_silver, study)
        if side == "Far":
            cable(f"HND_Equalizer_Branch_{side}", [
                (WHEEL_X - 0.005, near_y, equalizer_z),
                (WHEEL_X - 0.005, 0.0, equalizer_z),
                (WHEEL_X - 0.005, y, equalizer_z),
            ], 0.0032, cable_cyan, study)

    # Three saved cameras make the handle control, full route, and wheel interface inspectable.
    cameras = [
        add_camera("STUDY_Camera_Overview", Vector((-0.435, -0.205, 0.565)),
                   (0.03, -2.8, 0.36), ortho_scale=1.70),
        add_camera("STUDY_Camera_Handle_Detail", lever_pivot + Vector((0.008, 0.0, -0.008)),
                   (-0.28, -0.88, 0.24), lens=78),
        add_camera("STUDY_Camera_Wheel_Detail", Vector((WHEEL_X, near_y, WHEEL_BASE_Z + 0.040)),
                   (-0.36, -0.95, 0.25), lens=82),
    ]
    scene.camera = cameras[0]

    bpy.ops.mesh.primitive_plane_add(size=100, location=(0.0, 0.0, -0.004))
    floor = bpy.context.object
    floor.name = "HND_Render_Floor"
    floor.data.materials.append(floor_material)
    presentation = bpy.data.collections.new("Handle Brake Presentation Rig")
    scene.collection.children.link(presentation)
    for obj in [floor, *cameras]:
        for old_col in list(obj.users_collection):
            old_col.objects.unlink(obj)
        presentation.objects.link(obj)
    add_light("HND_Key_Light", Vector((-0.435, -0.205, 0.565)),
              (-0.85, -1.0, 1.35), 90, 1.2, (1.0, 0.88, 0.76))
    add_light("HND_Fill_Light", Vector((-0.435, -0.205, 0.565)),
              (0.65, 0.75, 0.7), 55, 1.45, (0.77, 0.86, 1.0))
    add_light("HND_Rim_Light", Vector((-0.435, -0.205, 0.565)),
              (0.7, -0.1, 1.5), 100, 0.9, (0.82, 0.91, 1.0))
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            for old_col in list(obj.users_collection):
                old_col.objects.unlink(obj)
            presentation.objects.link(obj)

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes.clear()
    background = world.node_tree.nodes.new("ShaderNodeBackground")
    output = world.node_tree.nodes.new("ShaderNodeOutputWorld")
    background.inputs["Color"].default_value = (0.015, 0.020, 0.026, 1.0)
    background.inputs["Strength"].default_value = 0.55
    world.node_tree.links.new(background.outputs["Background"], output.inputs["Surface"])
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
    scene.frame_set(1)
    scene["Study"] = "Handle-lever-actuated rear-wheel brake"
    scene["Engineering status"] = "Schematic only; not engineered, load-rated, or safety validated"
    scene.render.filepath = "//../exports/renders/handle_brake_overview.png"
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"Saved separate handle-brake study: {BLEND_OUT}")
    print("The cart source and M6–M9 studies were not modified.")


if __name__ == "__main__":
    build()
