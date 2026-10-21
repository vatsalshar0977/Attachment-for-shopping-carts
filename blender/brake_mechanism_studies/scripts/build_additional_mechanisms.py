#!/usr/bin/env python3
"""Build four additional, separate schematic cart-brake Blender studies.

Each output opens the supplied cart reference, adds one distinct brake concept,
and saves to this studies folder. The original cart and the existing M1–M5
brake-alternatives project are read-only inputs and are never saved over.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[3]
CART_SOURCE = REPO / "blender/source/hcd mockup.blend"
STUDY_ROOT = REPO / "blender/brake_mechanism_studies"
SOURCE_DIR = STUDY_ROOT / "source"
RENDER_DIR = STUDY_ROOT / "exports/renders"
sys.path.insert(0, str(REPO / "blender/scripts"))
sys.path.insert(0, str(REPO / "blender/brake_mechanisms/scripts"))
import build_attachment as geom  # noqa: E402
import build_brake_mechanisms as brk  # noqa: E402

HANDLE = Vector((-0.4944, 0.0, 1.0917))
WHEEL_X = -0.398
WHEEL_BASE_Z = 0.036
WHEEL_CENTRE_Z = 0.076
WHEEL_R = 0.038
WHEEL_YS = {"Near": -0.246, "Far": 0.246}

MATERIALS: dict[str, bpy.types.Material] = {}


def mat(name: str) -> bpy.types.Material:
    return MATERIALS[name]


def add_collection(name: str, description: str) -> bpy.types.Collection:
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    col["Description"] = description
    col["Status"] = "Concept schematic — not an engineered brake design"
    col["Cost"] = "Not supplied"
    return col


def add_common_materials() -> None:
    MATERIALS.clear()
    MATERIALS.update({
        "frame": geom.material("STUDY_Frame_Metal", "#71808A", 0.48, 0.42),
        "dark": geom.material("STUDY_Dark_Hardware", "#26323B", 0.55, 0.18),
        "orange": geom.material("STUDY_Linkage_Orange", "#E29337", 0.36, 0.26),
        "cyan": geom.material("STUDY_Control_Cyan", "#26A7B3", 0.38, 0.18),
        "blue": geom.material("STUDY_Input_Blue", "#347DBB", 0.42, 0.08),
        "red": geom.material("STUDY_Lock_Red", "#D84D48", 0.43, 0.08),
        "silver": geom.material("STUDY_Spring_Silver", "#B8C3C8", 0.3, 0.65),
        "rubber": geom.material("STUDY_Drum_Rubber", "#39454E", 0.75, 0.0),
        "cart": geom.material("STUDY_Render_Cart", "#5F6A74", 0.62, 0.22),
        "floor": geom.material("STUDY_Render_Floor", "#343D47", 0.88, 0.0),
    })


def cylinder_y(name: str, radius: float, depth: float, position, material, col):
    return geom.add_axis_y_cylinder(
        name, radius, depth, tuple(position), material, col,
        bevel=min(depth * 0.12, 0.0015),
    )


def rod(name: str, start, end, radius: float, material, col):
    return brk.rod(name, start, end, radius, material, col)


def pivot(name: str, position, radius: float, depth: float, material, col):
    return brk.pivot(name, position, radius, depth, material, col)


def cable(name: str, points, radius: float, material, col):
    return brk.cable(name, points, radius, material, col)


def spring(name: str, start, end, radius: float, turns: int, wire: float, material, col):
    return brk.helix(name, start, end, radius, turns, wire, material, col)


def box(name: str, dimensions, position, material, col, bevel=0.0):
    return geom.add_box(
        name, tuple(dimensions), tuple(position), material, col, bevel=bevel,
    )


def add_shoes(col: bpy.types.Collection):
    for side, y in WHEEL_YS.items():
        shoe = box(
            f"STUDY_Shared_Applied_Shoe_{side}", (0.024, 0.026, 0.016),
            (WHEEL_X, y, WHEEL_BASE_Z + 0.034), mat("red"), col, bevel=0.003,
        )
        shoe["State"] = "Shown in applied-brake position"
        cylinder_y(
            f"STUDY_Shared_Shoe_Hinge_{side}", 0.008, 0.018,
            (WHEEL_X + 0.010, y, WHEEL_BASE_Z + 0.016), mat("dark"), col,
        )


def add_handle_input(col, name: str, side_y=-0.18):
    pivot = Vector((HANDLE.x, side_y, HANDLE.z - 0.02))
    lever_end = pivot + Vector((0.048, 0.0, 0.050))
    cylinder_y(name + "_Pivot", 0.010, 0.025, pivot, mat("dark"), col)
    rod(name + "_Lever", pivot, lever_end, 0.0055, mat("blue"), col)
    box(name + "_Grip", (0.050, 0.045, 0.020),
        (HANDLE.x + 0.018, side_y, HANDLE.z - 0.070), mat("blue"), col, bevel=0.004)
    return lever_end


def add_ratchet_disc(name: str, centre_x: float, centre_z: float, y: float,
                     depth: float, teeth: int, root_radius: float,
                     tip_radius: float, material, col):
    """Extrude a simple saw-tooth ratchet profile along the caster axle."""
    profile = []
    step = math.tau / teeth
    for i in range(teeth):
        a = i * step
        for fraction, radius in ((0.0, root_radius), (0.38, root_radius),
                                 (0.63, tip_radius), (0.78, root_radius)):
            angle = a + fraction * step
            profile.append((centre_x + radius * math.cos(angle),
                            centre_z + radius * math.sin(angle)))
    count = len(profile)
    verts = [(x, y - depth / 2.0, z) for x, z in profile]
    verts.extend((x, y + depth / 2.0, z) for x, z in profile)
    faces = [tuple(range(count)), tuple(range(count, 2 * count))]
    for i in range(count):
        nxt = (i + 1) % count
        faces.append((i, nxt, count + nxt, count + i))
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    mesh.materials.append(material)
    return obj


def add_band_arc(name: str, centre_x: float, centre_z: float, y: float,
                 radius: float, start_deg: float, end_deg: float,
                 wire_radius: float, material, col):
    points = []
    steps = 28
    for i in range(steps + 1):
        t = i / steps
        angle = math.radians(start_deg + (end_deg - start_deg) * t)
        points.append((centre_x + radius * math.cos(angle), y,
                       centre_z + radius * math.sin(angle)))
    return cable(name, points, wire_radius, material, col)


def add_area_light(name, target: Vector, offset, energy: float, size: float, color):
    data = bpy.data.lights.new(name + "_Data", "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = target + Vector(offset)
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def add_camera(target: Vector, style: str):
    data = bpy.data.cameras.new("STUDY_Presentation_Camera_Data")
    camera = bpy.data.objects.new("STUDY_Presentation_Camera", data)
    bpy.context.scene.collection.objects.link(camera)
    if style == "side":
        data.type = "ORTHO"
        data.ortho_scale = 1.70
        camera.location = target + Vector((0.03, -2.8, 0.42))
    elif style == "pedal":
        data.type = "PERSP"
        data.lens = 72
        camera.location = target + Vector((-0.22, -1.25, 0.30))
    elif style == "ratchet":
        data.type = "PERSP"
        data.lens = 88
        camera.location = target + Vector((-0.36, -0.92, 0.24))
    else:  # wheel / band detail
        data.type = "PERSP"
        data.lens = 84
        camera.location = target + Vector((-0.30, -1.05, 0.28))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = camera
    return camera


def setup_presentation(scene, slug: str, target: Vector, style: str):
    presentation = bpy.data.collections.new("STUDY Presentation Rig")
    scene.collection.children.link(presentation)
    bpy.ops.mesh.primitive_plane_add(size=100, location=(0.0, 0.0, -0.004))
    floor = bpy.context.object
    floor.name = "STUDY_Render_Floor"
    floor.data.materials.append(mat("floor"))
    for current in list(floor.users_collection):
        current.objects.unlink(floor)
    presentation.objects.link(floor)
    add_camera(target, style)
    add_area_light("STUDY_Key_Light", target, (-0.85, -1.0, 1.35), 90, 1.2, (1.0, 0.88, 0.76))
    add_area_light("STUDY_Fill_Light", target, (0.65, 0.75, 0.7), 55, 1.45, (0.77, 0.86, 1.0))
    add_area_light("STUDY_Rim_Light", target, (0.7, -0.1, 1.5), 100, 0.9, (0.82, 0.91, 1.0))
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes.clear()
    bg = world.node_tree.nodes.new("ShaderNodeBackground")
    out = world.node_tree.nodes.new("ShaderNodeOutputWorld")
    bg.inputs["Color"].default_value = (0.015, 0.020, 0.026, 1.0)
    bg.inputs["Strength"].default_value = 0.55
    world.node_tree.links.new(bg.outputs["Background"], out.inputs["Surface"])
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
    scene.render.filepath = str(RENDER_DIR / f"{slug}.png")


def build_m6():
    slug = "M6_foot_treadle_cable"
    col = add_collection(
        "STUDY M6 — Foot treadle with twin cables",
        "Foot-operated transverse pedal pulls two cables to apply the rear shoes.",
    )
    col["Operating concept"] = "Step on the rear treadle to apply both brakes; release returns the pedal."
    col["Notes"] = "Foot clearance, pedal guarding, cable adjustment, and release behaviour require evaluation."
    shared = add_collection("STUDY M6 — Applied brake shoes", "Red shoes shown against both rear wheels.")
    add_shoes(shared)
    # Transverse shaft, pedal arm, and broad non-slip foot plate.
    shaft_z = WHEEL_BASE_Z + 0.108
    shaft_x = WHEEL_X - 0.045
    rod("STUDY_M6_Treadle_Shaft", (shaft_x, -0.285, shaft_z),
        (shaft_x, 0.285, shaft_z), 0.007, mat("orange"), col)
    rod("STUDY_M6_Pedal_Arm", (shaft_x, 0.0, shaft_z),
        (shaft_x - 0.095, 0.0, shaft_z - 0.050), 0.008, mat("orange"), col)
    plate = box("STUDY_M6_Foot_Plate", (0.105, 0.390, 0.018),
                (shaft_x - 0.105, 0.0, shaft_z - 0.060), mat("blue"), col, bevel=0.008)
    plate["Input"] = "Press down with a foot to apply both rear brakes"
    box("STUDY_M6_Non_Slip_Pad", (0.078, 0.330, 0.006),
        (shaft_x - 0.105, 0.0, shaft_z - 0.048), mat("dark"), col, bevel=0.003)
    for side, y in WHEEL_YS.items():
        # A shaft lever tensions the near and far cable independently.
        rod(f"STUDY_M6_Cable_Arm_{side}",
            (shaft_x, y, shaft_z), (shaft_x + 0.018, y, shaft_z + 0.045),
            0.0055, mat("orange"), col)
        cable(f"STUDY_M6_Apply_Cable_{side}", [
            (shaft_x + 0.018, y, shaft_z + 0.045),
            (WHEEL_X - 0.015, y, 0.205),
            (WHEEL_X - 0.008, y, WHEEL_BASE_Z + 0.055),
        ], 0.0035, mat("cyan"), col)
        spring(f"STUDY_M6_Return_Spring_{side}",
               (shaft_x, y, shaft_z + 0.008), (shaft_x, y, shaft_z + 0.052),
               0.006, 4, 0.0018, mat("silver"), col)
    target, style = Vector((shaft_x - 0.015, -0.19, 0.135)), "pedal"
    return slug, col, target, style


def build_m7():
    slug = "M7_ratchet_pawl_lock"
    col = add_collection(
        "STUDY M7 — Ratchet ring and spring pawl",
        "A spring-engaged pawl meshes with a toothed ring at each rear wheel.",
    )
    col["Operating concept"] = "Spring-loaded pawls engage wheel ratchets; a handle control cable lifts the pawls to release."
    col["Notes"] = "A pawl lock is discrete rather than a smooth friction brake; tooth engagement, guarding, and bidirectional holding need evaluation."
    release = add_handle_input(col, "STUDY_M7_Handle_Release")
    for side, y in WHEEL_YS.items():
        outboard = -0.292 if side == "Near" else 0.292
        add_ratchet_disc(
            f"STUDY_M7_Ratchet_Ring_{side}", WHEEL_X, WHEEL_CENTRE_Z,
            outboard, 0.010, 14, 0.027, 0.039, mat("orange"), col,
        )
        pivot_pos = Vector((WHEEL_X + 0.034, outboard, WHEEL_CENTRE_Z + 0.052))
        tip = Vector((WHEEL_X + 0.028, outboard, WHEEL_CENTRE_Z + 0.030))
        pivot(f"STUDY_M7_Pawl_Pivot_{side}", pivot_pos, 0.008, 0.020, mat("dark"), col)
        pawl = rod(f"STUDY_M7_Engaged_Pawl_{side}", pivot_pos, tip,
                   0.0065, mat("red"), col)
        pawl["State"] = "Pawl shown engaged with ratchet teeth"
        spring(f"STUDY_M7_Pawl_Spring_{side}",
               pivot_pos + Vector((0.004, 0.0, 0.006)),
               pivot_pos + Vector((-0.018, 0.0, 0.022)),
               0.004, 3, 0.0014, mat("silver"), col)
        # Cable pulls the pawl's outer arm upward; a small cross-link joins sides.
        cable(f"STUDY_M7_Release_Cable_{side}", [
            release,
            (HANDLE.x + 0.030, y, 0.80),
            (WHEEL_X - 0.020, y, 0.32),
            pivot_pos + Vector((0.0, 0.0, 0.018)),
        ], 0.003, mat("cyan"), col)
    target, style = Vector((WHEEL_X, -0.275, WHEEL_CENTRE_Z + 0.014)), "ratchet"
    return slug, col, target, style


def build_m8():
    slug = "M8_hydraulic_dual_caliper"
    col = add_collection(
        "STUDY M8 — Hydraulic master cylinder and twin calipers",
        "A hand lever drives a master cylinder and fluid lines to two rear wheel calipers.",
    )
    col["Operating concept"] = "A handle lever pressurizes a master cylinder; two calipers clamp rear-wheel rotors."
    col["Notes"] = "Sealing, bleeding, hose routing, maintenance, and suitable caster/rotor packaging need evaluation."
    release_y = -0.185
    lever_pivot = Vector((HANDLE.x + 0.005, release_y, HANDLE.z - 0.018))
    lever_tip = Vector((HANDLE.x + 0.060, release_y, HANDLE.z + 0.052))
    pivot("STUDY_M8_Lever_Pivot", lever_pivot, 0.010, 0.024, mat("dark"), col)
    rod("STUDY_M8_Hand_Lever", lever_pivot, lever_tip, 0.006, mat("blue"), col)
    cylinder_y("STUDY_M8_Master_Cylinder", 0.010, 0.075,
               (HANDLE.x + 0.015, release_y, HANDLE.z - 0.060), mat("frame"), col)
    rod("STUDY_M8_Push_Rod", lever_pivot + Vector((0.008, 0.0, -0.012)),
        (HANDLE.x - 0.006, release_y, HANDLE.z - 0.060), 0.0035, mat("orange"), col)
    near_y = WHEEL_YS["Near"]
    near_caliper_point = Vector((WHEEL_X + 0.022, near_y - 0.045, WHEEL_CENTRE_Z + 0.020))
    cable("STUDY_M8_Hydraulic_Line_Near", [
        (HANDLE.x + 0.015, release_y - 0.040, HANDLE.z - 0.080),
        (HANDLE.x + 0.045, near_y, 0.84),
        (WHEEL_X + 0.035, near_y, 0.42),
        near_caliper_point,
    ], 0.004, mat("cyan"), col)
    cable("STUDY_M8_Hydraulic_Line_Far", [
        (WHEEL_X + 0.035, near_y, 0.42),
        (WHEEL_X + 0.035, 0.0, 0.28),
        (WHEEL_X + 0.022, WHEEL_YS["Far"] + 0.045, WHEEL_CENTRE_Z + 0.020),
    ], 0.0035, mat("cyan"), col)
    for side, y in WHEEL_YS.items():
        outboard = y + (0.040 if side == "Near" else -0.040)
        rotor = cylinder_y(
            f"STUDY_M8_Rotor_{side}", 0.034, 0.008,
            (WHEEL_X, outboard, WHEEL_CENTRE_Z), mat("silver"), col,
        )
        rotor["Part"] = "Schematic rotor disc"
        cylinder_y(f"STUDY_M8_Rotor_Hub_{side}", 0.012, 0.012,
                   (WHEEL_X, outboard + (0.006 if side == "Near" else -0.006),
                    WHEEL_CENTRE_Z), mat("dark"), col)
        caliper_y = outboard + (0.008 if side == "Near" else -0.008)
        box(f"STUDY_M8_Caliper_Body_{side}", (0.026, 0.027, 0.038),
            (WHEEL_X + 0.024, caliper_y, WHEEL_CENTRE_Z + 0.020), mat("frame"), col, bevel=0.004)
        box(f"STUDY_M8_Caliper_Pad_{side}", (0.020, 0.010, 0.022),
            (WHEEL_X + 0.012, caliper_y, WHEEL_CENTRE_Z + 0.014), mat("red"), col, bevel=0.003)
    target, style = Vector((-0.435, -0.205, 0.565)), "side"
    return slug, col, target, style


def build_m9():
    slug = "M9_external_band_brake"
    col = add_collection(
        "STUDY M9 — External band brake on rear drums",
        "Flexible friction bands wrap dedicated small drums at both rear casters.",
    )
    col["Operating concept"] = "A handle lever pulls an equalized cable to tighten bands around both rear drums."
    col["Notes"] = "Band clearance, contamination, wear adjustment, heat, and caster packaging need evaluation."
    release = add_handle_input(col, "STUDY_M9_Handle_Lever")
    for side, y in WHEEL_YS.items():
        outboard = y + (-0.042 if side == "Near" else 0.042)
        cylinder_y(f"STUDY_M9_Drum_{side}", 0.033, 0.018,
                   (WHEEL_X, outboard, WHEEL_CENTRE_Z), mat("dark"), col)
        # An almost-wraparound band leaves an upper-right gap for the pull lever.
        band_y = outboard + (-0.012 if side == "Near" else 0.012)
        add_band_arc(
            f"STUDY_M9_Band_Lining_{side}", WHEEL_X, WHEEL_CENTRE_Z,
            band_y, 0.038, 45.0, 315.0, 0.005, mat("red"), col,
        )
        end_a = Vector((WHEEL_X + 0.027, band_y, WHEEL_CENTRE_Z + 0.027))
        end_b = Vector((WHEEL_X + 0.027, band_y, WHEEL_CENTRE_Z - 0.027))
        lever_pivot = Vector((WHEEL_X + 0.050, band_y, WHEEL_CENTRE_Z))
        pivot(f"STUDY_M9_Band_Lever_Pivot_{side}", lever_pivot, 0.0075, 0.016,
              mat("dark"), col)
        rod(f"STUDY_M9_Band_Lever_{side}", lever_pivot, end_a,
            0.0055, mat("orange"), col)
        rod(f"STUDY_M9_Band_Anchor_{side}", end_b,
            Vector((WHEEL_X + 0.005, band_y, WHEEL_CENTRE_Z - 0.033)),
            0.0045, mat("frame"), col)
        cable(f"STUDY_M9_Band_Pull_Cable_{side}", [
            release,
            (HANDLE.x + 0.035, y, 0.82),
            (WHEEL_X + 0.040, y, 0.34),
            lever_pivot + Vector((0.0, 0.0, 0.012)),
        ], 0.003, mat("cyan"), col)
    target, style = Vector((WHEEL_X, -0.285, WHEEL_CENTRE_Z)), "band"
    return slug, col, target, style


BUILDERS = (build_m6, build_m7, build_m8, build_m9)


def build_one(builder):
    slug = None
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    if not CART_SOURCE.exists():
        raise FileNotFoundError(CART_SOURCE)
    bpy.ops.wm.open_mainfile(filepath=str(CART_SOURCE))
    scene = bpy.context.scene
    geom.clear_previous_build()
    add_common_materials()
    cart = bpy.data.objects.get("Shopping Cart")
    if cart is None:
        raise RuntimeError("Shopping Cart mesh not found in the supplied reference file")

    # Keep the reference geometry, but use a subdued presentation material in
    # each new study file. The original source blend is never saved over.
    cart.data.materials.clear()
    cart.data.materials.append(mat("cart"))
    for obj in list(bpy.data.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)

    slug, study, target, style = builder()
    scene["Brake Study"] = slug
    scene["Engineering status"] = "Schematic only; not engineered, load-rated, or safety validated"
    setup_presentation(scene, slug, target, style)
    scene.frame_set(1)
    scene.render.filepath = f"//../exports/renders/{slug}.png"
    dest = SOURCE_DIR / f"{slug}.blend"
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(dest))
    print(f"Saved {slug}: {dest}")


def main():
    for builder in BUILDERS:
        build_one(builder)
    print(f"\nFour additional schematic studies saved under {SOURCE_DIR}")
    print("The source shopping-cart and M1–M5 brake files were not modified.")


if __name__ == "__main__":
    main()
