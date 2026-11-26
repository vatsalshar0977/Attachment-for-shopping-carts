#!/usr/bin/env python3
"""Build five schematic rear-brake alternatives in a separate Blender file.

The supplied cart scene is read as context. This script clears generated HCD
objects only in memory and saves the brake-mechanism comparison to this folder;
it never writes to the existing lean-rest project files.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "blender/source/hcd mockup.blend"
DEST = REPO / "blender/brake_mechanisms/source/cart brake alternatives.blend"
sys.path.insert(0, str(REPO / "blender/scripts"))
import build_attachment as geom  # noqa: E402


# Color coding: neutral = cart, cyan = cable/spring, orange = linkage/cam,
# blue = hand/pad input, red = brake applied.

def make_material(name: str, hex_color: str, roughness=0.4, metallic=0.0):
    return geom.material(name, hex_color, roughness, metallic)


def box(name: str, dims, loc, mat, col, bevel=0.0, parent=None):
    return geom.add_box(name, tuple(dims), tuple(loc), mat, col,
                        bevel=bevel, parent=parent)


def rod(name: str, start, end, radius, mat, col):
    start, end = Vector(start), Vector(end)
    direction = end - start
    mesh = geom.cylinder_mesh(name, radius, direction.length, col, mat, vertices=24)
    mesh.location = (start + end) * 0.5
    mesh.rotation_mode = "QUATERNION"
    mesh.rotation_quaternion = direction.normalized().to_track_quat("Z", "Y")
    return mesh


def cable(name: str, points, radius, mat, col):
    curve = bpy.data.curves.new(name + "_Curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*Vector(co), 1.0)
    obj = bpy.data.objects.new(name, curve)
    col.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def helix(name, start, end, radius, turns, wire_radius, mat, col):
    """Short helical spring along the supplied start/end axis."""
    start, end = Vector(start), Vector(end)
    axis = end - start
    length = axis.length
    q = axis.normalized().to_track_quat("Z", "Y")
    pts = []
    steps = max(32, turns * 16)
    for i in range(steps + 1):
        t = i / steps
        angle = math.tau * turns * t
        local = Vector((radius * math.cos(angle), radius * math.sin(angle), length * t))
        pts.append(start + q @ local)
    return cable(name, pts, wire_radius, mat, col)


def pivot(name, position, radius, depth, mat, col):
    return geom.add_axis_y_cylinder(name, radius, depth, tuple(position), mat, col,
                                    bevel=min(depth * 0.15, 0.0015))


def variant_collection(name, title, how, notes, cost):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    col["Mechanism"] = title
    col["How it works"] = how
    col["Notes"] = notes
    col["Estimated cost per cart"] = cost
    col["Status"] = "Concept schematic — not an engineered brake design"
    return col


def add_wheel_brakes(shared, brake_red, wheel_x, wheel_ys, wheel_z):
    shoes = {}
    for side, y in wheel_ys.items():
        shoe_loc = Vector((wheel_x, y, wheel_z + 0.034))
        shoes[side] = shoe_loc
        shoe = box(f"BRK_Shared_Brake_Shoe_{side}", (0.024, 0.026, 0.016),
                   shoe_loc, brake_red, shared, bevel=0.003)
        shoe["State"] = "Shown in brake-applied position"
        pivot(f"BRK_Shared_Shoe_Hinge_{side}",
              (wheel_x + 0.010, y, wheel_z + 0.016), 0.008, 0.018,
              brake_red, shared)
    return shoes


def add_handle_grip(col, handle_x, handle_y, handle_z, blue, dark):
    # Trigger sleeve/grip placed on the shopper-facing segment of the bar.
    ymid = handle_y - 0.175
    sleeve = geom.add_axis_y_cylinder("BRK_Deadman_Grip_Sleeve", 0.0155, 0.105,
                                     (handle_x, ymid, handle_z), blue, col,
                                     bevel=0.0008)
    sleeve["Input"] = "Hand held = brake released; open hand = brake applied"
    box("BRK_Deadman_Trigger", (0.040, 0.045, 0.018),
        (handle_x - 0.014, ymid, handle_z - 0.022), dark, col, bevel=0.004)
    return Vector((handle_x - 0.020, ymid, handle_z - 0.025))


def build() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    geom.clear_previous_build()
    scene = bpy.context.scene
    cart = bpy.data.objects.get("Shopping Cart")
    if cart is None:
        raise RuntimeError("The source cart mesh was not found")

    handle_x, handle_y, handle_z, y_min, y_max = geom.measure_handle(cart)
    wheel_x, wheel_z = -0.398, 0.036
    wheel_ys = {"Left": -0.246, "Right": 0.246}
    print(f"Handle centre x={handle_x:+.3f}, z={handle_z:.3f} m; "
          f"rear-wheel reference x={wheel_x:+.3f}, z={wheel_z:.3f} m")

    metal = make_material("BRK_Metal_Frame", "#8996A2", 0.34, 0.72)
    dark = make_material("BRK_Dark_Grip", "#26313A", 0.42, 0.22)
    cable_mat = make_material("BRK_Cable_Cyan", "#26A6A8", 0.36, 0.25)
    linkage_mat = make_material("BRK_Linkage_Orange", "#E49A32", 0.34, 0.32)
    input_blue = make_material("BRK_Input_Blue", "#2774B8", 0.38, 0.12)
    brake_red = make_material("BRK_Brake_Red", "#D94A45", 0.42, 0.08)
    pad_blue = make_material("BRK_Lean_Pad_Blue", "#2869A8", 0.68, 0.0)
    spring_silver = make_material("BRK_Spring_Silver", "#B5C2C9", 0.28, 0.78)

    shared = bpy.data.collections.new("Brake shoes — common reference")
    scene.collection.children.link(shared)
    shared["Description"] = "Same red brake shoes are used by each alternative"
    shoes = add_wheel_brakes(shared, brake_red, wheel_x, wheel_ys, wheel_z)
    brake_points = {side: Vector(pos) for side, pos in shoes.items()}

    # Every alternative is a separate, toggleable collection placed on the same
    # cart. Only the spring-applied option is visible when the file opens.
    variants = []
    descriptions = [
        ("01 — Spring-applied cable / dead-man grip",
         "Holding the handle grip tensions the release cable; opening the grip lets springs apply both rear brakes.",
         "Fail-safe intent depends on spring-applied brake geometry and cable failure releasing the brake; verify physically.",
         "₹150–300 per cart"),
        ("02 — Push-rod with bell cranks",
         "Rigid rods run down the frame and rotate bell cranks at the rear casters to apply/release the shoes.",
         "Stiff, little stretch; requires routing space and protected joints along the frame.",
         "₹300–500 per cart"),
        ("03 — Over-centre toggle at handle",
         "A handle lever drives a toggle slightly past dead centre and against a stop, holding the locked state without hand force.",
         "Needs a positive stop, pinch-point guarding, and reliable engagement past centre.",
         "₹200–400 per cart"),
        ("04 — Pad-linked lock",
         "Loading the leaning pad pushes a plunger that holds the brake latch applied while the shopper leans.",
         "Prevents brake release during pad loading; the pad/plunger must not create a false-safe state.",
         "₹100–200 per cart"),
        ("05 — Cross-bar cam lock",
         "One cross-bar rotates two eccentric cams that press the rear-wheel brake shoes together.",
         "Locks both rear wheels together; user-supplied notes/cost were not specified.",
         "Not supplied"),
    ]
    for i, (title, how, notes, cost) in enumerate(descriptions, 1):
        col = variant_collection(f"BRK Variant {i:02d} — {title}", title, how, notes, cost)
        variants.append(col)

    # M1: spring-applied brakes released by the dead-man grip cable.
    m1 = variants[0]
    trigger = add_handle_grip(m1, handle_x, handle_y, handle_z, input_blue, dark)
    near_y = wheel_ys["Left"]
    cable(m1.name + "_Release_Cable", [
        trigger,
        (handle_x + 0.030, near_y, handle_z - 0.025),
        (handle_x + 0.050, near_y, 0.84),
        (wheel_x - 0.020, near_y, 0.40),
        (wheel_x - 0.008, near_y, wheel_z + 0.060),
    ], 0.0025, cable_mat, m1)
    rod("BRK_M1_Rear_Equalizer", (wheel_x - 0.008, -0.246, wheel_z + 0.060),
        (wheel_x - 0.008, 0.246, wheel_z + 0.060), 0.0035, linkage_mat, m1)
    for side, y in wheel_ys.items():
        helix(f"BRK_M1_Apply_Spring_{side}",
              (wheel_x - 0.008, y, wheel_z + 0.090),
              (wheel_x - 0.008, y, wheel_z + 0.046),
              0.006, 4, 0.0018, spring_silver, m1)
        rod(f"BRK_M1_Spring_To_Shoe_{side}",
            (wheel_x - 0.008, y, wheel_z + 0.050), brake_points[side],
            0.0028, linkage_mat, m1)

    # M2: two rigid rods and a bell crank at each rear caster.
    m2 = variants[1]
    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        y = wheel_ys[side]
        upper = (handle_x + 0.045, y * 0.88, handle_z - 0.06)
        lower = (wheel_x - 0.018, y * 0.92, wheel_z + 0.075)
        rod(f"BRK_M2_Push_Rod_{side}", upper, lower, 0.006, metal, m2)
        pivot(f"BRK_M2_Bellcrank_Pivot_{side}",
              (wheel_x, y * 0.94, wheel_z + 0.055), 0.010, 0.018,
              linkage_mat, m2)
        rod(f"BRK_M2_Bellcrank_In_{side}",
            (wheel_x, y * 0.94, wheel_z + 0.055), lower,
            0.0045, linkage_mat, m2)
        rod(f"BRK_M2_Bellcrank_Out_{side}",
            (wheel_x, y * 0.94, wheel_z + 0.055), brake_points[side],
            0.0045, linkage_mat, m2)
        geom.add_sphere(f"BRK_M2_Rod_Joint_{side}", 0.008,
                        lower, metal, m2)

    # M3: hand lever, knee link, positive stop, and a brake-actuation cable.
    m3 = variants[2]
    y = handle_y - 0.205
    p = Vector((handle_x, y, handle_z))
    knee = Vector((handle_x + 0.047, y, handle_z + 0.018))
    end = Vector((handle_x + 0.093, y, handle_z + 0.025))  # just past centre
    handle_end = Vector((handle_x + 0.018, y, handle_z + 0.080))
    pivot("BRK_M3_Handle_Pivot", p, 0.013, 0.020, dark, m3)
    rod("BRK_M3_Toggle_Lever", p, handle_end, 0.007, input_blue, m3)
    rod("BRK_M3_Toggle_Knee_Link", knee, end, 0.006, linkage_mat, m3)
    rod("BRK_M3_Toggle_Input_Link", p, knee, 0.006, linkage_mat, m3)
    box("BRK_M3_Overtravel_Stop", (0.020, 0.026, 0.018),
        (end.x, y, end.z + 0.018), brake_red, m3, bevel=0.003)
    cable("BRK_M3_Brake_Control", [
        end, (handle_x + 0.04, y, 0.82),
        (wheel_x - 0.015, y, 0.36),
        (wheel_x - 0.006, y, wheel_z + 0.055),
    ], 0.003, cable_mat, m3)
    cable("BRK_M3_Brake_Split", [
        (wheel_x - 0.006, y, wheel_z + 0.055),
        (wheel_x - 0.006, 0.0, wheel_z + 0.055),
        (wheel_x - 0.006, wheel_ys["Right"], wheel_z + 0.055),
    ], 0.0025, cable_mat, m3)

    # M4: a broad lean-pad reference, spring plunger, and brake-hold linkage.
    m4 = variants[3]
    linked_pad = box("BRK_M4_Lean_Pad", (0.050, 0.430, 0.235),
                     (handle_x - 0.052, handle_y, handle_z - 0.235),
                     pad_blue, m4, bevel=0.020)
    linked_pad["Input"] = "Pad load pushes a plunger to maintain brake-applied state"
    plunger_start = Vector((handle_x - 0.025, handle_y - 0.155, handle_z - 0.245))
    plunger_end = Vector((handle_x + 0.055, handle_y - 0.155, handle_z - 0.245))
    rod("BRK_M4_Pad_Plunger", plunger_start, plunger_end, 0.007, linkage_mat, m4)
    helix("BRK_M4_Plunger_Return_Spring",
          (handle_x - 0.005, handle_y - 0.155, handle_z - 0.245),
          (handle_x + 0.040, handle_y - 0.155, handle_z - 0.245),
          0.008, 5, 0.0018, spring_silver, m4)
    cable("BRK_M4_Plunger_Brake_Link", [
        plunger_end,
        (handle_x + 0.055, handle_y - 0.155, 0.72),
        (wheel_x - 0.010, handle_y - 0.18, 0.30),
        (wheel_x - 0.006, wheel_ys["Left"], wheel_z + 0.055),
    ], 0.0035, linkage_mat, m4)
    cable("BRK_M4_Brake_Split", [
        (wheel_x - 0.006, wheel_ys["Left"], wheel_z + 0.055),
        (wheel_x - 0.006, 0.0, wheel_z + 0.055),
        (wheel_x - 0.006, wheel_ys["Right"], wheel_z + 0.055),
    ], 0.0028, cable_mat, m4)

    # M5: one rear cross-bar rotates two offset cams against the shared shoes.
    m5 = variants[4]
    bar_z = wheel_z + 0.060
    rod("BRK_M5_Cross_Bar", (wheel_x - 0.012, -0.270, bar_z),
        (wheel_x - 0.012, 0.270, bar_z), 0.007, linkage_mat, m5)
    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        y = wheel_ys[side]
        pivot_pos = (wheel_x - 0.012, y, bar_z)
        # The lobe centre is offset from the shaft centre to show cam action.
        cam = geom.add_axis_y_cylinder(
            f"BRK_M5_Eccentric_Cam_{side}", 0.025, 0.018,
            (wheel_x - 0.012, y, bar_z + 0.010), linkage_mat, m5,
            bevel=0.0012)
        cam["Part"] = "Eccentric lobe on the shared cross-bar"
        pivot(f"BRK_M5_Cam_Hub_{side}", pivot_pos, 0.009, 0.022, dark, m5)
        rod(f"BRK_M5_Cam_Follower_{side}",
            (wheel_x - 0.012, y, bar_z + 0.028), brake_points[side],
            0.0045, brake_red, m5)

    # Default to variant 1 only; all other alternatives remain available as
    # separately toggleable, overlapping collections in the Outliner.
    for i, col in enumerate(variants, 1):
        col.hide_render = i != 1
        col.hide_viewport = i != 1
        col["Alternative number"] = i
        print(f"  Variant {i}: {col.get('Mechanism')} | {col.get('Estimated cost per cart')}")

    presentation = bpy.data.collections.new("Brake Comparison Presentation")
    scene.collection.children.link(presentation)
    geom.add_presentation_camera(presentation, Vector((handle_x + 0.06, handle_y, 0.60)))
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1200, 820
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.world.color = (0.06, 0.075, 0.09)
    scene.frame_set(1)
    scene.render.filepath = "//../exports/renders/M1_spring_applied_cable.png"
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(DEST))
    print(f"\nSaved separate brake-mechanism comparison: {DEST}")
    print("The existing cart attachment scene was only read, not saved over.")


if __name__ == "__main__":
    build()
