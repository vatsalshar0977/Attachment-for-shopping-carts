#!/usr/bin/env python3
"""Create a separate, stackability-focused follow-up iteration.

Interpretation: in use, the broad pad hangs below the cart handle. To stow,
it swings up and over the handle, moves above the rear basket rim, turns down,
and parks upright in the cart's child-seat plane instead of lying across the
basket opening. The source scene is read only; this script saves to this folder.

Run from the repository root:
    LD_LIBRARY_PATH=$HOME/tools/bpy-stubs python3 blender/stackable_iteration/scripts/build_stackable_iteration.py
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[3]
SOURCE_BLEND = REPO / "blender/source/hcd mockup.blend"
OUTPUT_BLEND = REPO / "blender/stackable_iteration/source/stackable leaning support.blend"

# Blender frames for the conceptual up-over-and-down path.
DEPLOYED = 1
LIFTED = 8
OVER_HANDLE = 16
ABOVE_BASKET = 22
CHILD_SEAT = 29
STOWED = 35

# Reuse only the established, geometry-neutral mesh/material helpers. The
# original design's file is never opened for writing by this script.
sys.path.insert(0, str(REPO / "blender/scripts"))
import build_attachment as geom  # noqa: E402


def keyframe_rod(obj: bpy.types.Object, start: Vector, end: Vector,
                 frame: int, radius: float) -> None:
    axis = end - start
    length = axis.length
    if length < 0.005:
        raise RuntimeError(f"{obj.name} collapsed at frame {frame}")
    obj.location = (start + end) * 0.5
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = axis.normalized().to_track_quat("Z", "Y")
    obj.scale = (radius * 2.0, radius * 2.0, length)
    for path in ("location", "rotation_quaternion", "scale"):
        obj.keyframe_insert(data_path=path, frame=frame)


def animated_cylinder(name: str, collection: bpy.types.Collection,
                      mat: bpy.types.Material) -> bpy.types.Object:
    obj = geom.cylinder_mesh(name, 0.5, 1.0, collection, mat, vertices=32)
    obj.rotation_mode = "QUATERNION"
    obj["Animation"] = "Telescoping member of the handle-to-panel carrier"
    return obj


def build() -> None:
    if not SOURCE_BLEND.exists():
        raise FileNotFoundError(f"Reference scene missing: {SOURCE_BLEND}")
    OUTPUT_BLEND.parent.mkdir(parents=True, exist_ok=True)

    # Open the old scene as read-only input, then replace generated HCD objects
    # only in memory. Saving below targets a different path under this folder.
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))
    geom.clear_previous_build()
    scene = bpy.context.scene
    cart = bpy.data.objects.get("Shopping Cart")
    if cart is None:
        raise RuntimeError("Shopping Cart mesh not found in the reference scene")

    assembly = geom.ensure_collection("HCD - Stackable Iteration")
    presentation = geom.ensure_collection("HCD - Stackable Presentation")
    handle_x, handle_y, handle_z, cart_y_min, cart_y_max = geom.measure_handle(cart)
    print(f"Measured handle centre ({handle_x:+.4f}, {handle_y:+.4f}, {handle_z:.4f}) m; "
          f"basket width {cart_y_max - cart_y_min:.3f} m")

    metal = geom.material("HCD_Stackable_Aluminium", "#8795A2", 0.29, 0.78)
    dark = geom.material("HCD_Stackable_Graphite", "#28333E", 0.42, 0.36)
    shell_mat = geom.material("HCD_Stackable_Shell", "#596775", 0.43, 0.22)
    accent = geom.material("HCD_Stackable_Release_Accent", "#E5A044", 0.34, 0.12)
    cushion_mat = geom.soft_tpe_material()

    # Deployed panel pivot sits just below the measured crossbar. When stored,
    # it finishes upright, flush to the rear child-seat zone, not across the tub.
    deployed_pivot = Vector((handle_x, handle_y, handle_z - 0.085))
    over_pivot = Vector((handle_x + 0.155, handle_y, handle_z + 0.158))
    stowed_pivot = Vector((handle_x + 0.104, handle_y, 0.760))
    fold_root = geom.make_empty("HCD_Stackable_Fold_Root", assembly, deployed_pivot)
    fold_root.rotation_mode = "XYZ"
    fold_root["Function"] = "Broad leaning panel; folds up and over the handle into the child-seat plane"
    fold_root["Deployed frame"] = DEPLOYED
    fold_root["Stowed frame"] = STOWED
    fold_root["Stacking intent"] = "Panel parks upright at the rear child-seat plane; basket top remains open"
    fold_root["Fit reference"] = "Supplied cart handle, measured approx. 23.3 mm diameter"
    fold_root["Warning"] = "Concept fit only; cart nesting and leaning loads need physical testing"

    panel_shell = geom.add_box(
        "HCD_Stackable_Panel_Shell", (0.024, 0.460, 0.300),
        (-0.035, 0.0, -0.150), shell_mat, assembly, bevel=0.010,
        parent=fold_root)
    panel_shell["Part"] = "460 mm wide rigid-looking backplate"
    cushion = geom.add_box(
        "HCD_Stackable_Cushion", (0.050, 0.430, 0.260),
        (-0.072, 0.0, -0.150), cushion_mat, assembly, bevel=0.021,
        parent=fold_root)
    cushion["Part"] = "430 mm wide cushioned leaning face"
    cushion["Stowed orientation"] = "Cushion faces inward toward the child-seat area"

    side_signs = (("Left", -1.0), ("Right", 1.0))
    # Fixed handle clamps and the two panel-side hinge discs.
    for side, sign in side_signs:
        y_clamp = handle_y + sign * 0.213
        geom.add_torus(
            f"HCD_Stackable_Handle_Clamp_{side}",
            0.0233 / 2.0 + 0.0035, 0.0030,
            (handle_x, y_clamp, handle_z), metal, assembly)
        saddle = geom.add_box(
            f"HCD_Stackable_Clamp_Saddle_{side}", (0.042, 0.050, 0.044),
            (handle_x + 0.003, y_clamp, handle_z - 0.005), dark,
            assembly, bevel=0.007)
        saddle["Part"] = "Fixed clamp around the shopping-cart crossbar"
        geom.add_axis_y_cylinder(
            f"HCD_Stackable_Handle_Pivot_{side}", 0.031, 0.012,
            (handle_x, handle_y + sign * 0.245, handle_z), dark,
            assembly, bevel=0.0012)
        ear = geom.add_axis_y_cylinder(
            f"HCD_Stackable_Panel_Ear_{side}", 0.027, 0.010,
            (0.0, sign * 0.232, 0.0), metal, assembly,
            bevel=0.0010, parent=fold_root)
        ear["Part"] = "Panel hinge ear on the moving carrier"
        geom.add_axis_y_cylinder(
            f"HCD_Stackable_Hinge_Pin_{side}", 0.006, 0.018,
            (handle_x, handle_y + sign * 0.254, handle_z), metal,
            assembly, bevel=0.0008)
        lock_tab = geom.add_box(
            f"HCD_Stackable_Lock_Tab_{side}", (0.022, 0.012, 0.030),
            (-0.006, sign * 0.244, 0.030), accent, assembly,
            bevel=0.004, parent=fold_root)
        lock_tab["Part"] = "Conceptual release/position-lock tab"

    # Paired telescoping carrier arms remain attached to the handle while the
    # panel lifts above the cart rim and then lowers into the child-seat zone.
    carrier_outer: dict[str, bpy.types.Object] = {}
    carrier_inner: dict[str, bpy.types.Object] = {}
    carrier_collars: dict[str, bpy.types.Object] = {}
    arm_anchors: dict[str, Vector] = {}
    for side, sign in side_signs:
        y = handle_y + sign * 0.205
        anchor = Vector((handle_x, y, handle_z))
        arm_anchors[side] = anchor
        geom.add_sphere(f"HCD_Stackable_Handle_Joint_{side}", 0.012,
                        tuple(anchor), metal, assembly)
        geom.add_sphere(f"HCD_Stackable_Panel_Joint_{side}", 0.012,
                        (0.0, sign * 0.205, 0.0), metal, assembly,
                        parent=fold_root)
        carrier_outer[side] = animated_cylinder(
            f"HCD_Stackable_Carrier_Sleeve_{side}", assembly, dark)
        carrier_inner[side] = animated_cylinder(
            f"HCD_Stackable_Carrier_Slider_{side}", assembly, metal)
        carrier_collars[side] = geom.add_torus(
            f"HCD_Stackable_Carrier_Collar_{side}", 0.011, 0.0025,
            tuple(anchor), accent, assembly, axis_y=False)

    # Multiple transition keys make the intended "up, over, then down" route
    # explicit. The shell is above the basket mouth before it translates inward.
    poses = (
        (DEPLOYED, deployed_pivot, 0.0),
        (LIFTED, deployed_pivot, math.pi / 2.0),
        (OVER_HANDLE, over_pivot, math.pi / 2.0),
        (ABOVE_BASKET, over_pivot, math.pi),
        (CHILD_SEAT, stowed_pivot, math.pi),
        (STOWED, stowed_pivot, math.pi),
    )
    scene.frame_start, scene.frame_end = DEPLOYED, STOWED
    for frame, location, angle in poses:
        fold_root.location = location
        fold_root.rotation_euler = (0.0, angle, 0.0)
        fold_root.keyframe_insert(data_path="location", frame=frame)
        fold_root.keyframe_insert(data_path="rotation_euler", frame=frame)
        for side, sign in side_signs:
            start = arm_anchors[side]
            end = location + Vector((0.0, sign * 0.205, 0.0))
            direction = end - start
            total = direction.length
            axis = direction.normalized()
            sleeve_len = min(0.105, total * 0.72)
            sleeve_end = start + axis * sleeve_len
            inner_start = start + axis * max(0.0, sleeve_len - 0.026)
            keyframe_rod(carrier_outer[side], start, sleeve_end, frame, 0.009)
            keyframe_rod(carrier_inner[side], inner_start, end, frame, 0.0055)
            collar = carrier_collars[side]
            collar.location = sleeve_end
            collar.rotation_mode = "QUATERNION"
            collar.rotation_quaternion = axis.to_track_quat("Z", "Y")
            collar.keyframe_insert(data_path="location", frame=frame)
            collar.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            print(f"  {side} carrier @ frame {frame}: {total * 1000:.0f} mm")

    scene.timeline_markers.clear()
    for label, frame in (("DEPLOYED — leaning rest", DEPLOYED),
                         ("SWING UP — over handle", LIFTED),
                         ("ABOVE BASKET MOUTH", OVER_HANDLE),
                         ("TURN DOWN — child seat", CHILD_SEAT),
                         ("STOWED — nesting layout", STOWED)):
        scene.timeline_markers.new(label, frame=frame)

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1200, 820
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.world.color = (0.08, 0.10, 0.13)
    scene.render.filepath = "//../exports/renders/01_stackable_deployed.png"

    # Keep an inspection camera and soft lights in the new scene only.
    target = deployed_pivot + Vector((-0.06, 0.0, -0.13))
    geom.add_presentation_camera(presentation, target)
    scene.frame_set(DEPLOYED)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    fold_root.select_set(True)
    bpy.context.view_layer.objects.active = fold_root

    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))
    print(f"\nSaved separate stackability iteration: {OUTPUT_BLEND}")
    print("  source left untouched:", SOURCE_BLEND)
    print("  deployed -> lifts over handle -> crosses above rim -> parks upright at child-seat plane")
    print("  visual stackability concept only; verify actual cart nesting physically")


if __name__ == "__main__":
    build()
