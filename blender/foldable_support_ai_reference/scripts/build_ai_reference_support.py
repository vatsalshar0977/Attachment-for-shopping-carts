#!/usr/bin/env python3
"""Build a fresh foldable cart-leaning support from the newer AI render.

This scene is built from the original cart reference and the newer render only;
it does not import or modify the earlier sketch-proportion support model.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[3]
CART_SOURCE = REPO / "blender/source/hcd mockup.blend"
PROJECT = REPO / "blender/foldable_support_ai_reference"
BLEND_OUT = PROJECT / "source/foldable_leaning_support.blend"
RENDER_DIR = PROJECT / "exports/renders"
sys.path.insert(0, str(REPO / "blender/scripts"))
sys.path.insert(0, str(REPO / "blender/brake_mechanisms/scripts"))
import build_attachment as geom  # noqa: E402
import build_brake_mechanisms as brk  # noqa: E402

HANDLE = Vector((-0.4944, 0.0, 1.0917))
HINGE = Vector((-0.548, 0.0, 0.962))
PANEL_WIDTH = 0.460
PANEL_HEIGHT = 0.280
PANEL_THICKNESS = 0.058
DEPLOY_ANGLE = math.radians(12.0)
MATS: dict[str, bpy.types.Material] = {}


def mat(key):
    return MATS[key]


def link_to(obj, collection):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    collection.objects.link(obj)


def new_collection(name, description, parent=None):
    col = bpy.data.collections.new(name)
    (parent.children if parent else bpy.context.scene.collection.children).link(col)
    col["Description"] = description
    return col


def add_materials():
    MATS.clear()
    MATS.update({
        "metal": geom.material("AIREF_Brushed_Aluminium", "#A6ADB2", 0.30, 0.72),
        "metal_dark": geom.material("AIREF_Dark_Anodised_Metal", "#41474D", 0.34, 0.62),
        "rubber": geom.material("AIREF_Clamp_Rubber", "#181C20", 0.82, 0.0),
        "cushion": geom.material("AIREF_Charcoal_Cushion", "#20242A", 0.72, 0.0),
        "seam": geom.material("AIREF_Cushion_Seam", "#333941", 0.68, 0.0),
        "accent": geom.material("AIREF_Lock_Accent", "#B96F35", 0.38, 0.22),
        "pin": geom.material("AIREF_Quick_Release_Pin", "#D0D5D8", 0.26, 0.78),
        "cart": geom.material("AIREF_Render_Cart", "#68737D", 0.55, 0.30),
        "floor": geom.material("AIREF_Render_Floor", "#3C444D", 0.88, 0.0),
    })
    # Fine, subtle grain keeps the black pad from reading as glossy plastic.
    cushion = mat("cushion")
    bsdf = cushion.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.72
    noise = cushion.node_tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 240.0
    noise.inputs["Detail"].default_value = 2.0
    bump = cushion.node_tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.00018
    cushion.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    cushion.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def add_box(name, dimensions, location, material, collection, bevel=0.0, parent=None):
    return geom.add_box(name, tuple(dimensions), tuple(location), material, collection,
                        bevel=bevel, parent=parent)


def add_rod(name, start, end, radius, material, collection):
    return brk.rod(name, start, end, radius, material, collection)


def add_rod_local(name, start, end, radius, material, collection, parent):
    start, end = Vector(start), Vector(end)
    direction = end - start
    obj = brk.rod(name, start, end, radius, material, collection)
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.location = (start + end) * 0.5
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.normalized().to_track_quat("Z", "Y")
    return obj


def add_cylinder_y(name, radius, depth, position, material, collection,
                   bevel=0.001, parent=None):
    return geom.add_axis_y_cylinder(name, radius, depth, tuple(position), material,
                                    collection, bevel=bevel, parent=parent)


def add_sphere(name, radius, position, material, collection, parent=None):
    return geom.add_sphere(name, radius, tuple(position), material, collection, parent=parent)


def add_curve(name, points, radius, material, collection):
    curve = bpy.data.curves.new(name + "_Curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = radius
    curve.bevel_resolution = 4
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*Vector(co), 1.0)
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    curve.materials.append(material)
    return obj


def add_c_clamp(name, center, y, radius, collection, side_label):
    """An open C-collar around the cart tube with a quick-release cam lever."""
    center = Vector(center)
    points = []
    start, end, steps = -128.0, 128.0, 40
    for i in range(steps + 1):
        angle = math.radians(start + (end - start) * i / steps)
        points.append((center.x + radius * math.cos(angle), y,
                       center.z + radius * math.sin(angle)))
    add_curve(name + "_C_Strap", points, 0.0036, mat("metal"), collection)

    for label, angle_deg in (("Lower", start), ("Upper", end)):
        a = math.radians(angle_deg)
        jaw = Vector((center.x + radius * math.cos(a), y,
                      center.z + radius * math.sin(a)))
        add_box(f"{name}_{label}_Jaw", (0.024, 0.028, 0.020), jaw,
                mat("metal_dark"), collection, bevel=0.004)
        add_cylinder_y(f"{name}_{label}_Jaw_Pin", 0.0048, 0.036,
                       (jaw.x, y, jaw.z), mat("pin"), collection, bevel=0.0006)

    cam_pivot = Vector((center.x - radius * 0.53, y - 0.012, center.z - radius * 0.78))
    cam_end = cam_pivot + Vector((-0.038, 0.0, -0.028))
    add_cylinder_y(name + "_Cam_Pivot", 0.009, 0.034, cam_pivot,
                   mat("accent"), collection, bevel=0.001)
    add_rod(name + "_Quick_Release_Lever", cam_pivot, cam_end,
            0.0055, mat("metal_dark"), collection)
    add_box(name + "_Lever_Grip", (0.056, 0.030, 0.012),
            cam_end + Vector((-0.014, 0.0, -0.003)), mat("rubber"),
            collection, bevel=0.005)
    # Elastomer liner between the clamp and cart tube.
    add_curve(name + "_Inner_Liner", [
        (center.x + (radius - 0.002) * math.cos(math.radians(a)), y,
         center.z + (radius - 0.002) * math.sin(math.radians(a)))
        for a in range(-115, 116, 8)
    ], 0.0018, mat("rubber"), collection)


def rotate_y(v, angle):
    c, s = math.cos(angle), math.sin(angle)
    return Vector((c * v.x + s * v.z, v.y, -s * v.x + c * v.z))


def add_rosette(name, center, side, collection):
    add_cylinder_y(name + "_Detent_Disc", 0.032, 0.014, center,
                   mat("metal_dark"), collection, bevel=0.001)
    add_cylinder_y(name + "_Pivot_Boss", 0.013, 0.022, center,
                   mat("metal"), collection, bevel=0.001)
    add_cylinder_y(name + "_Lock_Button", 0.0065, 0.027, center,
                   mat("accent"), collection, bevel=0.0008)
    # Eight visible detent marks imply indexed panel-angle adjustment.
    for i in range(8):
        angle = math.tau * i / 8.0
        p = Vector((center[0] + 0.024 * math.cos(angle),
                    center[1] + side * 0.010,
                    center[2] + 0.024 * math.sin(angle)))
        add_sphere(f"{name}_Detent_Mark_{i+1}", 0.0025, p,
                   mat("rubber"), collection)


def add_part_a(collection):
    """C-clamps, quick-release hardware, standoffs, and two-axis hinge mount."""
    for index, y in enumerate((-0.195, 0.195), 1):
        add_c_clamp(f"AIREF_PartA_Handle_Clamp_{index}", HANDLE, y, 0.017,
                    collection, f"{index}")
        # Rigid standoff from the handle collar to the panel pivot.
        add_rod(f"AIREF_PartA_Standoff_{index}",
                (HANDLE.x + 0.018, y, HANDLE.z - 0.015),
                (HINGE.x + 0.016, y, HINGE.z),
                0.010, mat("metal"), collection)
        add_cylinder_y(f"AIREF_PartA_Standoff_End_{index}", 0.014, 0.034,
                       (HINGE.x + 0.016, y, HINGE.z),
                       mat("metal_dark"), collection, bevel=0.001)

    add_rod("AIREF_PartA_Transverse_Hinge_Axle",
            (HINGE.x, -0.244, HINGE.z), (HINGE.x, 0.244, HINGE.z),
            0.011, mat("metal"), collection)
    for side, y, sign in (("Near", -0.238, -1), ("Far", 0.238, 1)):
        add_rosette(f"AIREF_PartA_{side}_Angle_Rosette",
                    (HINGE.x, y, HINGE.z), sign, collection)
        # Radial yoke plate from the indexed pivot toward the pad hinge.
        add_rod(f"AIREF_PartA_{side}_Yoke_Arm",
                (HINGE.x + 0.014, y, HINGE.z),
                (HINGE.x + 0.020, y, HINGE.z - 0.045),
                0.009, mat("metal_dark"), collection)
    collection["Part"] = "Part A — open tube clamps, cam levers, and indexed hinge"


def add_pad_pose(pose_collection, pose_name, angle):
    panel = new_collection(f"{pose_name} — Cushioned panel", "Rounded charcoal leaning pad with a hinge barrel.", pose_collection)
    root = bpy.data.objects.new(f"AIREF_{pose_name}_Panel_Pivot", None)
    panel.objects.link(root)
    root.empty_display_type = "CIRCLE"
    root.empty_display_size = 0.04
    root.location = HINGE
    root.rotation_euler = (0.0, angle, 0.0)
    root["Movement"] = "Rotates around the transverse hinge axis"

    z_center = -PANEL_HEIGHT / 2.0
    add_box(f"AIREF_{pose_name}_Panel_Shell",
            (PANEL_THICKNESS, PANEL_WIDTH, PANEL_HEIGHT),
            (0.002, 0.0, z_center), mat("metal_dark"), panel,
            bevel=0.040, parent=root)
    add_box(f"AIREF_{pose_name}_Soft_Pad",
            (0.028, PANEL_WIDTH - 0.032, PANEL_HEIGHT - 0.032),
            (-0.038, 0.0, z_center), mat("cushion"), panel,
            bevel=0.038, parent=root)
    # Narrow peripheral seam around the pad and a soft inset perimeter lip.
    add_box(f"AIREF_{pose_name}_Pad_Inset",
            (0.009, PANEL_WIDTH - 0.060, PANEL_HEIGHT - 0.060),
            (-0.055, 0.0, z_center), mat("seam"), panel,
            bevel=0.030, parent=root)
    add_box(f"AIREF_{pose_name}_Pad_Face",
            (0.006, PANEL_WIDTH - 0.078, PANEL_HEIGHT - 0.078),
            (-0.060, 0.0, z_center), mat("cushion"), panel,
            bevel=0.027, parent=root)

    # Wide pivot barrel and end fittings, matching the cylindrical hinge in the reference.
    add_cylinder_y(f"AIREF_{pose_name}_Hinge_Barrel", 0.024, PANEL_WIDTH + 0.035,
                   (0.010, 0.0, 0.020), mat("metal_dark"), panel,
                   bevel=0.002, parent=root)
    for side, y in (("L", -PANEL_WIDTH / 2.0), ("R", PANEL_WIDTH / 2.0)):
        add_cylinder_y(f"AIREF_{pose_name}_Hinge_EndCap_{side}", 0.027, 0.020,
                       (0.010, y, 0.020), mat("metal"), panel,
                       bevel=0.0015, parent=root)
        add_cylinder_y(f"AIREF_{pose_name}_Hinge_Pin_{side}", 0.007, 0.024,
                       (0.010, y, 0.020), mat("accent"), panel,
                       bevel=0.0008, parent=root)
        # Small rear shell ribs and side cheeks strengthen the pivot area visually.
        add_box(f"AIREF_{pose_name}_Rear_Cheek_{side}", (0.028, 0.022, 0.085),
                (0.035, y * 0.88, -0.048), mat("metal_dark"), panel,
                bevel=0.008, parent=root)
    panel["Part"] = "Main rounded, cushioned leaning panel"
    return root


def add_adjustable_strut(pose_collection, panel_angle):
    part_b = new_collection("Part B — Slotted telescopic support", "One adjustable tube strut with pin lock and clevis ends.", pose_collection)
    panel_joint_local = Vector((0.018, 0.0, -PANEL_HEIGHT * 0.80))
    panel_joint = HINGE + rotate_y(panel_joint_local, panel_angle)
    # The upper anchor is carried by Part A's clamp/yoke; the lower end pivots on the pad.
    upper_anchor = Vector((HANDLE.x + 0.012, 0.0, HANDLE.z - 0.055))
    axis = upper_anchor - panel_joint
    length = axis.length
    direction = axis.normalized()
    outer_start = panel_joint + direction * 0.020
    sleeve_at = panel_joint + direction * (length * 0.60)
    inner_start = panel_joint + direction * (length * 0.53)
    inner_end = upper_anchor - direction * 0.020

    # Forked pivots at both ends.
    for label, point in (("Pad", panel_joint), ("Mount", upper_anchor)):
        add_box(f"AIREF_PartB_{label}_Clevis_Left", (0.030, 0.010, 0.032),
                point + Vector((0.0, -0.014, 0.0)), mat("metal_dark"), part_b,
                bevel=0.004)
        add_box(f"AIREF_PartB_{label}_Clevis_Right", (0.030, 0.010, 0.032),
                point + Vector((0.0, 0.014, 0.0)), mat("metal_dark"), part_b,
                bevel=0.004)
        add_cylinder_y(f"AIREF_PartB_{label}_Pivot_Pin", 0.006, 0.042,
                       point, mat("accent"), part_b, bevel=0.0008)

    add_rod("AIREF_PartB_Outer_Telescopic_Tube", outer_start, sleeve_at,
            0.014, mat("metal"), part_b)
    add_rod("AIREF_PartB_Inner_Sliding_Rod", inner_start, inner_end,
            0.009, mat("metal_dark"), part_b)
    collar_mid = panel_joint + direction * (length * 0.575)
    add_rod("AIREF_PartB_Adjustment_Collar",
            collar_mid - direction * 0.013, collar_mid + direction * 0.013,
            0.020, mat("accent"), part_b)
    add_cylinder_y("AIREF_PartB_Quick_Release_Pin", 0.0065, 0.046,
                   collar_mid, mat("pin"), part_b, bevel=0.0008)
    # A long adjustment slot and index holes are modeled on the tube's visible side.
    side_vector = Vector((-direction.z, 0.0, direction.x)).normalized()
    slot_start = panel_joint + direction * (length * 0.20) + side_vector * 0.012
    slot_end = panel_joint + direction * (length * 0.46) + side_vector * 0.012
    add_rod("AIREF_PartB_Adjustment_Slot", slot_start, slot_end,
            0.0022, mat("rubber"), part_b)
    for i, t in enumerate((0.28, 0.36, 0.44, 0.52), 1):
        pos = panel_joint + direction * (length * t) + side_vector * 0.013
        add_sphere(f"AIREF_PartB_Index_Hole_{i}", 0.0038, pos,
                   mat("rubber"), part_b)
    part_b["Part"] = "Part B — adjustable locking strut"
    part_b["Adjustment"] = "Sliding inner tube, elongated slot, and quick-release pin"
    return part_b


def add_folded_strut(pose_collection, panel_root):
    part_b = new_collection("Part B — Folded telescopic support", "Compressed strut nested along the panel underside.", pose_collection)
    add_rod_local("AIREF_Folded_PartB_Outer_Tube",
                  (0.035, 0.0, -0.040), (0.035, 0.0, -0.145),
                  0.014, mat("metal"), part_b, panel_root)
    add_rod_local("AIREF_Folded_PartB_Inner_Rod",
                  (0.035, 0.0, -0.130), (0.035, 0.0, -0.245),
                  0.009, mat("metal_dark"), part_b, panel_root)
    add_cylinder_y("AIREF_Folded_PartB_Lock_Collar", 0.020, 0.032,
                   (0.035, 0.0, -0.138), mat("accent"), part_b,
                   bevel=0.001, parent=panel_root)
    add_cylinder_y("AIREF_Folded_PartB_Lock_Pin", 0.006, 0.044,
                   (0.035, 0.0, -0.138), mat("pin"), part_b,
                   bevel=0.0008, parent=panel_root)


def add_camera(name, collection, target, offset, lens=55):
    data = bpy.data.cameras.new(name + "_Data")
    data.type = "PERSP"
    data.lens = lens
    camera = bpy.data.objects.new(name, data)
    collection.objects.link(camera)
    camera.location = target + Vector(offset)
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    return camera


def add_light(name, collection, target, offset, energy, size, color):
    data = bpy.data.lights.new(name + "_Data", "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    light = bpy.data.objects.new(name, data)
    collection.objects.link(light)
    light.location = target + Vector(offset)
    light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
    return light


def setup_scene(scene):
    scene.unit_settings.system = "METRIC"
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
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes.clear()
    bg = world.node_tree.nodes.new("ShaderNodeBackground")
    out = world.node_tree.nodes.new("ShaderNodeOutputWorld")
    bg.inputs["Color"].default_value = (0.018, 0.022, 0.028, 1.0)
    bg.inputs["Strength"].default_value = 0.50
    world.node_tree.links.new(bg.outputs["Background"], out.inputs["Surface"])


def build():
    if not CART_SOURCE.exists():
        raise FileNotFoundError(CART_SOURCE)
    BLEND_OUT.parent.mkdir(parents=True, exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(CART_SOURCE))
    scene = bpy.context.scene
    setup_scene(scene)
    geom.clear_previous_build()
    for obj in list(bpy.data.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    cart = bpy.data.objects.get("Shopping Cart")
    if cart is None:
        raise RuntimeError("Shopping Cart mesh missing from the original reference scene")

    add_materials()
    cart.data.materials.clear()
    cart.data.materials.append(mat("cart"))
    scene["Product"] = "Foldable clamp-on cart leaning support"
    scene["Reference"] = "New AI render supplied by user"
    scene["Scale"] = "Proportional concept; no dimensions supplied"
    scene["Use"] = "Leaning support only — not a seat"
    scene["Status"] = "Not fit-validated, load-rated, or safety-certified"

    assembly = new_collection("AI-render reference assembly",
                              "New interpretation of the user's render: clamp, pivot pad, and adjustable strut.")
    part_a = new_collection("PART A — Tube clamp and pivot mount",
                            "Open C-clamps with quick-release cams and indexed panel-angle pivots.", assembly)
    add_part_a(part_a)

    deployed = new_collection("POSE — Deployed support", "Default assembled leaning-support pose.", assembly)
    deployed["State"] = "Deployed"
    add_pad_pose(deployed, "Deployed", DEPLOY_ANGLE)
    add_adjustable_strut(deployed, DEPLOY_ANGLE)
    deployed.hide_viewport = False
    deployed.hide_render = False

    folded = new_collection("POSE — Folded panel", "Alternate folded pose; pad rotates forward and the strut nests underneath.", assembly)
    folded["State"] = "Folded concept pose"
    folded_root = add_pad_pose(folded, "Folded", -math.pi / 2.0)
    add_folded_strut(folded, folded_root)
    folded.hide_viewport = True
    folded.hide_render = True

    presentation = new_collection("Presentation rig", "Studio floor, saved cameras, and lighting.")
    bpy.ops.mesh.primitive_plane_add(size=100, location=(0.0, 0.0, -0.004))
    floor = bpy.context.object
    floor.name = "AIREF_Studio_Floor"
    floor.data.materials.append(mat("floor"))
    link_to(floor, presentation)

    overview_target = Vector((-0.42, 0.0, 0.76))
    cameras = [
        add_camera("AIREF_Camera_Overview", presentation, overview_target,
                   (-1.55, -2.45, 0.92), lens=48),
        add_camera("AIREF_Camera_PartA_Clamp_Detail", presentation,
                   Vector((HANDLE.x - 0.01, -0.19, HANDLE.z - 0.005)),
                   (-0.42, -0.92, 0.30), lens=78),
        add_camera("AIREF_Camera_PartB_Strut_Detail", presentation,
                   Vector((-0.525, -0.02, 0.875)), (0.65, -1.05, 0.36), lens=78),
        add_camera("AIREF_Camera_Folded_Overview", presentation,
                   Vector((-0.38, 0.0, 0.93)), (-1.50, -2.35, 0.94), lens=48),
    ]
    scene.camera = cameras[0]
    add_light("AIREF_Key_Light", presentation, overview_target,
              (-0.9, -1.4, 1.55), 150, 1.55, (1.0, 0.88, 0.75))
    add_light("AIREF_Fill_Light", presentation, overview_target,
              (0.7, 1.0, 0.8), 90, 1.8, (0.76, 0.86, 1.0))
    add_light("AIREF_Rim_Light", presentation, overview_target,
              (-0.2, 0.5, 1.8), 125, 1.1, (0.86, 0.93, 1.0))
    add_light("AIREF_Detail_Light", presentation, Vector((-0.525, -0.02, 0.875)),
              (0.7, -0.75, 0.9), 75, 0.9, (1.0, 0.91, 0.80))

    scene.frame_set(1)
    scene.render.filepath = "//../exports/renders/01_deployed_overview.png"
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"Saved new AI-render-reference model: {BLEND_OUT}")
    print("Built from the original cart reference; the earlier support model was not used.")


if __name__ == "__main__":
    build()
