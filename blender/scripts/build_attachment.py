#!/usr/bin/env python3
"""Build a fold-out, padded leaning support on the supplied cart mock-up.

The broad backrest rotates inward around the cart handle. Frame 1 is deployed;
frame 35 folds the support into the open basket. The paired telescoping stays
follow the panel so the two useful poses are visible in the timeline.

This is a visual/fit prototype only. It is not load-rated or safety-certified.

Run from the repository root:
    LD_LIBRARY_PATH=$HOME/tools/bpy-stubs python3 blender/scripts/build_attachment.py
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Matrix, Vector


# --------------------------------------------------------------------------- #
# Project parameters (model units are metres; the cart file is a 1:1 mock-up).
# --------------------------------------------------------------------------- #

BLEND_PATH = "blender/source/hcd mockup.blend"
CART_NAME = "Shopping Cart"

# Fit envelope: measured from the supplied normalized cart mock-up.
HANDLE_DIAMETER = 0.0233
REST_WIDTH = 0.460
REST_HEIGHT = 0.270
CUSHION_WIDTH = 0.430
CUSHION_HEIGHT = 0.238

DEPLOY_FRAME = 1
MID_FOLD_FRAME = 18
STOW_FRAME = 35
DEPLOYED_ANGLE = 0.0
STOWED_ANGLE = -math.pi / 2.0


# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def hex_to_linear(value: str) -> tuple[float, float, float, float]:
    value = value.lstrip("#")
    rgb = []
    for i in (0, 2, 4):
        channel = int(value[i:i + 2], 16) / 255.0
        rgb.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    return rgb[0], rgb[1], rgb[2], 1.0


def material(name: str, colour: str, roughness: float = 0.45,
             metallic: float = 0.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = hex_to_linear(colour)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_to_linear(colour)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def soft_tpe_material() -> bpy.types.Material:
    mat = material("HCD_Material_Soft_TPE", "#2D5FA5", 0.74)
    mat["Finish"] = "Textured, cushioned thermoplastic-elastomer concept"
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.location = (420, 80)
    bsdf.inputs["Specular IOR Level"].default_value = 0.22
    bsdf.inputs["Coat Weight"].default_value = 0.025
    bsdf.inputs["Coat Roughness"].default_value = 0.62

    tex = nodes.new("ShaderNodeTexCoord")
    tex.location = (-900, 40)
    wave = nodes.new("ShaderNodeTexWave")
    wave.location = (-650, 180)
    wave.wave_type = "BANDS"
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = 32.0
    wave.inputs["Distortion"].default_value = 0.03
    wave.inputs["Detail"].default_value = 1.0
    links.new(tex.outputs["Object"], wave.inputs["Vector"])

    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-650, -140)
    noise.inputs["Scale"].default_value = 180.0
    noise.inputs["Detail"].default_value = 2.0
    links.new(tex.outputs["Object"], noise.inputs["Vector"])

    ribs = nodes.new("ShaderNodeBump")
    ribs.location = (-120, 160)
    ribs.inputs["Strength"].default_value = 0.055
    ribs.inputs["Distance"].default_value = 0.00022
    links.new(wave.outputs["Fac"], ribs.inputs["Height"])

    grain = nodes.new("ShaderNodeBump")
    grain.location = (160, -40)
    grain.inputs["Strength"].default_value = 0.08
    grain.inputs["Distance"].default_value = 0.00012
    links.new(noise.outputs["Fac"], grain.inputs["Height"])
    links.new(ribs.outputs["Normal"], grain.inputs["Normal"])
    links.new(grain.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def ensure_collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    collection.objects.link(obj)


def clear_previous_build() -> None:
    """Remove only generated attachment/presentation objects; keep the cart."""
    for obj in list(bpy.data.objects):
        if obj.name.startswith("HCD_"):
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection_name in ("HCD - Attachment", "HCD - Foldable Lean Rest", "HCD - Presentation"):
        col = bpy.data.collections.get(collection_name)
        if col is not None:
            # Objects were removed above; deleting an empty obsolete collection is safe.
            bpy.data.collections.remove(col)
    for datablocks in (bpy.data.materials, bpy.data.meshes, bpy.data.curves,
                       bpy.data.cameras, bpy.data.lights, bpy.data.actions):
        for data in list(datablocks):
            if data.users == 0 and data.name.startswith("HCD_"):
                datablocks.remove(data)


def make_mesh_object(name: str, verts: list[tuple[float, float, float]],
                     faces: list[tuple[int, ...]], collection: bpy.types.Collection,
                     mat: bpy.types.Material | None = None) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    if mat is not None:
        mesh.materials.append(mat)
    return obj


def add_box(name: str, dimensions: tuple[float, float, float],
            location: tuple[float, float, float], mat: bpy.types.Material,
            collection: bpy.types.Collection, bevel: float = 0.0,
            parent: bpy.types.Object | None = None) -> bpy.types.Object:
    dx, dy, dz = dimensions
    hx, hy, hz = dx / 2.0, dy / 2.0, dz / 2.0
    verts = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
             (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    obj = make_mesh_object(name, verts, faces, collection, mat)
    if parent is None:
        obj.location = location
    else:
        obj.parent = parent
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.location = location
    if bevel > 0:
        modifier = obj.modifiers.new("Soft_Radius", "BEVEL")
        modifier.width = min(bevel, min(dimensions) * 0.48)
        modifier.segments = 6
        modifier.limit_method = "ANGLE"
        modifier.angle_limit = math.radians(30.0)
        modifier.use_clamp_overlap = True
        normal = obj.modifiers.new("Weighted_Corner_Normals", "WEIGHTED_NORMAL")
        normal.keep_sharp = True
        normal.weight = 40
    return obj


def add_oriented_beam(name: str, start: Vector, end: Vector,
                      width: float, depth: float, mat: bpy.types.Material,
                      collection: bpy.types.Collection,
                      bevel: float = 0.0) -> bpy.types.Object:
    direction = end - start
    obj = add_box(name, (width, depth, direction.length), tuple((start + end) * 0.5),
                  mat, collection, bevel=bevel)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.normalized().to_track_quat("Z", "Y")
    return obj


def cylinder_mesh(name: str, radius: float, depth: float, collection: bpy.types.Collection,
                  mat: bpy.types.Material, vertices: int = 48) -> bpy.types.Object:
    """Cylinder with its long axis along local Z, centred at the object origin."""
    verts = []
    half = depth / 2.0
    for z in (-half, half):
        for i in range(vertices):
            ang = math.tau * i / vertices
            verts.append((radius * math.cos(ang), radius * math.sin(ang), z))
    faces = []
    faces.append(tuple(reversed(range(vertices))))
    faces.append(tuple(range(vertices, 2 * vertices)))
    for i in range(vertices):
        nxt = (i + 1) % vertices
        faces.append((i, nxt, vertices + nxt, vertices + i))
    obj = make_mesh_object(name, verts, faces, collection, mat)
    for poly in obj.data.polygons:
        poly.use_smooth = poly.loop_total == 4
    return obj


def add_axis_y_cylinder(name: str, radius: float, depth: float,
                        location: tuple[float, float, float], mat: bpy.types.Material,
                        collection: bpy.types.Collection, bevel: float = 0.0,
                        parent: bpy.types.Object | None = None) -> bpy.types.Object:
    obj = cylinder_mesh(name, radius, depth, collection, mat)
    if parent is None:
        obj.location = location
    else:
        obj.parent = parent
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.location = location
    obj.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
    if bevel > 0:
        modifier = obj.modifiers.new("Edge_Radius", "BEVEL")
        modifier.width = min(bevel, depth * 0.2)
        modifier.segments = 3
        modifier.limit_method = "ANGLE"
        modifier.angle_limit = math.radians(30.0)
        obj.modifiers.new("Weighted_Normals", "WEIGHTED_NORMAL")
    return obj


def add_sphere(name: str, radius: float, location: tuple[float, float, float],
               mat: bpy.types.Material, collection: bpy.types.Collection,
               parent: bpy.types.Object | None = None) -> bpy.types.Object:
    # Latitude-longitude sphere with single pole vertices (closed and manifold).
    lat_steps, lon_steps = 16, 32
    verts = [(0.0, 0.0, radius)]
    for j in range(1, lat_steps):
        phi = math.pi * j / lat_steps
        ring_radius = radius * math.sin(phi)
        z = radius * math.cos(phi)
        for i in range(lon_steps):
            theta = math.tau * i / lon_steps
            verts.append((ring_radius * math.cos(theta), ring_radius * math.sin(theta), z))
    south = len(verts)
    verts.append((0.0, 0.0, -radius))
    faces = []
    first_ring = 1
    for i in range(lon_steps):
        faces.append((0, first_ring + i, first_ring + (i + 1) % lon_steps))
    for j in range(lat_steps - 2):
        ring_a = 1 + j * lon_steps
        ring_b = ring_a + lon_steps
        for i in range(lon_steps):
            nxt = (i + 1) % lon_steps
            faces.append((ring_a + i, ring_b + i, ring_b + nxt, ring_a + nxt))
    last_ring = 1 + (lat_steps - 2) * lon_steps
    for i in range(lon_steps):
        faces.append((last_ring + i, south, last_ring + (i + 1) % lon_steps))
    obj = make_mesh_object(name, verts, faces, collection, mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    if parent is None:
        obj.location = location
    else:
        obj.parent = parent
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.location = location
    return obj


def add_torus(name: str, major_radius: float, minor_radius: float,
              location: tuple[float, float, float], mat: bpy.types.Material,
              collection: bpy.types.Collection, axis_y: bool = True) -> bpy.types.Object:
    # Explicit torus mesh, axis along local Z before optional orientation.
    major_steps, minor_steps = 48, 12
    verts = []
    for i in range(major_steps):
        u = math.tau * i / major_steps
        for j in range(minor_steps):
            v = math.tau * j / minor_steps
            ring = major_radius + minor_radius * math.cos(v)
            verts.append((ring * math.cos(u), ring * math.sin(u), minor_radius * math.sin(v)))
    faces = []
    for i in range(major_steps):
        for j in range(minor_steps):
            a = i * minor_steps + j
            b = i * minor_steps + (j + 1) % minor_steps
            c = ((i + 1) % major_steps) * minor_steps + (j + 1) % minor_steps
            d = ((i + 1) % major_steps) * minor_steps + j
            faces.append((a, b, c, d))
    obj = make_mesh_object(name, verts, faces, collection, mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    obj.location = location
    if axis_y:
        obj.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
    return obj


def make_empty(name: str, collection: bpy.types.Collection, location: Vector) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = 0.10
    obj.location = location
    collection.objects.link(obj)
    return obj


def parent_local(obj: bpy.types.Object, parent: bpy.types.Object,
                 location: tuple[float, float, float]) -> None:
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.location = location


def clean_and_normalize_cart() -> bpy.types.Object:
    cart = bpy.data.objects.get(CART_NAME)
    if cart is None:
        raise RuntimeError(f"Could not find the supplied cart object {CART_NAME!r}")
    if cart.type != "MESH":
        raise RuntimeError(f"{CART_NAME!r} must be a mesh for handle measurement")

    # The project file's cart was normalized on the prior build; retain its current
    # dimensions and centre it at the origin for predictable animation/rendering.
    bpy.context.view_layer.update()
    coords = [cart.matrix_world @ v.co for v in cart.data.vertices]
    min_x, max_x = min(v.x for v in coords), max(v.x for v in coords)
    min_y, max_y = min(v.y for v in coords), max(v.y for v in coords)
    min_z = min(v.z for v in coords)
    cart.location.x -= (min_x + max_x) / 2.0
    cart.location.y -= (min_y + max_y) / 2.0
    cart.location.z -= min_z
    cart.name = CART_NAME
    cart.data.name = "Shopping_Cart_Reference_Mesh"
    cart["Design reference"] = "Supplied shopping-cart mock-up; not a structural simulation"
    return cart


def measure_handle(cart: bpy.types.Object) -> tuple[float, float, float, float, float]:
    bpy.context.view_layer.update()
    world_verts = [cart.matrix_world @ v.co for v in cart.data.vertices]
    zmax = max(v.z for v in world_verts)
    ymin, ymax = min(v.y for v in world_verts), max(v.y for v in world_verts)
    ymid = (ymin + ymax) / 2.0
    top = [v for v in world_verts if v.z > zmax - 0.05]
    band = [v for v in top if abs(v.y - ymid) < 0.10]
    if not band:
        raise RuntimeError("Could not identify the top cart-handle crossbar")
    hx = sorted(v.x for v in band)[len(band) // 2]
    hz = sorted(v.z for v in band)[len(band) // 2]
    return hx, ymid, hz, ymin, ymax


def set_render_defaults(scene: bpy.types.Scene) -> None:
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 820
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.film_transparent = False
    scene.render.filepath = "//../exports/renders/01_deployed_hero.png"
    scene.frame_start = DEPLOY_FRAME
    scene.frame_end = STOW_FRAME
    scene.timeline_markers.clear()
    scene.timeline_markers.new("DEPLOYED — lean", frame=DEPLOY_FRAME)
    scene.timeline_markers.new("MID-FOLD", frame=MID_FOLD_FRAME)
    scene.timeline_markers.new("STOWED — inside basket", frame=STOW_FRAME)
    scene.frame_set(DEPLOY_FRAME)


def add_presentation_camera(collection: bpy.types.Collection, target: Vector) -> None:
    camera_data = bpy.data.cameras.new("HCD_Presentation_Camera_Data")
    camera_data.lens = 55
    camera = bpy.data.objects.new("HCD_Presentation_Camera", camera_data)
    collection.objects.link(camera)
    direction = Vector((-1.4, -1.6, 0.8))
    direction.normalize()
    camera.location = target + direction * 2.15
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = camera

    for name, offset, power, size, colour in (
        ("HCD_Key_Light", Vector((-1.1, -1.5, 1.4)), 650, 1.2, (1.0, 0.85, 0.70)),
        ("HCD_Fill_Light", Vector((-0.5, 1.4, 0.5)), 420, 1.5, (0.70, 0.82, 1.0)),
        ("HCD_Rim_Light", Vector((1.6, 0.4, 1.2)), 800, 0.9, (0.65, 0.80, 1.0)),
    ):
        data = bpy.data.lights.new(name + "_Data", "AREA")
        data.energy = power
        data.shape = "DISK"
        data.size = size
        data.color = colour
        light = bpy.data.objects.new(name, data)
        collection.objects.link(light)
        light.location = target + offset
        light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()


def keyframe_strut(obj: bpy.types.Object, p0: Vector, p1: Vector,
                   frame: int, radius: float) -> None:
    direction = p1 - p0
    length = direction.length
    if length < 0.001:
        raise ValueError("Support stay collapsed; check the hinge/panel dimensions")
    obj.location = (p0 + p1) * 0.5
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.normalized().to_track_quat("Z", "Y")
    obj.scale = (radius * 2.0, radius * 2.0, length)
    obj.keyframe_insert(data_path="location", frame=frame)
    obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    obj.keyframe_insert(data_path="scale", frame=frame)


def make_animated_rod(name: str, radius: float, collection: bpy.types.Collection,
                      mat: bpy.types.Material) -> bpy.types.Object:
    # A unit-long cylinder is scaled along local Z at each support pose.
    obj = cylinder_mesh(name, 0.5, 1.0, collection, mat, vertices=32)
    obj.rotation_mode = "QUATERNION"
    for poly in obj.data.polygons:
        poly.use_smooth = poly.loop_total == 4
    obj["Nominal radius (mm)"] = radius * 1000.0
    return obj


def main() -> None:
    blend_path = os.path.join(repo_root(), BLEND_PATH)
    if not bpy.data.objects.get(CART_NAME):
        bpy.ops.wm.open_mainfile(filepath=blend_path)
    clear_previous_build()
    scene = bpy.context.scene
    cart = clean_and_normalize_cart()
    cart_collection = ensure_collection("Cart - Reference")
    move_to_collection(cart, cart_collection)
    cart.display_type = "TEXTURED"
    cart["Handle reference diameter (mm)"] = round(HANDLE_DIAMETER * 1000.0, 1)

    # Keep the supplied wire-cart visible in renders, but visually subordinate.
    cart_mat = material("HCD_Material_Cart_Reference", "#ABB3BC", 0.58, 0.45)
    cart.data.materials.clear()
    cart.data.materials.append(cart_mat)

    hx, ymid, hz, ymin, ymax = measure_handle(cart)
    print(f"  handle pivot measured at x={hx:+.4f}, y={ymid:+.4f}, z={hz:.4f} m; "
          f"cart sides y={ymin:+.3f}…{ymax:+.3f} m")

    assembly = ensure_collection("HCD - Foldable Lean Rest")
    presentation = ensure_collection("HCD - Presentation")
    metal = material("HCD_Material_Anodized_Aluminium", "#8996A3", 0.27, 0.82)
    dark = material("HCD_Material_Graphite", "#252D37", 0.38, 0.48)
    shell_mat = material("HCD_Material_Shell", "#52616F", 0.44, 0.24)
    latch_mat = material("HCD_Material_Safety_Accent", "#E6A542", 0.31, 0.18)
    tpe = soft_tpe_material()

    # The handle carries two short drop brackets; their lower hinge axis sits
    # over the basket rim so the folded panel clears the handle and stows inside.
    pivot_x = hx + 0.120
    pivot_z = hz - 0.100
    root_location = Vector((pivot_x, ymid, pivot_z))
    root = make_empty("HCD_Fold_Root", assembly, root_location)
    root.rotation_mode = "XYZ"
    root["Function"] = "Broad padded leaning support; folds inward into the basket"
    root["Deployed frame"] = DEPLOY_FRAME
    root["Stowed frame"] = STOW_FRAME
    root["Fit reference"] = "Measured cart handle approx. 23.3 mm diameter"
    root["Warning"] = "Visual/fit prototype only — not load-rated or safety-certified"

    # Broad rigid backing and a single continuous, soft-touch face.
    shell = add_box("HCD_Rest_Panel_Shell", (0.026, REST_WIDTH, REST_HEIGHT),
                    (-0.086, 0.0, -0.140), shell_mat, assembly, bevel=0.011,
                    parent=root)
    shell["Part"] = "460 mm wide articulated backing plate"
    cushion = add_box("HCD_Rest_Cushion", (0.060, CUSHION_WIDTH, CUSHION_HEIGHT),
                      (-0.126, 0.0, -0.141), tpe, assembly, bevel=0.024,
                      parent=root)
    cushion["Part"] = "430 × 238 mm cushioned contact face"
    cushion["Soft finish"] = "Subtle horizontal grip texture via procedural bump"

    # Two moving hinge ears on the panel and two fixed clamps around the handle.
    # Y is the hinge axis; rotating around it swings the pad down and inward.
    side_signs = (("Left", -1.0), ("Right", 1.0))
    for side, sign in side_signs:
        y_local = sign * 0.233
        clamp_y = ymid + sign * 0.213
        # Handle collars and drop brackets bridge down/in from the crossbar to
        # a lower pivot tucked over the basket rim.
        add_torus(f"HCD_Handle_Clamp_{side}", HANDLE_DIAMETER / 2.0 + 0.0035,
                  0.0032, (hx, clamp_y, hz), metal, assembly)
        add_box(f"HCD_Clamp_Saddle_{side}", (0.045, 0.058, 0.056),
                (hx + 0.004, clamp_y, hz - 0.004), dark, assembly, bevel=0.008)
        bracket_start = Vector((hx + 0.020, clamp_y, hz - 0.018))
        bracket_end = Vector((pivot_x, clamp_y, pivot_z))
        bracket = add_oriented_beam(
            f"HCD_Drop_Bracket_{side}", bracket_start, bracket_end,
            0.026, 0.030, dark, assembly, bevel=0.006)
        bracket["Part"] = "Rigid drop link from handle clamp to lower fold axis"
        fixed_disc = add_axis_y_cylinder(
            f"HCD_Hinge_Mount_{side}", 0.034, 0.012,
            (pivot_x, ymid + sign * 0.241, pivot_z), dark,
            assembly, bevel=0.0014)
        fixed_disc["Part"] = "Cart-side hinge bracket; static to drop link"
        moving_disc = add_axis_y_cylinder(
            f"HCD_Hinge_Ear_{side}", 0.029, 0.010,
            (0.0, y_local, 0.0), metal, assembly, bevel=0.0012, parent=root)
        moving_disc["Part"] = "Panel-side hinge ear; rotates with the rest"
        # A visible pin and a yellow/orange positive-lock release flag.
        add_axis_y_cylinder(
            f"HCD_Hinge_Pin_{side}", 0.0065, 0.020,
            (pivot_x, ymid + sign * 0.252, pivot_z), metal,
            assembly, bevel=0.001)
        latch = add_box(
            f"HCD_Hinge_Lock_Tab_{side}", (0.024, 0.012, 0.032),
            (-0.004, sign * 0.244, 0.036), latch_mat, assembly, bevel=0.005,
            parent=root)
        latch["Part"] = "Release tab for conceptual two-position hinge lock"

    # Compact stay pivots attach to the rear basket sides. Their telescoping
    # members brace the pad when open and extend into the basket as it stows.
    stay_anchors: dict[str, Vector] = {}
    panel_local_endpoints: dict[str, Vector] = {}
    outer_rods: dict[str, bpy.types.Object] = {}
    inner_rods: dict[str, bpy.types.Object] = {}
    collar_objs: dict[str, bpy.types.Object] = {}
    for side, sign in side_signs:
        y = ymid + sign * 0.195
        anchor = Vector((pivot_x, y, pivot_z - 0.170))
        end_local = Vector((-0.070, sign * 0.205, -0.263))
        stay_anchors[side] = anchor
        panel_local_endpoints[side] = end_local
        add_box(f"HCD_Stay_Mount_{side}", (0.040, 0.052, 0.046),
                tuple(anchor), dark, assembly, bevel=0.009)
        add_sphere(f"HCD_Stay_Cart_Pivot_{side}", 0.015, tuple(anchor), metal, assembly)
        add_sphere(f"HCD_Stay_Panel_Pivot_{side}", 0.013, tuple(end_local), metal,
                   assembly, parent=root)
        outer_rods[side] = make_animated_rod(
            f"HCD_Stay_Outer_Tube_{side}", 0.0085, assembly, dark)
        inner_rods[side] = make_animated_rod(
            f"HCD_Stay_Inner_Rod_{side}", 0.0048, assembly, metal)
        collar_objs[side] = add_torus(
            f"HCD_Stay_Lock_Collar_{side}", 0.009, 0.0025,
            tuple(anchor), latch_mat, assembly, axis_y=False)

    # Animate at deployed, halfway, and stowed. Each stay remains attached at
    # the exact modeled pivots at all three key poses while telescoping.
    pose_frames = ((DEPLOY_FRAME, DEPLOYED_ANGLE),
                   (MID_FOLD_FRAME, (DEPLOYED_ANGLE + STOWED_ANGLE) / 2.0),
                   (STOW_FRAME, STOWED_ANGLE))
    scene.frame_start = DEPLOY_FRAME
    scene.frame_end = STOW_FRAME
    root.rotation_mode = "XYZ"
    for frame, angle in pose_frames:
        root.rotation_euler = (0.0, angle, 0.0)
        root.keyframe_insert(data_path="rotation_euler", frame=frame)
        rot = Matrix.Rotation(angle, 3, "Y")
        for side, sign in side_signs:
            anchor = stay_anchors[side]
            end = root_location + rot @ panel_local_endpoints[side]
            axis = (end - anchor).normalized()
            full_len = (end - anchor).length
            # A fixed outer sleeve and a sliding inner rod overlap by 28 mm.
            sleeve_len = 0.095
            overlap = 0.028
            sleeve_end = anchor + axis * sleeve_len
            inner_start = anchor + axis * (sleeve_len - overlap)
            keyframe_strut(outer_rods[side], anchor, sleeve_end, frame, 0.0085)
            keyframe_strut(inner_rods[side], inner_start, end, frame, 0.0048)
            # The collar moves along the telescoping joint with the sleeve tip.
            collar = collar_objs[side]
            collar.location = sleeve_end
            collar.rotation_mode = "QUATERNION"
            collar.rotation_quaternion = axis.to_track_quat("Z", "Y")
            collar.keyframe_insert(data_path="location", frame=frame)
            collar.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            print(f"  {side} stay @ frame {frame}: {full_len * 1000:.0f} mm")

    scene.timeline_markers.clear()
    scene.timeline_markers.new("DEPLOYED — lean", frame=DEPLOY_FRAME)
    scene.timeline_markers.new("MID-FOLD", frame=MID_FOLD_FRAME)
    scene.timeline_markers.new("STOWED — inside basket", frame=STOW_FRAME)
    scene.frame_set(DEPLOY_FRAME)

    # A native scene camera/light set for quick inspection in Blender. The
    # dedicated render_studio.py script builds temporary multi-view studios.
    target = root_location + Vector((-0.035, 0.0, -0.135))
    add_presentation_camera(presentation, target)
    scene.world.color = (0.035, 0.045, 0.06)
    set_render_defaults(scene)
    scene.frame_set(DEPLOY_FRAME)
    bpy.context.view_layer.update()

    # Make the root selected for a convenient timeline/control experience.
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"\nSaved fold-out leaning support to {blend_path}")
    print(f"  frame {DEPLOY_FRAME}: deployed broad padded backrest")
    print(f"  frame {STOW_FRAME}: folds inward, horizontally inside the cart basket")
    print("  prototype only; verify structure, clearances, hinge locks, and loads physically")


if __name__ == "__main__":
    main()
