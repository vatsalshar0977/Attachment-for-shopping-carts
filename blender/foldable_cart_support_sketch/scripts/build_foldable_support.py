#!/usr/bin/env python3
"""Build a separate cart-mounted folding leaning-support study from the sketch.

The model uses the supplied shopping-cart Blender file as visual mounting
context. The sketch has no dimensions, so proportions are approximate; this is
not a manufacturing or fit-validated design. The padded panel is a leaning
support, not a seat.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[3]
CART_SOURCE = REPO / "blender/source/hcd mockup.blend"
PROJECT = REPO / "blender/foldable_cart_support_sketch"
BLEND_OUT = PROJECT / "source/foldable_cart_leaning_support.blend"
RENDERS = PROJECT / "exports/renders"
sys.path.insert(0, str(REPO / "blender/scripts"))
sys.path.insert(0, str(REPO / "blender/brake_mechanisms/scripts"))
import build_attachment as geom  # noqa: E402
import build_brake_mechanisms as brk  # noqa: E402

HANDLE = Vector((-0.4944, 0.0, 1.0917))
HINGE = Vector((-0.548, 0.0, 0.944))
PANEL_WIDTH = 0.460
PANEL_HEIGHT = 0.340
PANEL_THICKNESS = 0.060
DEPLOYED_TILT = math.radians(10.0)

MATS: dict[str, bpy.types.Material] = {}


def material(key: str):
    return MATS[key]


def move_to_collection(obj, collection):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    collection.objects.link(obj)


def new_collection(name: str, description: str, parent=None):
    collection = bpy.data.collections.new(name)
    (parent.children if parent else bpy.context.scene.collection.children).link(collection)
    collection["Description"] = description
    return collection


def add_materials():
    MATS.clear()
    MATS.update({
        "mount": geom.material("FOLD_Mount_Aluminium", "#87939B", 0.38, 0.58),
        "shell": geom.material("FOLD_Panel_Shell", "#47535C", 0.56, 0.18),
        "cushion": geom.material("FOLD_Leaning_Pad", "#88735D", 0.78, 0.0),
        "rib": geom.material("FOLD_Pad_Ribs", "#A18A70", 0.74, 0.0),
        "dark": geom.material("FOLD_Dark_Hardware", "#27323A", 0.48, 0.2),
        "lock": geom.material("FOLD_Lock_Accent", "#367FB6", 0.4, 0.08),
        "tube": geom.material("FOLD_Adjustable_Tube", "#C1C9CC", 0.34, 0.65),
        "collar": geom.material("FOLD_Adjustment_Collar", "#D28B3A", 0.42, 0.25),
        "cart": geom.material("FOLD_Render_Cart", "#65717A", 0.58, 0.28),
        "floor": geom.material("FOLD_Render_Floor", "#39434C", 0.9, 0.0),
    })


def add_box(name, dimensions, location, mat, collection, bevel=0.0, parent=None):
    return geom.add_box(name, tuple(dimensions), tuple(location), mat, collection,
                        bevel=bevel, parent=parent)


def add_rod(name, start, end, radius, mat, collection):
    return brk.rod(name, start, end, radius, mat, collection)


def add_rod_local(name, start, end, radius, mat, collection, parent):
    start, end = Vector(start), Vector(end)
    direction = end - start
    obj = brk.rod(name, start, end, radius, mat, collection)
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.location = (start + end) * 0.5
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.normalized().to_track_quat("Z", "Y")
    return obj


def add_cylinder_y(name, radius, depth, location, mat, collection, bevel=0.001, parent=None):
    return geom.add_axis_y_cylinder(name, radius, depth, tuple(location), mat, collection,
                                    bevel=bevel, parent=parent)


def add_torus_y(name, location, major_radius, minor_radius, mat, collection):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=48, minor_segments=12,
        major_radius=major_radius, minor_radius=minor_radius,
        location=tuple(location), rotation=(math.pi / 2.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    move_to_collection(obj, collection)
    return obj


def add_sphere(name, radius, location, mat, collection, parent=None):
    return geom.add_sphere(name, radius, tuple(location), mat, collection, parent=parent)


def rotate_y(vector: Vector, angle: float) -> Vector:
    c, s = math.cos(angle), math.sin(angle)
    return Vector((c * vector.x + s * vector.z, vector.y,
                   -s * vector.x + c * vector.z))


def add_area_light(name, target, offset, energy, size, color, collection):
    data = bpy.data.lights.new(name + "_Data", "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = target + Vector(offset)
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def add_camera(name, collection, target, offset, lens=55, ortho_scale=None):
    data = bpy.data.cameras.new(name + "_Data")
    if ortho_scale is None:
        data.type = "PERSP"
        data.lens = lens
    else:
        data.type = "ORTHO"
        data.ortho_scale = ortho_scale
    camera = bpy.data.objects.new(name, data)
    collection.objects.link(camera)
    camera.location = target + Vector(offset)
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    return camera


def add_mount_hardware(collection):
    """Tube collars, standoff arms, hinge rail, and side pivots (Part B mount)."""
    handle_radius = 0.01165
    collar_y = (-0.190, 0.190)
    for i, y in enumerate(collar_y, 1):
        add_torus_y(f"FOLD_Handle_Split_Collar_{i}",
                    (HANDLE.x, y, HANDLE.z), handle_radius + 0.0025, 0.003,
                    material("mount"), collection)
        # A pair of low-profile ears and a fastener suggest a two-piece clamp.
        add_box(f"FOLD_Collar_Lug_{i}", (0.028, 0.035, 0.030),
                (HANDLE.x + 0.014, y, HANDLE.z - 0.015),
                material("dark"), collection, bevel=0.004)
        add_cylinder_y(f"FOLD_Collar_Bolt_{i}", 0.006, 0.042,
                       (HANDLE.x + 0.018, y, HANDLE.z - 0.015),
                       material("collar"), collection, bevel=0.0008)
        # Standoff bracket connects the handle clamp to the panel hinge axis.
        add_rod(f"FOLD_Mount_Standoff_{i}",
                (HANDLE.x + 0.018, y, HANDLE.z - 0.018),
                (HINGE.x + 0.010, y, HINGE.z),
                0.010, material("mount"), collection)
        add_cylinder_y(f"FOLD_Standoff_Lower_Pivot_{i}", 0.012, 0.032,
                       (HINGE.x + 0.010, y, HINGE.z),
                       material("dark"), collection, bevel=0.001)

    # Continuous cross-hinge/shaft and end caps.
    add_rod("FOLD_Panel_Hinge_Shaft", (HINGE.x, -0.245, HINGE.z),
            (HINGE.x, 0.245, HINGE.z), 0.009, material("mount"), collection)
    for i, y in enumerate((-0.232, 0.232), 1):
        add_cylinder_y(f"FOLD_Hinge_End_Cap_{i}", 0.018, 0.022,
                       (HINGE.x, y, HINGE.z), material("dark"), collection,
                       bevel=0.001)
        add_cylinder_y(f"FOLD_Hinge_Pin_{i}", 0.0065, 0.030,
                       (HINGE.x, y, HINGE.z), material("collar"), collection,
                       bevel=0.0008)
    collection["Attachment"] = "Split collars around cart handle tube; fit is approximate"


def add_panel_pose(pose_collection, pose_name, angle, include_supports):
    """Create Part A as a hinged rounded shell with a ribbed leaning pad."""
    part_a = new_collection(f"Part A — Leaning panel ({pose_name})",
                            "Rounded shell and cushioned, ribbed leaning face.", pose_collection)
    root = bpy.data.objects.new(f"FOLD_{pose_name}_Panel_Pivot_Empty", None)
    part_a.objects.link(root)
    root.empty_display_type = "CIRCLE"
    root.empty_display_size = 0.035
    root.location = HINGE
    root.rotation_euler = (0.0, angle, 0.0)
    root["Pivot axis"] = "Horizontal Y-axis hinge"
    root["Pose"] = pose_name

    zc = -PANEL_HEIGHT / 2.0
    add_box(f"FOLD_{pose_name}_Panel_Shell",
            (PANEL_THICKNESS, PANEL_WIDTH, PANEL_HEIGHT),
            (0.0, 0.0, zc), material("shell"), part_a,
            bevel=0.025, parent=root)
    add_box(f"FOLD_{pose_name}_Cushion_Base",
            (0.024, PANEL_WIDTH - 0.050, PANEL_HEIGHT - 0.050),
            (-0.040, 0.0, zc), material("cushion"), part_a,
            bevel=0.020, parent=root)

    # Five soft longitudinal ribs echo the grooved surface drawn in the sketch.
    for idx, y in enumerate((-0.155, -0.078, 0.0, 0.078, 0.155), 1):
        add_box(f"FOLD_{pose_name}_Cushion_Rib_{idx}",
                (0.012, 0.026, PANEL_HEIGHT - 0.075),
                (-0.058, y, zc), material("rib"), part_a,
                bevel=0.010, parent=root)
    # Rounded side rails and end trims define the soft-edged panel perimeter.
    for side, y in (("L", -0.212), ("R", 0.212)):
        add_rod_local(f"FOLD_{pose_name}_Panel_Side_Rail_{side}",
                      (-0.015, y, -0.025), (-0.015, y, -PANEL_HEIGHT + 0.025),
                      0.010, material("dark"), part_a, root)
        add_cylinder_y(f"FOLD_{pose_name}_Panel_Hinge_Cheek_{side}",
                       0.019, 0.030, (0.0, y, 0.0), material("mount"),
                       part_a, bevel=0.001, parent=root)
        add_cylinder_y(f"FOLD_{pose_name}_Panel_Hinge_Bolt_{side}",
                       0.007, 0.034, (0.0, y, 0.0), material("collar"),
                       part_a, bevel=0.0008, parent=root)
    add_box(f"FOLD_{pose_name}_Top_Trim", (0.066, PANEL_WIDTH - 0.015, 0.022),
            (-0.004, 0.0, -0.012), material("dark"), part_a,
            bevel=0.006, parent=root)
    add_box(f"FOLD_{pose_name}_Bottom_Trim", (0.066, PANEL_WIDTH - 0.015, 0.022),
            (-0.004, 0.0, -PANEL_HEIGHT + 0.012), material("dark"), part_a,
            bevel=0.006, parent=root)
    part_a["Use"] = "Leaning support only; not a seat"
    part_a["Approximate visual envelope"] = "0.46 m wide × 0.34 m tall; inferred from sketch proportions"

    part_b = new_collection(f"Part B — Folding lock struts ({pose_name})",
                            "Paired telescoping struts with sleeve collars and quick-release pins.",
                            pose_collection)
    if include_supports:
        panel_local = Vector((0.0, 0.0, -0.265))
        for side, y in (("L", -0.190), ("R", 0.190)):
            local_joint = Vector((0.012, y, panel_local.z))
            lower_world = HINGE + rotate_y(local_joint, angle)
            upper_world = Vector((HINGE.x + 0.058, y, HINGE.z - 0.105))
            axis = upper_world - lower_world
            length = axis.length
            direction = axis.normalized()
            outer_start = lower_world + direction * 0.012
            sleeve_end = lower_world + direction * (length * 0.60)
            inner_start = lower_world + direction * (length * 0.53)
            inner_end = upper_world - direction * 0.012
            add_cylinder_y(f"FOLD_{pose_name}_Strut_Lower_Pivot_{side}",
                           0.014, 0.034, lower_world, material("dark"), part_b,
                           bevel=0.001)
            add_rod(f"FOLD_{pose_name}_Strut_Outer_Tube_{side}",
                    outer_start, sleeve_end, 0.013, material("tube"), part_b)
            add_rod(f"FOLD_{pose_name}_Strut_Inner_Tube_{side}",
                    inner_start, inner_end, 0.0085, material("mount"), part_b)
            collar_mid = lower_world + direction * (length * 0.57)
            collar_start = collar_mid - direction * 0.010
            collar_end = collar_mid + direction * 0.010
            add_rod(f"FOLD_{pose_name}_Strut_Adjustment_Collar_{side}",
                    collar_start, collar_end, 0.017, material("collar"), part_b)
            add_cylinder_y(f"FOLD_{pose_name}_Strut_Quick_Pin_{side}",
                           0.006, 0.040, collar_mid, material("lock"), part_b,
                           bevel=0.0008)
            add_cylinder_y(f"FOLD_{pose_name}_Strut_Upper_Pivot_{side}",
                           0.013, 0.030, upper_world, material("dark"), part_b,
                           bevel=0.001)
            # A row of shallow indexing bosses makes the telescopic adjustment legible.
            for hole in range(3):
                t = 0.18 + hole * 0.12
                pos = lower_world + direction * (length * t)
                add_sphere(f"FOLD_{pose_name}_Strut_Index_Mark_{side}_{hole+1}",
                           0.0035, pos + Vector((-0.009, 0.0, 0.0)),
                           material("dark"), part_b)
    else:
        # In the folded pose, the struts nest flat along the back of the panel.
        for side, y in (("L", -0.185), ("R", 0.185)):
            add_rod_local(f"FOLD_{pose_name}_Stowed_Strut_Outer_{side}",
                          (0.032, y, -0.045), (0.032, y, -0.185),
                          0.012, material("tube"), part_b, root)
            add_rod_local(f"FOLD_{pose_name}_Stowed_Strut_Inner_{side}",
                          (0.032, y, -0.170), (0.032, y, -0.315),
                          0.0085, material("mount"), part_b, root)
            add_cylinder_y(f"FOLD_{pose_name}_Stowed_Strut_Collar_{side}",
                           0.016, 0.026, (0.032, y, -0.177),
                           material("collar"), part_b, bevel=0.001, parent=root)
            add_cylinder_y(f"FOLD_{pose_name}_Stowed_Strut_Pin_{side}",
                           0.0055, 0.034, (0.032, y, -0.177),
                           material("lock"), part_b, bevel=0.0008, parent=root)
    part_b["Part"] = "Part B — adjustable support/locking arm"
    return root


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
    background = world.node_tree.nodes.new("ShaderNodeBackground")
    output = world.node_tree.nodes.new("ShaderNodeOutputWorld")
    background.inputs["Color"].default_value = (0.018, 0.023, 0.029, 1.0)
    background.inputs["Strength"].default_value = 0.52
    world.node_tree.links.new(background.outputs["Background"], output.inputs["Surface"])


def build():
    if not CART_SOURCE.exists():
        raise FileNotFoundError(CART_SOURCE)
    BLEND_OUT.parent.mkdir(parents=True, exist_ok=True)
    RENDERS.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(CART_SOURCE))
    scene = bpy.context.scene
    setup_scene(scene)
    geom.clear_previous_build()
    for obj in list(bpy.data.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    cart = bpy.data.objects.get("Shopping Cart")
    if cart is None:
        raise RuntimeError("The supplied Shopping Cart mesh was not found")

    add_materials()
    cart.data.materials.clear()
    cart.data.materials.append(material("cart"))
    scene["Product"] = "Foldable cart-mounted leaning support"
    scene["Model assumptions"] = "Sketch proportions; no dimensions supplied"
    scene["Use note"] = "Leaning support only — not a seat"
    scene["Validation"] = "Concept visualization only; fit and load not validated"

    mounts = new_collection("Mounting collars and hinge rail",
                            "Split tube clamps around the cart handle, standoffs, and transverse hinge.")
    add_mount_hardware(mounts)

    deployed = new_collection("POSE — Deployed leaning support",
                              "Default assembled pose: upright, slightly reclined support panel.")
    deployed["State"] = "Deployed"
    add_panel_pose(deployed, "Deployed", DEPLOYED_TILT, include_supports=True)
    deployed.hide_viewport = False
    deployed.hide_render = False

    folded = new_collection("POSE — Folded / stowed",
                            "Alternative pose: panel rotates forward toward the cart basket; struts nest behind it.")
    folded["State"] = "Stowed concept view"
    add_panel_pose(folded, "Folded", -math.pi / 2.0, include_supports=False)
    folded.hide_viewport = True
    folded.hide_render = True

    presentation = new_collection("Presentation rig", "Studio floor, three cameras, and soft area lighting.")
    bpy.ops.mesh.primitive_plane_add(size=100, location=(0.0, 0.0, -0.004))
    floor = bpy.context.object
    floor.name = "FOLD_Studio_Floor"
    floor.data.materials.append(material("floor"))
    move_to_collection(floor, presentation)

    overview_target = Vector((-0.42, 0.0, 0.76))
    overview = add_camera("FOLD_Camera_Deployed_Overview", presentation,
                          overview_target, (-1.38, -2.40, 0.92), lens=48)
    handle_target = Vector((HINGE.x - 0.01, -0.19, HINGE.z + 0.02))
    handle_camera = add_camera("FOLD_Camera_Handle_Mount_Detail", presentation,
                               handle_target, (-0.48, -0.92, 0.40), lens=72)
    folded_camera = add_camera("FOLD_Camera_Folded_Overview", presentation,
                               Vector((-0.38, 0.0, 0.90)), (-1.30, -2.25, 0.95), lens=48)
    scene.camera = overview

    for name, target, offset, energy, size, color in (
        ("FOLD_Key", overview_target, (-0.9, -1.4, 1.6), 150, 1.6, (1.0, 0.87, 0.72)),
        ("FOLD_Fill", overview_target, (0.7, 1.0, 0.9), 85, 1.8, (0.72, 0.84, 1.0)),
        ("FOLD_Rim", overview_target, (-0.2, 0.5, 1.8), 120, 1.1, (0.86, 0.93, 1.0)),
    ):
        add_area_light(name, target, offset, energy, size, color, presentation)
    # A soft extra key makes the hinge/collar detail readable in the close-up camera.
    add_area_light("FOLD_Handle_Detail_Key", handle_target,
                   (-0.6, -0.8, 0.9), 65, 0.8, (1.0, 0.91, 0.79), presentation)

    scene.frame_set(1)
    scene.render.filepath = "//../exports/renders/01_deployed_overview.png"
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"Saved new, separate cart-support model: {BLEND_OUT}")
    print("The source cart and all earlier brake/support projects were read-only.")


if __name__ == "__main__":
    build()
