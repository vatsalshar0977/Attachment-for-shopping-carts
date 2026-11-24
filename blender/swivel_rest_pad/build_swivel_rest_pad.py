#!/usr/bin/env python3
"""Build a parametric, rigged swivel-rest-pad concept in cart context.

Run from the repository with Blender 4.5.x:
    blender --background --python blender/swivel_rest_pad/build_swivel_rest_pad.py

The builder copies only the Shopping Cart context mesh from
blender/source/hcd mockup.blend; that source project is never edited. The
packed grocery-aisle plate is loaded from blender/swivel_rest_pad/assets.
All attachment dimensions are millimeters. RENDER stays False by default.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

# ── Palette: the only source of material colors ──────────────────────────────
PALETTE = {
    "BACKDROP": "#F2EFE9",
    "BODY": "#3A4C40",
    "SAGE": "#8BA892",
    "TERRACOTTA": "#C4694A",
}

# ── Parametric dimensions (millimeters) ──────────────────────────────────────
HANDLEBAR_DIAMETER_MM = 25.0       # specified assumption; verify on real cart
HANDLEBAR_LENGTH_MM = 400.0
CLAMP_OUTER_DIAMETER_MM = 28.0
CLAMP_WALL_THICKNESS_MM = 3.0
CLAMP_LENGTH_MM = 110.0
CLAMP_SLOT_WIDTH_MM = 22.0
CLAMP_LIP_FLEX_MM = 1.5            # per lip; illustrative snap-flex shape key
# The nominal Ø28 / 3 mm-wall bore is Ø22; this radial flex opens it enough
# to clear the assumed Ø25 bar, documenting the brief's dimensional conflict.
CLAMP_RADIAL_FLEX_MM = max(
    0.0,
    HANDLEBAR_DIAMETER_MM * 0.5 + 0.15
    - (CLAMP_OUTER_DIAMETER_MM * 0.5 - CLAMP_WALL_THICKNESS_MM),
)
BRANCH_DIAMETER_MM = 22.0
BRANCH_LENGTH_MM = 55.0
BRANCH_WALL_MM = 3.0
COLLAR_DIAMETER_MM = 27.0
COLLAR_LENGTH_MM = 10.0
PAD_LENGTH_MM = 280.0              # cushion length, parallel to the cart handlebar
PAD_WIDTH_MM = 160.0               # vertical cushion height in the upright backrest pose
PAD_THICKNESS_MM = 35.0
PAD_CROWN_HEIGHT_MM = 4.0
NEUTRAL_TILT_DEGREES = 12.0       # forward resting pitch of the cushion
BASE_PLATE_THICKNESS_MM = 3.0
BASE_PLATE_CENTER_Z_MM = -(PAD_THICKNESS_MM * 0.5 + BASE_PLATE_THICKNESS_MM * 0.5)
PART_B_DIAMETER_MM = 18.0
PART_B_LENGTH_MM = 100.0
PART_B_WALL_MM = 2.5
METAL_EDGE_BEVEL_MM = 0.5
FPS = 24
USE_4K = False
PREVIEW_EEVEE = False
RENDER = False

# The detailed 13-second timing below is authoritative where the brief also
# mentions a shorter 10-second duration. Edit these frame pairs to retime stages.
TIMING = {
    "INTRO": (1, 24),
    "ASSEMBLE": (25, 96),
    "CLAMP": (97, 144),
    "SWIVEL": (145, 192),
    "TILT": (193, 240),
    "LATCH": (241, 276),
    "HOLD": (277, 312),
}
FRAME_START = 1
FRAME_END = 312
STARTUP_FRAME = 1  # close product hero view when the file opens

# The cart mesh is copied and measured at build time. The center of its actual
# handlebar island drives the mount location; the source project stays untouched.
CART_CONTEXT_SCALE = 1000.0
CLAMP_CENTER_Z = CLAMP_OUTER_DIAMETER_MM / 2.0
BRANCH_DIRECTION = -1.0
BRANCH_TIP_Z = BRANCH_DIRECTION * (CLAMP_CENTER_Z + BRANCH_LENGTH_MM)
PAD_MOUNT_OFFSET_Y = 0.0
PAD_CENTER_Y = -PAD_MOUNT_OFFSET_Y
TILT_AXIS_OFFSET_Y_MM = 0.0  # central bearing beneath the cushion's midpoint
AXLE_PLATE_OFFSET_Y_MM = TILT_AXIS_OFFSET_Y_MM - PAD_CENTER_Y
PLATE_AXIS_Z = BRANCH_DIRECTION * 31.0  # upright cushion center sits 100 mm below the handle
TILT_AXIS_Z = -8.0                      # hinge offset into the backplate
PAD_CENTER_FROM_TILT_Z = 8.0            # cushion shifts toward the shopper from the hinge
PAD_STEM_BOTTOM_Z_MM = PART_B_DIAMETER_MM * 0.5 + 5.0
PAD_STEM_TOP_Z_MM = -PLATE_AXIS_Z + COLLAR_LENGTH_MM
PAD_STEM_LENGTH_MM = PAD_STEM_TOP_Z_MM - PAD_STEM_BOTTOM_Z_MM
PAD_STEM_CENTER_Z_MM = (PAD_STEM_TOP_Z_MM + PAD_STEM_BOTTOM_Z_MM) * 0.5

PROJECT_DIR = Path(__file__).resolve().parent
CART_REFERENCE_BLEND = PROJECT_DIR.parent / "source" / "hcd mockup.blend"
GROCERY_BACKGROUND_IMAGE = PROJECT_DIR / "assets" / "grocery_aisle_background.png"
OUTPUT_BLEND = PROJECT_DIR / "swivel_pad_animated.blend"

COLLECTIONS: dict[str, bpy.types.Collection] = {}
OBJECTS: dict[str, bpy.types.Object] = {}
MATERIALS: dict[str, bpy.types.Material] = {}
LINEAR_PALETTE: dict[str, tuple[float, float, float, float]] = {}


# ── Common utility functions ─────────────────────────────────────────────────
def srgb_hex_to_linear(hex_value: str) -> tuple[float, float, float, float]:
    """Convert an sRGB hex triplet to Blender-linear RGBA."""
    value = hex_value.strip().lstrip("#")
    rgb = [int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return (linear[0], linear[1], linear[2], 1.0)


def make_palette() -> dict[str, tuple[float, float, float, float]]:
    """Return the four user-specified palette colors in Blender-linear space."""
    return {name: srgb_hex_to_linear(value) for name, value in PALETTE.items()}


def mix_rgba(a, b, factor: float) -> tuple[float, float, float, float]:
    return tuple((1.0 - factor) * a[i] + factor * b[i] for i in range(3)) + (1.0,)


def scale_rgba(color, factor: float) -> tuple[float, float, float, float]:
    return tuple(max(0.0, min(1.0, color[i] * factor)) for i in range(3)) + (1.0,)


def ensure_collection(name: str) -> bpy.types.Collection:
    collection = COLLECTIONS.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
        COLLECTIONS[name] = collection
    return collection


def link_object(obj: bpy.types.Object, collection_name: str) -> bpy.types.Object:
    collection = ensure_collection(collection_name)
    if collection not in obj.users_collection:
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)
    return obj


def remember(obj: bpy.types.Object, key: str | None = None) -> bpy.types.Object:
    OBJECTS[key or obj.name] = obj
    return obj


def set_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    if obj.type == "MESH":
        obj.data.materials.clear()
        obj.data.materials.append(material)
    elif obj.type == "CURVE":
        obj.data.materials.clear()
        obj.data.materials.append(material)
    elif obj.type == "FONT":
        obj.data.materials.clear()
        obj.data.materials.append(material)


def recalc_normals(obj: bpy.types.Object) -> None:
    if obj.type != "MESH":
        return
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def set_smooth(obj: bpy.types.Object) -> None:
    if obj.type == "MESH":
        for polygon in obj.data.polygons:
            polygon.use_smooth = True


def add_bevel(obj: bpy.types.Object, width: float = METAL_EDGE_BEVEL_MM,
              segments: int = 3, name: str = "Edge Bevel · 0.5 mm") -> bpy.types.Modifier:
    modifier = obj.modifiers.new(name, "BEVEL")
    modifier.width = width
    modifier.segments = segments
    modifier.limit_method = "ANGLE"
    if hasattr(modifier, "harden_normals"):
        modifier.harden_normals = True
    return modifier


def add_weighted_normals(obj: bpy.types.Object) -> None:
    modifier = obj.modifiers.new("Machined face normals", "WEIGHTED_NORMAL")
    if hasattr(modifier, "keep_sharp"):
        modifier.keep_sharp = True
    if hasattr(modifier, "weight"):
        modifier.weight = 40


def apply_scale(obj: bpy.types.Object) -> None:
    """Apply primitive sizing while leaving object scale at exactly 1."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    except RuntimeError:
        pass
    obj.select_set(False)
    obj.scale = (1.0, 1.0, 1.0)


def parent_local(obj: bpy.types.Object, parent: bpy.types.Object) -> None:
    """Parent while interpreting the object's existing transform as local."""
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)


def set_axis(obj: bpy.types.Object, axis: Vector) -> None:
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = axis.normalized().to_track_quat("Z", "Y")


def bevelled_box(name: str, dimensions: tuple[float, float, float], location,
                 material: bpy.types.Material, collection_name: str,
                 bevel: float = 0.5, rotation=None) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    apply_scale(obj)
    if rotation is not None:
        obj.rotation_euler = rotation
    link_object(obj, collection_name)
    set_material(obj, material)
    if bevel > 0:
        add_bevel(obj, min(bevel, min(dimensions) * 0.45), 3)
        add_weighted_normals(obj)
    return remember(obj)


def cylinder(name: str, radius: float, depth: float, location,
             material: bpy.types.Material, collection_name: str,
             axis: Vector | None = None, bevel: float = 0.5,
             vertices: int = 64) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                        depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    if axis is not None:
        set_axis(obj, axis)
    apply_scale(obj)
    link_object(obj, collection_name)
    set_material(obj, material)
    set_smooth(obj)
    if bevel > 0:
        add_bevel(obj, min(bevel, radius * 0.45, depth * 0.2), 3)
        add_weighted_normals(obj)
    return remember(obj)


def sphere(name: str, radius: float, location, material: bpy.types.Material,
           collection_name: str, scale=(1.0, 1.0, 1.0)) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16,
                                         radius=radius, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    apply_scale(obj)
    link_object(obj, collection_name)
    set_material(obj, material)
    set_smooth(obj)
    return remember(obj)


def mesh_object(name: str, vertices, faces, collection_name: str,
                material: bpy.types.Material | None = None) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    ensure_collection(collection_name).objects.link(obj)
    if material is not None:
        set_material(obj, material)
    recalc_normals(obj)
    return remember(obj)


def add_tube_mesh(name: str, outer_radius: float, inner_radius: float,
                  length: float, location, collection_name: str,
                  material: bpy.types.Material, axis: Vector | None = None,
                  bevel: float = 0.5, segments: int = 96) -> bpy.types.Object:
    """Create a hollow, open-ended tube around local Z with annular end faces."""
    verts = []
    for z in (-length * 0.5, length * 0.5):
        for radius in (outer_radius, inner_radius):
            for i in range(segments):
                angle = math.tau * i / segments
                verts.append((radius * math.cos(angle), radius * math.sin(angle), z))
    ob, ot, ib, it = 0, segments, 2 * segments, 3 * segments
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((ob + i, ob + j, ot + j, ot + i))
        faces.append((ib + i, it + i, it + j, ib + j))
        faces.append((ob + i, ot + i, it + i, ib + i))
        faces.append((ob + j, ib + j, it + j, ot + j))
    obj = mesh_object(name, verts, faces, collection_name, material)
    obj.location = location
    if axis is not None:
        set_axis(obj, axis)
    set_smooth(obj)
    if bevel > 0:
        add_bevel(obj, min(bevel, (outer_radius - inner_radius) * 0.45), 3)
        add_weighted_normals(obj)
    obj["Tube OD mm"] = outer_radius * 2
    obj["Tube ID mm"] = inner_radius * 2
    obj["Tube length mm"] = length
    return obj


def add_curve(name: str, points, radius: float, material: bpy.types.Material,
              collection_name: str, cyclic: bool = False) -> bpy.types.Object:
    data = bpy.data.curves.new(name + "_Curve", "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 16
    data.bevel_depth = radius
    data.bevel_resolution = 4
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        spline_point = Vector(co)
        point.co = (spline_point.x, spline_point.y, spline_point.z, 1.0)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, data)
    ensure_collection(collection_name).objects.link(obj)
    data.materials.append(material)
    return remember(obj)


def add_text(name: str, body: str, size: float, location,
             material: bpy.types.Material, collection_name: str,
             rotation=None, align_x: str = "LEFT") -> bpy.types.Object:
    data = bpy.data.curves.new(name + "_Text", "FONT")
    data.body = body
    data.size = size
    data.align_x = align_x
    data.align_y = "CENTER"
    data.extrude = 0.0
    data.bevel_depth = 0.0
    obj = bpy.data.objects.new(name, data)
    ensure_collection(collection_name).objects.link(obj)
    obj.location = location
    if rotation is not None:
        obj.rotation_euler = rotation
    set_material(obj, material)
    return remember(obj)


def boolean_difference(target: bpy.types.Object, cutter: bpy.types.Object,
                       name: str = "Precision Cut") -> None:
    modifier = target.modifiers.new(name, "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.object = cutter
    if hasattr(modifier, "solver"):
        modifier.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    cutter.select_set(False)
    try:
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    finally:
        target.select_set(False)
        if cutter.name in bpy.data.objects:
            bpy.data.objects.remove(cutter, do_unlink=True)
    recalc_normals(target)


def capsule_prism_x(name: str, width: float, length: float, x_depth: float,
                    center_z: float, collection_name: str) -> bpy.types.Object:
    """Capsule cutter in the local YZ plane, extruded from X=0 to +depth."""
    r = width * 0.5
    straight = max(0.0, (length - width) * 0.5)
    points = []
    steps = 14
    for i in range(steps + 1):
        a = math.pi * i / steps
        points.append((r * math.cos(a), center_z + straight + r * math.sin(a)))
    for i in range(steps + 1):
        a = math.pi + math.pi * i / steps
        points.append((r * math.cos(a), center_z - straight + r * math.sin(a)))
    verts = []
    for x in (0.0, x_depth):
        verts.extend((x, y, z) for y, z in points)
    n = len(points)
    faces = [tuple(range(n)), tuple(range(n, 2 * n))[::-1]]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return mesh_object(name, verts, faces, collection_name)


def key_object(obj: bpy.types.Object, data_path: str, frame: int) -> None:
    obj.keyframe_insert(data_path=data_path, frame=frame)


def key_component(obj: bpy.types.Object, data_path: str, index: int, frame: int) -> None:
    obj.keyframe_insert(data_path=data_path, index=index, frame=frame)


def key_property(obj: bpy.types.Object, property_name: str,
                 frame: int, value: float) -> None:
    obj[property_name] = value
    obj.keyframe_insert(data_path=f'["{property_name}"]', frame=frame,
                        group="Assembly Controller")


def tune_action(obj: bpy.types.Object, interpolation: str = "BEZIER") -> None:
    animation_data = obj.animation_data
    if not animation_data or not animation_data.action:
        return
    action = animation_data.action
    try:
        curves = action.fcurves
    except (AttributeError, TypeError):
        return
    for fcurve in curves:
        for point in fcurve.keyframe_points:
            point.interpolation = interpolation
            if interpolation == "BEZIER":
                point.handle_left_type = "AUTO_CLAMPED"
                point.handle_right_type = "AUTO_CLAMPED"


def add_multi_property_driver(target: bpy.types.Object, data_path: str, index: int,
                              controller: bpy.types.Object,
                              properties: dict[str, str], expression: str) -> bpy.types.FCurve:
    fcurve = target.driver_add(data_path, index)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    for variable_name, property_name in properties.items():
        variable = driver.variables.new()
        variable.name = variable_name
        variable.type = "SINGLE_PROP"
        variable.targets[0].id = controller
        variable.targets[0].data_path = f'["{property_name}"]'
    driver.expression = expression
    return fcurve


def add_property_driver(target: bpy.types.Object, data_path: str, index: int,
                        controller: bpy.types.Object, property_name: str,
                        expression: str) -> bpy.types.FCurve:
    return add_multi_property_driver(target, data_path, index, controller,
                                     {"value": property_name}, expression)


# ── Materials and palette-derived shaders ─────────────────────────────────────
def principled_material(name: str, color, roughness: float,
                        metallic: float = 0.0) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def set_socket(node, names: tuple[str, ...], value) -> bool:
    for name in names:
        if name in node.inputs:
            node.inputs[name].default_value = value
            return True
    return False


def make_gradient_material(name: str, axis_component: str,
                           coordinate_min: float, coordinate_max: float) -> bpy.types.Material:
    material = principled_material(name, LINEAR_PALETTE["SAGE"], 0.45, 0.35)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    texture = nodes.new("ShaderNodeTexCoord")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    links.new(texture.outputs["Object"], separate.inputs["Vector"])
    map_range = nodes.new("ShaderNodeMapRange")
    map_range.inputs["From Min"].default_value = coordinate_min
    map_range.inputs["From Max"].default_value = coordinate_max
    map_range.inputs["To Min"].default_value = 0.0
    map_range.inputs["To Max"].default_value = 1.0
    links.new(separate.outputs[axis_component], map_range.inputs["Value"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = LINEAR_PALETTE["SAGE"]
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = LINEAR_PALETTE["TERRACOTTA"]
    ramp.color_ramp.interpolation = "EASE"
    links.new(map_range.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    return material


def add_noise_bump(material: bpy.types.Material, scale: float,
                   strength: float, distance: float) -> None:
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader = next((node for node in nodes if node.type == "BSDF_PRINCIPLED"), None)
    if shader is None:
        return
    texcoord = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.62
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    links.new(texcoord.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])


def make_materials() -> dict[str, bpy.types.Material]:
    """Create all materials from PALETTE colors or blends derived from it."""
    global LINEAR_PALETTE
    LINEAR_PALETTE = make_palette()
    body = LINEAR_PALETTE["BODY"]
    cream = LINEAR_PALETTE["BACKDROP"]
    sage = LINEAR_PALETTE["SAGE"]
    terra = LINEAR_PALETTE["TERRACOTTA"]
    warm_aluminum = mix_rgba(sage, cream, 0.78)
    pale_sage = mix_rgba(cream, sage, 0.25)
    cart_tint = mix_rgba(body, sage, 0.62)
    dark_body = scale_rgba(body, 0.90)

    mats = {
        "Pad": principled_material("Pad · Forest soft-touch", body, 0.65, 0.0),
        "Base": principled_material("Base plate · 10% darker forest", dark_body, 0.68, 0.0),
        "Aluminum": principled_material("Warm brushed aluminum", warm_aluminum, 0.30, 1.0),
        "MetalDark": principled_material("Anodized recess · palette-derived", scale_rgba(warm_aluminum, 0.68), 0.36, 0.82),
        "Terracotta": principled_material("Terracotta satin control", terra, 0.40, 0.0),
        "Sage": principled_material("Sage motion graphic", sage, 0.78, 0.0),
        "SagePanel": principled_material("Sage hatch panel · 25% tint", pale_sage, 0.82, 0.0),
        "Label": principled_material("Forest labels", body, 0.64, 0.0),
        "CartContext": principled_material("Cart context · satin sage metal", cart_tint, 0.38, 0.58),
    }
    # Fine procedural grain stays subtle and all tints remain palette-derived.
    add_noise_bump(mats["Pad"], 185.0, 0.07, 0.11)
    add_noise_bump(mats["Aluminum"], 270.0, 0.035, 0.08)
    metal_shader = next(node for node in mats["Aluminum"].node_tree.nodes
                        if node.type == "BSDF_PRINCIPLED")
    set_socket(metal_shader, ("Anisotropic", "Anisotropic IOR Level"), 0.32)
    set_socket(metal_shader, ("Anisotropic Rotation",), 0.18)

    gradient_c = make_gradient_material("Interior gradient · clamp bore", "X", -55.0, 55.0)
    gradient_b = make_gradient_material("Interior gradient · axle strip", "Z", -32.0, -4.0)
    mats["GradientClamp"] = gradient_c
    mats["GradientAxle"] = gradient_b

    emission = bpy.data.materials.new("Terracotta pulse · emission")
    emission.diffuse_color = terra
    emission.use_nodes = True
    emission.node_tree.nodes.clear()
    out = emission.node_tree.nodes.new("ShaderNodeOutputMaterial")
    em = emission.node_tree.nodes.new("ShaderNodeEmission")
    em.name = "Pulse_Emission"
    em.inputs["Color"].default_value = terra
    em.inputs["Strength"].default_value = 0.0
    emission.node_tree.links.new(em.outputs["Emission"], out.inputs["Surface"])
    mats["Pulse"] = emission

    MATERIALS.clear()
    MATERIALS.update(mats)
    return MATERIALS


def detect_cart_handlebar(cart: bpy.types.Object) -> dict[str, object]:
    """Measure the long, round handlebar island in the copied cart mesh."""
    bpy.context.view_layer.update()
    mesh = cart.data
    adjacency = [set() for _ in mesh.vertices]
    for edge in mesh.edges:
        a, b = edge.vertices
        adjacency[a].add(b)
        adjacency[b].add(a)

    matrix = cart.matrix_world.copy()
    seen: set[int] = set()
    candidates = []
    for start in range(len(mesh.vertices)):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        component = []
        while stack:
            index = stack.pop()
            component.append(index)
            for neighbor in adjacency[index]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        points = [matrix @ mesh.vertices[index].co for index in component]
        if len(points) < 8:
            continue
        minimum = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
        maximum = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
        dimensions = maximum - minimum
        long_axis_index = max(range(3), key=lambda axis: dimensions[axis])
        cross_axes = [axis for axis in range(3) if axis != long_axis_index]
        long_length = dimensions[long_axis_index]
        cross_dims = [dimensions[axis] for axis in cross_axes]
        center = (minimum + maximum) * 0.5
        # Exclude basket rails, wheels, and the basket mesh: this component is
        # the approximately 0.49 m round tube at the cart's push-handle height.
        if (long_axis_index == 1 and 400.0 <= long_length <= 550.0
                and max(cross_dims) < 45.0 and min(cross_dims) > 12.0
                and center.z > 850.0):
            candidates.append((abs(long_length - 480.0), center, dimensions,
                               long_axis_index))
    if not candidates:
        raise RuntimeError("Could not identify the actual push handlebar in the copied cart mesh")
    _, center, dimensions, long_axis_index = min(candidates, key=lambda item: item[0])
    local_axis = Vector((0.0, 1.0, 0.0))
    axis = (matrix.to_3x3() @ local_axis).normalized()
    if axis.y < 0.0:
        axis.negate()
    cross_axes = [axis_index for axis_index in range(3) if axis_index != long_axis_index]
    diameter = (dimensions[cross_axes[0]] + dimensions[cross_axes[1]]) * 0.5
    return {
        "center": tuple(center),
        "axis": tuple(axis),
        "diameter": float(diameter),
        "length": float(dimensions[long_axis_index]),
    }


def make_cart_context() -> dict[str, object]:
    """Append and measure a palette-tinted cart copy; never edit the source."""
    if not CART_REFERENCE_BLEND.is_file():
        raise FileNotFoundError(f"Cart reference not found: {CART_REFERENCE_BLEND}")
    cart_root = make_empty("Cart_Context_Root", "Cart_Context", (0.0, 0.0, 0.0),
                           "PLAIN_AXES", 50.0)
    existing_material_names = {material.name for material in bpy.data.materials}
    with bpy.data.libraries.load(str(CART_REFERENCE_BLEND), link=False) as (source, target):
        if "Shopping Cart" not in source.objects:
            raise RuntimeError(f"No 'Shopping Cart' object in {CART_REFERENCE_BLEND}")
        target.objects = ["Shopping Cart"]
    cart = target.objects[0]
    if cart is None:
        raise RuntimeError("Could not append Shopping Cart reference object")
    cart.name = "Shopping_Cart_Context"
    link_object(cart, "Cart_Context")
    parent_local(cart, cart_root)
    cart.location = tuple(value * CART_CONTEXT_SCALE for value in cart.location)
    cart.scale = tuple(value * CART_CONTEXT_SCALE for value in cart.scale)
    if cart.type != "MESH":
        raise TypeError("Shopping Cart context must be a mesh to measure its handlebar")
    cart.data.materials.clear()
    cart.data.materials.append(MATERIALS["CartContext"])
    handle = detect_cart_handlebar(cart)
    for material in list(bpy.data.materials):
        if material.name not in existing_material_names and material.users == 0:
            bpy.data.materials.remove(material)
    cart["Context source"] = "Copied from blender/source/hcd mockup.blend; source file unchanged"
    cart["Reference dimensions mm"] = "1030 × 530 × 1112 (approximate source bounds)"
    cart["Measured handle center mm"] = handle["center"]
    cart["Measured handle axis"] = handle["axis"]
    cart["Measured handle Ø × length mm"] = (
        round(handle["diameter"], 2), round(handle["length"], 2))
    cart_root["Handlebar axis"] = handle["axis"]
    cart_root["Handlebar center mm"] = handle["center"]
    cart_root["Motion"] = "Stationary cart reference; only the attachment pivots"
    cart_root["Context only"] = True
    return {"root": cart_root, "cart": cart, "handle": handle}


# ── Main C-profile clamp and Part A T-connector ───────────────────────────────
def c_profile_clamp_mesh() -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[int], list[tuple[float, float]]]:
    outer_radius = CLAMP_OUTER_DIAMETER_MM / 2.0
    inner_radius = outer_radius - CLAMP_WALL_THICKNESS_MM
    slot_half = math.asin(min(0.999, CLAMP_SLOT_WIDTH_MM / (2.0 * outer_radius)))
    gap_center = math.pi  # local -Y opening; mounted orientation faces cart-front (+X)
    start = gap_center + slot_half
    end = gap_center + math.tau - slot_half
    steps = 72
    outer_angles = [start + (end - start) * i / steps for i in range(steps + 1)]
    inner_angles = list(reversed(outer_angles))
    profile: list[tuple[float, float, float, str]] = []
    for a in outer_angles:
        profile.append((outer_radius * math.cos(a), outer_radius * math.sin(a), a, "outer"))
    for a in inner_angles:
        profile.append((inner_radius * math.cos(a), inner_radius * math.sin(a), a, "inner"))

    verts = []
    half_len = CLAMP_LENGTH_MM * 0.5
    for x in (-half_len, half_len):
        verts.extend((x, y, z) for y, z, _, _ in profile)
    profile_count = len(profile)
    faces: list[tuple[int, ...]] = []
    material_ids: list[int] = []
    for i in range(profile_count):
        j = (i + 1) % profile_count
        faces.append((i, j, profile_count + j, profile_count + i))
        # The long inside arc receives the sage-to-terracotta gradient liner.
        material_ids.append(1 if profile[i][3] == "inner" and profile[j][3] == "inner" else 0)
    faces.append(tuple(range(profile_count)))
    material_ids.append(0)
    faces.append(tuple(range(profile_count, 2 * profile_count))[::-1])
    material_ids.append(0)
    flex_weights = [(y, z, angle, kind) for y, z, angle, kind in profile] * 2
    return verts, faces, material_ids, flex_weights


def make_clamp() -> dict[str, bpy.types.Object]:
    """Build Part A: slotted C-shell, perpendicular branch, and locking collar."""
    verts, faces, material_ids, flex_weights = c_profile_clamp_mesh()
    mesh = bpy.data.meshes.new("PartA_C_Profile_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    shell = bpy.data.objects.new("PartA_Main_C_Profile_Clamp", mesh)
    ensure_collection("PartA_Clamp").objects.link(shell)
    shell.data.materials.append(MATERIALS["Aluminum"])
    shell.data.materials.append(MATERIALS["GradientClamp"])
    for polygon, material_index in zip(shell.data.polygons, material_ids):
        polygon.material_index = material_index
        polygon.use_smooth = True
    recalc_normals(shell)
    # Snap flex spreads both lips by 1.5 mm, widening the 22 mm opening by 3 mm.
    shell.shape_key_add(name="Basis")
    flex = shell.shape_key_add(name="Snap_Flex_1p5mm_per_lip")
    bore_clearance = shell.shape_key_add(name="Bore_Clearance_for_assumed_Ø25")
    for i, (y, z, angle, kind) in enumerate(flex_weights):
        theta = angle % math.tau
        upper_lip_angle = math.pi - math.asin(min(0.999, CLAMP_SLOT_WIDTH_MM / CLAMP_OUTER_DIAMETER_MM))
        lower_lip_angle = math.pi + math.asin(min(0.999, CLAMP_SLOT_WIDTH_MM / CLAMP_OUTER_DIAMETER_MM))
        upper_end = abs(theta - upper_lip_angle) < math.radians(24.0)
        lower_end = abs(theta - lower_lip_angle) < math.radians(24.0)
        if kind == "inner" and CLAMP_RADIAL_FLEX_MM > 0.0:
            radius = math.hypot(y, z)
            bore_clearance.data[i].co.y += y / radius * CLAMP_RADIAL_FLEX_MM
            bore_clearance.data[i].co.z += z / radius * CLAMP_RADIAL_FLEX_MM
        if lower_end or upper_end:
            # Smooth falloff moves the lower lip down and upper lip up.
            if lower_end:
                weight = max(0.0, 1.0 - abs(theta - lower_lip_angle) / math.radians(24.0))
                sign = -1.0
            else:
                weight = max(0.0, 1.0 - abs(theta - upper_lip_angle) / math.radians(24.0))
                sign = 1.0
            flex.data[i].co.z += sign * CLAMP_LIP_FLEX_MM * weight
    add_bevel(shell, METAL_EDGE_BEVEL_MM, 3, "Snap-shell edge radius")
    add_weighted_normals(shell)
    shell["Part"] = "Part A · single central C-profile snap clamp"
    shell["Slot width mm"] = CLAMP_SLOT_WIDTH_MM
    shell["Nominal handlebar mm"] = HANDLEBAR_DIAMETER_MM
    shell["Nominal wall mm"] = CLAMP_WALL_THICKNESS_MM
    shell["Radial flex to clear assumed bar mm"] = CLAMP_RADIAL_FLEX_MM
    shell["Flex per lip mm"] = CLAMP_LIP_FLEX_MM
    remember(shell, "ClampShell")

    branch_center_z = BRANCH_DIRECTION * (CLAMP_CENTER_Z + BRANCH_LENGTH_MM * 0.5)
    branch = add_tube_mesh("PartA_T_Branch_Tube", BRANCH_DIAMETER_MM * 0.5,
                           BRANCH_DIAMETER_MM * 0.5 - BRANCH_WALL_MM,
                           BRANCH_LENGTH_MM, (0.0, 0.0, branch_center_z),
                           "PartA_Clamp", MATERIALS["Aluminum"],
                           axis=Vector((0.0, 0.0, 1.0)), bevel=METAL_EDGE_BEVEL_MM)
    branch["Part"] = "Part A · 90-degree branch stem"

    # Hollow machined collar with six boolean windows, then three rib rings.
    collar_center = BRANCH_DIRECTION * (CLAMP_CENTER_Z + BRANCH_LENGTH_MM - COLLAR_LENGTH_MM * 0.5)
    collar = add_tube_mesh("PartA_Ribbed_Window_Collar", COLLAR_DIAMETER_MM * 0.5,
                           BRANCH_DIAMETER_MM * 0.5 + 0.25,
                           COLLAR_LENGTH_MM, (0.0, 0.0, collar_center),
                           "PartA_Clamp", MATERIALS["Aluminum"],
                           axis=Vector((0.0, 0.0, 1.0)), bevel=0.0)
    # Window cutters are oriented radially through the collar wall.
    for i in range(6):
        angle = math.tau * i / 6.0
        radius = COLLAR_DIAMETER_MM * 0.5 - 0.4
        loc = (radius * math.cos(angle), radius * math.sin(angle), collar_center)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        cutter = bpy.context.object
        cutter.name = f"TEMP_Collar_Window_Cutter_{i+1}"
        cutter.dimensions = (8.0, 5.0, 4.2)
        cutter.rotation_euler[2] = angle
        apply_scale(cutter)
        boolean_difference(collar, cutter, f"Collar window {i+1}")
    add_bevel(collar, 0.45, 3, "Fine collar window edges")
    add_weighted_normals(collar)
    collar["Window count"] = 6
    collar["Part"] = "Part A · ribbed female-locking collar"
    for index, z in enumerate((collar_center - 3.5, collar_center, collar_center + 3.5), 1):
        bpy.ops.mesh.primitive_torus_add(major_radius=COLLAR_DIAMETER_MM * 0.5 - 0.1,
                                         minor_radius=0.55, major_segments=64,
                                         minor_segments=10, location=(0.0, 0.0, z))
        rib = bpy.context.object
        rib.name = f"PartA_Collar_Rib_{index}"
        link_object(rib, "PartA_Clamp")
        set_material(rib, MATERIALS["Aluminum"])
        set_smooth(rib)
        remember(rib)

    # A thin sage-to-terracotta wash in the T-branch bore hints at the cutaway.
    liner = add_tube_mesh("PartA_Bore_Gradient_Liner", 8.25, 7.9, BRANCH_LENGTH_MM - 4.0,
                          (0.0, 0.0, branch_center_z), "PartA_Clamp",
                          MATERIALS["GradientClamp"], axis=Vector((0.0, 0.0, 1.0)),
                          bevel=0.0, segments=64)
    liner["Visual only"] = True

    return {"shell": shell, "branch": branch, "collar": collar, "liner": liner}


def make_handlebar() -> bpy.types.Object:
    """Create the specified Ø25 × 400 mm overlay aligned to the cart handle."""
    bar = add_tube_mesh("Handlebar_Prop_Ø25x400", HANDLEBAR_DIAMETER_MM * 0.5,
                        HANDLEBAR_DIAMETER_MM * 0.5 - 2.4,
                        HANDLEBAR_LENGTH_MM, (0.0, 0.0, 0.0),
                        "Handlebar", MATERIALS["CartContext"],
                        axis=Vector((1.0, 0.0, 0.0)), bevel=0.35)
    bar["Specified size mm"] = "Ø25 × 400"
    bar["Context alignment"] = "Centered on the measured source-cart handle; visual overlay only"
    return remember(bar, "Handlebar")


# ── Part B: slotted axle and its gradient strip ───────────────────────────────
def make_axle() -> dict[str, bpy.types.Object]:
    """Build Part B as an Ø18 mm hollow axle with a machined oval slot."""
    outer = PART_B_DIAMETER_MM * 0.5
    inner = outer - PART_B_WALL_MM
    axle = add_tube_mesh("PartB_Pivot_Axle_Ø18x100", outer, inner,
                         PART_B_LENGTH_MM, (0.0, 0.0, 0.0),
                         "PartB_Axle", MATERIALS["Aluminum"],
                         axis=Vector((0.0, 0.0, 1.0)), bevel=0.0)
    slot_center_z = -PART_B_LENGTH_MM * 0.38
    cutter = capsule_prism_x("TEMP_PartB_Oval_Slot_Cutter", 5.0, 15.0,
                             22.0, slot_center_z, "PartB_Axle")
    boolean_difference(axle, cutter, "Oval pin engagement slot")
    add_bevel(axle, 0.5, 3, "Oval-slot edge break")
    add_weighted_normals(axle)
    axle["Part"] = "Part B · pivot axle"
    axle["Oval slot width mm"] = 5.0
    axle["Oval slot length mm"] = 15.0

    # Sage-to-terracotta strip sits behind the slot as a cutaway indicator.
    strip = bevelled_box("PartB_Gradient_Side_Strip",
                         (0.55, 4.2, 27.0),
                         (outer - 0.85, 0.0, slot_center_z),
                         MATERIALS["GradientAxle"], "PartB_Axle", bevel=0.18)
    parent_local(strip, axle)
    strip.location = (outer - 0.85, 0.0, slot_center_z)
    remember(strip)
    return {"axle": axle, "gradient_strip": strip}


# ── Cushioned leaning support, removable plate, and logo/details ──────────────
def superellipse_point(theta: float, a: float, b: float, exponent: float = 3.8):
    c, s = math.cos(theta), math.sin(theta)
    p = 2.0 / exponent
    x = a * math.copysign(abs(c) ** p, c)
    y = b * math.copysign(abs(s) ** p, s)
    return x, y


def make_cushion_mesh() -> bpy.types.Object:
    length = PAD_LENGTH_MM
    width = PAD_WIDTH_MM
    thickness = PAD_THICKNESS_MM
    a, b = length * 0.5, width * 0.5
    angular = 96
    radial = 14
    vertices = []
    faces = []
    top_start = 0
    bottom_start = 0
    ring_ids_top = []
    ring_ids_bottom = []
    # The cushion has a slight convex crown, not a seat-like central depression.
    vertices.append((0.0, 0.0, thickness * 0.5))
    for j in range(1, radial + 1):
        r = j / radial
        ring = []
        for i in range(angular):
            theta = math.tau * i / angular
            x, y = superellipse_point(theta, a, b, exponent=4.8)
            z = thickness * 0.5 - PAD_CROWN_HEIGHT_MM * r * r
            ring.append(len(vertices))
            vertices.append((x * r, y * r, z))
        ring_ids_top.append(ring)
    # Top fan and quads.
    first = ring_ids_top[0]
    for i in range(angular):
        j = (i + 1) % angular
        faces.append((top_start, first[i], first[j]))
    for ring_index in range(1, len(ring_ids_top)):
        prev, curr = ring_ids_top[ring_index - 1], ring_ids_top[ring_index]
        for i in range(angular):
            j = (i + 1) % angular
            faces.append((prev[i], curr[i], curr[j], prev[j]))

    # Rounded underside: a slightly convex support surface under the pad.
    bottom_center = len(vertices)
    vertices.append((0.0, 0.0, -thickness * 0.5 + 1.2))
    for j in range(1, radial + 1):
        r = j / radial
        ring = []
        for i in range(angular):
            theta = math.tau * i / angular
            x, y = superellipse_point(theta, a, b)
            z = -thickness * 0.5 + 1.2 * (1.0 - r * r)
            ring.append(len(vertices))
            vertices.append((x * r, y * r, z))
        ring_ids_bottom.append(ring)
    first = ring_ids_bottom[0]
    for i in range(angular):
        j = (i + 1) % angular
        faces.append((bottom_center, first[j], first[i]))
    for ring_index in range(1, len(ring_ids_bottom)):
        prev, curr = ring_ids_bottom[ring_index - 1], ring_ids_bottom[ring_index]
        for i in range(angular):
            j = (i + 1) % angular
            faces.append((prev[j], curr[j], curr[i], prev[i]))

    # Side wall joins the top and bottom perimeter rings.
    top_edge = ring_ids_top[-1]
    bottom_edge = ring_ids_bottom[-1]
    for i in range(angular):
        j = (i + 1) % angular
        faces.append((top_edge[i], bottom_edge[i], bottom_edge[j], top_edge[j]))

    obj = mesh_object("Pad_Body_Crowned_Cushion", vertices, faces,
                      "Pad_Body", MATERIALS["Pad"])
    set_smooth(obj)
    obj["Nominal size mm"] = f"{length:.0f} × {width:.0f} × {thickness:.0f}"
    obj["Crown height mm"] = PAD_CROWN_HEIGHT_MM
    obj["Surface"] = "Parametric rounded-corner cushion with a softly convex crown; leaning support, not a seat"
    return remember(obj, "PadBody")


def make_pad() -> dict[str, bpy.types.Object]:
    """Create the crowned leaning cushion, central socket, pivot, and details."""
    body = make_cushion_mesh()
    # A vertical socket receives the short Part A collar stem behind the cushion face.
    stem_socket_center_y = -PAD_STEM_CENTER_Z_MM
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=12.25,
                                        depth=PAD_STEM_LENGTH_MM + 2.0,
                                        location=(0.0, stem_socket_center_y, 0.0),
                                        rotation=(math.pi / 2.0, 0.0, 0.0))
    stem_cutter = bpy.context.object
    stem_cutter.name = "TEMP_Pad_Central_Stem_Socket"
    boolean_difference(body, stem_cutter, "Vertical stem receiver through cushion")
    axle_body_y = TILT_AXIS_OFFSET_Y_MM - PAD_CENTER_Y
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=13.5,
                                        depth=PART_B_LENGTH_MM + 12.0,
                                        location=(0.0, axle_body_y,
                                                  -PAD_CENTER_FROM_TILT_Z),
                                        rotation=(0.0, math.pi / 2.0, 0.0))
    axle_cutter = bpy.context.object
    axle_cutter.name = "TEMP_Pad_PartB_Barrel_Bore"
    boolean_difference(body, axle_cutter, "Part B rear barrel clearance tunnel")
    bpy.ops.mesh.primitive_cube_add(size=1.0,
                                    location=(0.0, axle_body_y + 32.0,
                                              -9.0 - PAD_CENTER_FROM_TILT_Z))
    latch_cavity = bpy.context.object
    latch_cavity.name = "TEMP_Pad_Latch_Cavity"
    latch_cavity.dimensions = (32.0, 24.0, 14.0)
    apply_scale(latch_cavity)
    boolean_difference(body, latch_cavity, "Underside latch service pocket")
    body["Clearance"] = "Stem receiver bore, rear-pivot tunnel, and latch service pocket are modeled"
    subdivision = body.modifiers.new("Soft crowned cushion surface", "SUBSURF")
    subdivision.subdivision_type = "CATMULL_CLARK"
    subdivision.levels = 1
    subdivision.render_levels = 2
    add_bevel(body, 0.35, 2, "Soft perimeter edge")

    receiver = add_tube_mesh("Pad_Stem_Receiver_Barrel", BRANCH_DIAMETER_MM * 0.5,
                             BRANCH_DIAMETER_MM * 0.5 - BRANCH_WALL_MM,
                             PAD_STEM_LENGTH_MM,
                             (0.0, -PAD_STEM_CENTER_Z_MM, PAD_CENTER_FROM_TILT_Z),
                             "Pad_Body", MATERIALS["Aluminum"],
                             axis=Vector((0.0, -1.0, 0.0)), bevel=0.5)
    receiver["Interface"] = "Ø22 stem nests inside the measured Part A collar; visual clearance only"
    receiver_liner = add_tube_mesh("Pad_Receiver_Gradient_Liner", 7.8, 7.5,
                                   max(1.0, PAD_STEM_LENGTH_MM - 2.0),
                                   (0.0, -PAD_STEM_CENTER_Z_MM, PAD_CENTER_FROM_TILT_Z),
                                   "Pad_Body", MATERIALS["GradientClamp"],
                                   axis=Vector((0.0, -1.0, 0.0)),
                                   bevel=0.0, segments=64)
    rear_barrel = add_tube_mesh("Pad_Rear_Pivot_Barrel", 13.0, 10.3,
                                PART_B_LENGTH_MM, (0.0, axle_body_y, TILT_AXIS_Z),
                                "Pad_Body", MATERIALS["Aluminum"],
                                axis=Vector((1.0, 0.0, 0.0)), bevel=0.5)
    rear_barrel["Part"] = "Lower housing barrel for Part B axle"

    # Small logo plaque sits on the crowned top, clear of the central stem.
    logo_x = -PAD_LENGTH_MM * 0.34
    logo_surface_z = (PAD_CENTER_FROM_TILT_Z + PAD_THICKNESS_MM * 0.5
                      - PAD_CROWN_HEIGHT_MM * (logo_x / (PAD_LENGTH_MM * 0.5)) ** 2)
    badge = bevelled_box("Pad_Embossed_Logo_Plate", (48.0, 18.0, 1.0),
                         (logo_x, 0.0, logo_surface_z + 0.5),
                         MATERIALS["Aluminum"], "Pad_Body", bevel=0.48)
    logo = add_text("Pad_Logo_RP", "RP", 9.0,
                    (logo_x, 0.0, logo_surface_z + 1.06),
                    MATERIALS["Label"], "Pad_Body", align_x="CENTER")
    logo.data.extrude = 0.15
    logo.data.bevel_depth = 0.08

    # A small lower-front plaque faces the shopper on the upright cushion.
    side_label_y = PAD_WIDTH_MM * 0.31
    side_surface_z = (PAD_CENTER_FROM_TILT_Z + PAD_THICKNESS_MM * 0.5
                      - PAD_CROWN_HEIGHT_MM * (side_label_y / (PAD_WIDTH_MM * 0.5)) ** 2)
    side_badge = bevelled_box("Pad_Side_Text_Strip", (80.0, 12.0, 1.0),
                              (0.0, side_label_y, side_surface_z + 0.5),
                              MATERIALS["Base"], "Pad_Body", bevel=0.45)
    side_text = add_text("Pad_Side_Text", "SWIVEL REST", 6.0,
                         (0.0, side_label_y, side_surface_z + 1.06),
                         MATERIALS["Sage"], "Pad_Body", align_x="CENTER")

    # Register construction objects for hierarchical parenting in rig().
    return {"body": body, "receiver": receiver, "receiver_liner": receiver_liner,
            "rear_barrel": rear_barrel, "badge": badge, "logo": logo,
            "side_badge": side_badge, "side_text": side_text}


def make_baseplate() -> dict[str, bpy.types.Object]:
    """Create the rounded removable plate with an axle channel and latch window."""
    length = PAD_LENGTH_MM - 8.0
    width = PAD_WIDTH_MM - 6.0
    half_length, half_width = length * 0.5, width * 0.5
    half_thickness = BASE_PLATE_THICKNESS_MM * 0.5
    steps = 96
    outline = [superellipse_point(math.tau * index / steps,
                                  half_length, half_width, exponent=5.0)
               for index in range(steps)]
    vertices = ([(x, y, -half_thickness) for x, y in outline]
                + [(x, y, half_thickness) for x, y in outline])
    faces = [tuple(reversed(range(steps))), tuple(range(steps, 2 * steps))]
    for index in range(steps):
        following = (index + 1) % steps
        faces.append((index, following, steps + following, steps + index))
    plate = mesh_object("Pad_Removable_BasePlate", vertices, faces,
                        "Pad_BasePlate", MATERIALS["Base"])
    plate.location = (0.0, 0.0, BASE_PLATE_CENTER_Z_MM)
    plate["Nominal size mm"] = f"{length:.0f} × {width:.0f} × {BASE_PLATE_THICKNESS_MM:.0f}"
    # The upright backplate has a long-axis channel for the Part B hinge axle.
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=13.5,
                                        depth=PART_B_LENGTH_MM + 12.0,
                                        location=(0.0, AXLE_PLATE_OFFSET_Y_MM, TILT_AXIS_Z),
                                        rotation=(0.0, math.pi / 2.0, 0.0))
    axle_channel = bpy.context.object
    axle_channel.name = "TEMP_BasePlate_PartB_Channel"
    boolean_difference(plate, axle_channel, "Part B barrel channel")
    # A narrow access opening lets the terracotta slider sit flush through the plate.
    bpy.ops.mesh.primitive_cube_add(size=1.0,
                                    location=(0.0, AXLE_PLATE_OFFSET_Y_MM + 32.0,
                                              BASE_PLATE_CENTER_Z_MM))
    slider_cutter = bpy.context.object
    slider_cutter.name = "TEMP_BasePlate_Slider_Window"
    slider_cutter.dimensions = (24.0, 18.0, 8.0)
    apply_scale(slider_cutter)
    boolean_difference(plate, slider_cutter, "Slider access window")
    add_bevel(plate, 0.5, 3, "Base-plate machined edge")
    add_weighted_normals(plate)
    plate["Part"] = "Removable pad base plate"
    plate["Central mount note"] = "Upright backplate with a long-axis Part B hinge channel and separate collar receiver"
    plate["Slider window mm"] = "24 × 18"
    return {"plate": plate}


# ── Latch, slider, spring, lever, and engagement pin ──────────────────────────
def make_helix(name: str, center, axis: str, radius: float, pitch: float,
               turns: float, wire_radius: float, material: bpy.types.Material,
               collection_name: str) -> bpy.types.Object:
    points = []
    count = max(48, int(turns * 32))
    length = turns * pitch
    for i in range(count + 1):
        t = i / count
        angle = turns * math.tau * t
        if axis == "X":
            point = (center[0] + length * (t - 0.5),
                     center[1] + radius * math.cos(angle),
                     center[2] + radius * math.sin(angle))
        elif axis == "Y":
            point = (center[0] + radius * math.cos(angle),
                     center[1] + length * (t - 0.5),
                     center[2] + radius * math.sin(angle))
        else:
            point = (center[0] + radius * math.cos(angle),
                     center[1] + radius * math.sin(angle),
                     center[2] + length * (t - 0.5))
        points.append(point)
    return add_curve(name, points, wire_radius, material, collection_name)


def make_latch() -> dict[str, bpy.types.Object]:
    """Build visible latch internals plus the slider-driven pin and glow marker."""
    slider_root = bpy.data.objects.new("Slider_Travel_Root", None)
    ensure_collection("Latch_Assembly").objects.link(slider_root)
    slider_root.empty_display_type = "PLAIN_AXES"
    slider_root.empty_display_size = 3.0
    slider_root.location = (0.0, 0.0, -9.0)
    remember(slider_root, "SliderRoot")

    slider = bevelled_box("Latch_Slider_Button_Terracotta", (13.0, 20.0, 4.0),
                          (-32.0, 0.0, 0.0), MATERIALS["Terracotta"],
                          "Latch_Assembly", bevel=1.5)
    parent_local(slider, slider_root)
    slider.location = (-32.0, 0.0, 0.0)
    slider["Travel mm"] = 6.0
    remember(slider, "SliderButton")

    lever_root = bpy.data.objects.new("Latch_Lever_Pivot_Rig", None)
    ensure_collection("Latch_Assembly").objects.link(lever_root)
    lever_root.empty_display_type = "CIRCLE"
    lever_root.empty_display_size = 3.0
    lever_root.location = (-38.0, 0.0, 6.0)
    remember(lever_root, "LeverRoot")

    lever = bevelled_box("Latch_Spring_Lever", (22.0, 4.0, 2.6),
                         (7.0, 0.0, 0.0), MATERIALS["Aluminum"],
                         "Latch_Assembly", bevel=0.8)
    parent_local(lever, lever_root)
    lever.location = (7.0, 0.0, 0.0)
    remember(lever, "LatchLever")

    pivot_pin = cylinder("Latch_Lever_Pivot_Pin", 2.2, 7.0,
                         (-38.0, 0.0, 6.0), MATERIALS["Aluminum"],
                         "Latch_Assembly", axis=Vector((0.0, 1.0, 0.0)), bevel=0.35)
    parent_local(pivot_pin, lever_root)
    pivot_pin.location = (0.0, 0.0, 0.0)

    # Pin is positioned at the Part B slot; it follows the driver-operated lever.
    pin = cylinder("Latch_Pin_Engaging_PartB_Slot", 2.0, 6.0,
                   (-31.0, 0.0, 8.2), MATERIALS["Terracotta"],
                   "Latch_Assembly", axis=Vector((0.0, 0.0, 1.0)), bevel=0.35)
    parent_local(pin, lever_root)
    pin.location = (0.0, 0.0, 2.2)
    remember(pin, "LatchPin")

    spring = make_helix("Latch_Return_Spring", (-38.0, 0.0, 3.2), "Y",
                        2.0, 1.6, 5.0, 0.38, MATERIALS["Aluminum"],
                        "Latch_Assembly")

    # Four corner bosses and flush fasteners are referenced from the enlarged plate.
    bolt_x = PAD_LENGTH_MM * 0.5 - 20.0
    bolt_y = PAD_WIDTH_MM * 0.5 - 20.0
    boss_center_z = BASE_PLATE_CENTER_Z_MM + BASE_PLATE_THICKNESS_MM * 0.5 + 3.0
    fastener_center_z = BASE_PLATE_CENTER_Z_MM - BASE_PLATE_THICKNESS_MM * 0.5 - 0.5
    bolt_positions = ((-bolt_x, -bolt_y), (bolt_x, -bolt_y),
                      (-bolt_x, bolt_y), (bolt_x, bolt_y))
    for i, (x, y) in enumerate(bolt_positions, 1):
        boss = cylinder(f"Pad_Base_Screw_Boss_{i}", 4.0, 6.0,
                        (x, y, boss_center_z), MATERIALS["MetalDark"],
                        "Latch_Assembly", axis=Vector((0.0, 0.0, 1.0)), bevel=0.6)
        head = cylinder(f"BasePlate_Fastener_{i}", 2.6, 1.0,
                        (x, y, fastener_center_z), MATERIALS["Aluminum"],
                        "Pad_BasePlate", axis=Vector((0.0, 0.0, 1.0)), bevel=0.35)

    # A hidden-by-default accent halo pulses during the latch click.
    bpy.ops.mesh.primitive_torus_add(major_radius=7.8, minor_radius=0.45,
                                     major_segments=48, minor_segments=10,
                                     location=(-32.0, 0.0, -11.2))
    pulse = bpy.context.object
    pulse.name = "Latch_Click_Pulse_Ring"
    link_object(pulse, "Latch_Assembly")
    set_material(pulse, MATERIALS["Pulse"])
    set_smooth(pulse)
    pulse.scale = (0.001, 0.001, 0.001)
    remember(pulse, "LatchPulse")

    return {"slider_root": slider_root, "slider": slider,
            "lever_root": lever_root, "lever": lever,
            "pin": pin, "spring": spring, "pulse": pulse}


# ── Rigs, hierarchy, constraints, and manual controls ─────────────────────────
def make_empty(name: str, collection_name: str, location=(0.0, 0.0, 0.0),
               display: str = "PLAIN_AXES", size: float = 8.0) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    ensure_collection(collection_name).objects.link(obj)
    obj.empty_display_type = display
    obj.empty_display_size = size
    obj.location = location
    return remember(obj)


def rig(cart_root: bpy.types.Object,
        handle: dict[str, object]) -> dict[str, bpy.types.Object]:
    """Create the handle-mounted rig with an upright, shopper-facing neutral cushion."""
    controller = make_empty("Assembly_Controller", "Rig", (0.0, 0.0, 0.0), "CUBE", 12.0)
    parent_local(controller, cart_root)
    controller.location = Vector(handle["center"])
    controller.rotation_mode = "QUATERNION"
    controller.rotation_quaternion = Vector((1.0, 0.0, 0.0)).rotation_difference(
        Vector(handle["axis"]).normalized())
    controller["Swivel"] = 0.0       # degrees; manually editable
    controller["Tilt"] = NEUTRAL_TILT_DEGREES  # neutral cushion rest pitch
    controller["Plate_Roll"] = 0.0   # degrees around the upright cushion's face normal
    controller["Explode"] = 0.0
    controller["PartB_Insertion"] = 0.0
    controller["BasePlate_Separation"] = 0.0
    controller["Collar_Insertion"] = 0.0
    for key, (low, high, description) in {
        "Swivel": (-45.0, 45.0, "Rest-pad lateral swivel about the handle mount; ±45 degrees"),
        "Tilt": (0.0, 90.0, "Forward lean of the upright cushion; neutral rest angle is 12°"),
        "Plate_Roll": (-45.0, 45.0, "Roll upright backing plate around the user-facing normal"),
        "Explode": (0.0, 1.0, "Manual exploded-state control"),
        "PartB_Insertion": (0.0, 1.0, "Part B axial exploded distance"),
        "BasePlate_Separation": (0.0, 1.0, "Base plate exploded distance"),
        "Collar_Insertion": (0.0, 1.0, "Part A collar insertion distance"),
    }.items():
        try:
            controller.id_properties_ui(key).update(min=low, max=high, description=description)
        except (AttributeError, TypeError):
            pass
    remember(controller, "Controller")

    part_a_root = make_empty("PartA_Root", "Rig", (0.0, 0.0, 0.0), "CIRCLE", 10.0)
    parent_local(part_a_root, controller)
    remember(part_a_root, "PartARoot")

    # Branch-stem Z is the swivel axis. It directly carries the tilt rig and pad.
    swivel = make_empty("Swivel_Axis", "Rig", (0.0, 0.0, BRANCH_TIP_Z), "CIRCLE", 10.0)
    parent_local(swivel, part_a_root)
    remember(swivel, "SwivelAxis")

    # Stand the baseplate in the customer-facing plane: local X follows the
    # handlebar, local Y is vertical, and local Z points toward the shopper.
    plate_axis = make_empty("Plate_Axis", "Rig",
                            (0.0, PAD_CENTER_Y, PLATE_AXIS_Z), "CIRCLE", 8.0)
    parent_local(plate_axis, swivel)
    plate_axis.rotation_euler.x = -math.pi / 2.0
    remember(plate_axis, "PlateAxis")

    # The hinge axle runs along the pad's long edge, parallel to the handlebar.
    tilt = make_empty("Tilt_Axis", "Rig",
                      (0.0, AXLE_PLATE_OFFSET_Y_MM, TILT_AXIS_Z), "CIRCLE", 8.0)
    parent_local(tilt, plate_axis)
    remember(tilt, "TiltAxis")

    # The cushion local X/Y/Z axes now map to horizontal/vertical/front-to-back.
    pad_frame = make_empty("Pad_Body_Frame", "Rig", (0.0, 0.0, 0.0),
                           "PLAIN_AXES", 4.0)
    parent_local(pad_frame, tilt)
    remember(pad_frame, "PadFrame")

    # The latch uses a local frame aligned to the Part B slot on the customer-facing side.
    latch_frame = make_empty("Latch_Assembly_Frame", "Rig", (0.0, 0.0, 0.0),
                             "PLAIN_AXES", 4.0)
    parent_local(latch_frame, pad_frame)
    latch_frame.rotation_euler.z = -math.pi / 2.0
    remember(latch_frame, "LatchFrame")

    # Extra roots make each component explode exactly along its own axis.
    axle_root = make_empty("PartB_Explode_Root", "Rig",
                           (0.0, AXLE_PLATE_OFFSET_Y_MM, TILT_AXIS_Z), "PLAIN_AXES", 4.0)
    parent_local(axle_root, plate_axis)
    remember(axle_root, "AxleRoot")

    base_root = make_empty("BasePlate_Explode_Root", "Rig",
                           (0.0, 0.0, 0.0), "PLAIN_AXES", 4.0)
    parent_local(base_root, plate_axis)
    remember(base_root, "BaseRoot")

    # Parent Part A components to its common root.
    for key in ("ClampShell", "PartA_T_Branch_Tube", "PartA_Ribbed_Window_Collar",
                "PartA_Bore_Gradient_Liner"):
        obj = OBJECTS.get(key)
        if obj is not None:
            parent_local(obj, part_a_root)
    for name in list(OBJECTS):
        if name.startswith("PartA_Collar_Rib_"):
            parent_local(OBJECTS[name], part_a_root)

    # Part B axle and gradient strip follow the removable plate/roll axis.
    axle = OBJECTS["PartB_Pivot_Axle_Ø18x100"]
    parent_local(axle, axle_root)
    axle.location = (0.0, 0.0, 0.0)
    # Local +Z follows Plate_Axis +X, i.e. the handlebar-parallel hinge axle.
    set_axis(axle, Vector((1.0, 0.0, 0.0)))
    parent_local(OBJECTS["PartB_Gradient_Side_Strip"], axle)
    OBJECTS["PartB_Gradient_Side_Strip"].location = (PART_B_DIAMETER_MM * 0.5 - 0.85, 0.0, -18.0)
    rear_barrel = OBJECTS["Pad_Rear_Pivot_Barrel"]
    parent_local(rear_barrel, plate_axis)
    set_axis(rear_barrel, Vector((1.0, 0.0, 0.0)))
    rear_barrel.location = (0.0, AXLE_PLATE_OFFSET_Y_MM, TILT_AXIS_Z)

    # The pad shell and its stem socket tilt about Part B; base plate and axle do not.
    body_objs = ("PadBody", "Pad_Stem_Receiver_Barrel", "Pad_Receiver_Gradient_Liner",
                 "Pad_Embossed_Logo_Plate", "Pad_Logo_RP", "Pad_Side_Text_Strip",
                 "Pad_Side_Text")
    for key in body_objs:
        obj = OBJECTS.get(key)
        if obj is not None:
            parent_local(obj, pad_frame)
    OBJECTS["PadBody"].location = (0.0, PAD_CENTER_Y - TILT_AXIS_OFFSET_Y_MM,
                                    PAD_CENTER_FROM_TILT_Z)
    receiver_center_y = -PAD_STEM_CENTER_Z_MM
    receiver_center_z = PAD_CENTER_FROM_TILT_Z
    OBJECTS["Pad_Stem_Receiver_Barrel"].location = (0.0, receiver_center_y,
                                                     receiver_center_z)
    OBJECTS["Pad_Receiver_Gradient_Liner"].location = (0.0, receiver_center_y,
                                                       receiver_center_z)
    logo_x_local = -PAD_LENGTH_MM * 0.34
    logo_surface_z = (PAD_CENTER_FROM_TILT_Z + PAD_THICKNESS_MM * 0.5
                      - PAD_CROWN_HEIGHT_MM * (logo_x_local / (PAD_LENGTH_MM * 0.5)) ** 2)
    OBJECTS["Pad_Embossed_Logo_Plate"].location = (logo_x_local, 0.0,
                                                   logo_surface_z + 0.5)
    OBJECTS["Pad_Logo_RP"].location = (logo_x_local, 0.0,
                                      logo_surface_z + 1.06)
    side_label_y = PAD_WIDTH_MM * 0.31
    side_surface_z = (PAD_CENTER_FROM_TILT_Z + PAD_THICKNESS_MM * 0.5
                      - PAD_CROWN_HEIGHT_MM * (side_label_y / (PAD_WIDTH_MM * 0.5)) ** 2)
    OBJECTS["Pad_Side_Text_Strip"].location = (0.0, side_label_y,
                                                side_surface_z + 0.5)
    OBJECTS["Pad_Side_Text"].location = (0.0, side_label_y,
                                         side_surface_z + 1.06)

    plate = OBJECTS["Pad_Removable_BasePlate"]
    parent_local(plate, base_root)
    plate.location = (0.0, 0.0, BASE_PLATE_CENTER_Z_MM)
    # Keep the upright center intact aside from the hinge channel and slider access window.
    for name, obj in list(OBJECTS.items()):
        if name.startswith("BasePlate_Fastener_"):
            parent_local(obj, base_root)
            # Keep screw heads flush against the back of the upright plate.
            obj.location.z = BASE_PLATE_CENTER_Z_MM - BASE_PLATE_THICKNESS_MM * 0.5 - 0.5

    # Latch internals stay on the moving pad frame; the lever retains its driven pivot hierarchy.
    for key in ("SliderRoot", "Latch_Return_Spring", "LatchPulse"):
        obj = OBJECTS.get(key)
        if obj is not None:
            parent_local(obj, latch_frame)
    slider_root = OBJECTS["SliderRoot"]
    slider_root.location = (0.0, 0.0, -9.0)
    OBJECTS["SliderButton"].location = (-32.0, 0.0, 0.0)
    lever_root = OBJECTS["LeverRoot"]
    parent_local(lever_root, latch_frame)
    lever_root.location = (-38.0, 0.0, 6.0)
    OBJECTS["LatchLever"].location = (7.0, 0.0, 0.0)
    OBJECTS["Latch_Lever_Pivot_Pin"].location = (0.0, 0.0, 0.0)
    OBJECTS["LatchPin"].location = (0.0, 0.0, 3.0)
    # Helix spline points already carry their local center coordinates.
    OBJECTS["Latch_Return_Spring"].location = (0.0, 0.0, 0.0)
    pulse = OBJECTS["LatchPulse"]
    pulse.location = (-32.0, 0.0, -11.2)
    for key in ("Pad_Base_Screw_Boss_1", "Pad_Base_Screw_Boss_2",
                "Pad_Base_Screw_Boss_3", "Pad_Base_Screw_Boss_4"):
        if key in OBJECTS:
            parent_local(OBJECTS[key], plate_axis)

    # Simple animation-friendly internal coordinate axes and controller drivers.
    add_property_driver(swivel, "rotation_euler", 2, controller, "Swivel",
                        "value * 0.017453292519943295")
    add_property_driver(tilt, "rotation_euler", 0, controller, "Tilt",
                        "value * 0.017453292519943295")
    add_property_driver(plate_axis, "rotation_euler", 1, controller, "Plate_Roll",
                        "value * 0.017453292519943295")
    add_property_driver(part_a_root, "location", 2, controller, "Explode", "40.0 * value")
    add_multi_property_driver(axle_root, "location", 0, controller,
                              {"explode": "Explode", "insert": "PartB_Insertion"},
                              "18.0 * explode + 42.0 * insert")
    add_multi_property_driver(base_root, "location", 2, controller,
                              {"explode": "Explode", "separate": "BasePlate_Separation"},
                              "-14.0 * explode - 24.0 * separate")
    add_multi_property_driver(swivel, "location", 2, controller,
                              {"explode": "Explode", "insert": "Collar_Insertion"},
                              f"{BRANCH_TIP_Z:.6f} + 20.0 * explode + 38.0 * insert")

    limit = tilt.constraints.new("LIMIT_ROTATION")
    limit.name = "Mechanical tilt range · 0–90°"
    limit.use_limit_x = True
    limit.min_x = 0.0
    limit.max_x = math.radians(90.0)
    limit.owner_space = "LOCAL"
    if hasattr(limit, "use_transform_limit"):
        limit.use_transform_limit = True

    lever_root.rotation_mode = "XYZ"
    lever_driver = lever_root.driver_add("rotation_euler", 1)
    driver = lever_driver.driver
    driver.type = "SCRIPTED"
    variable = driver.variables.new()
    variable.name = "slider_x"
    variable.type = "TRANSFORMS"
    variable.targets[0].id = slider_root
    variable.targets[0].transform_type = "LOC_X"
    variable.targets[0].transform_space = "LOCAL_SPACE"
    driver.expression = "-0.20943951023931953 * min(max(slider_x / 6.0, 0.0), 1.0)"

    return {"controller": controller, "part_a_root": part_a_root,
            "swivel": swivel, "plate_axis": plate_axis,
            "tilt": tilt, "pad_frame": pad_frame, "latch_frame": latch_frame,
            "axle_root": axle_root, "base_root": base_root,
            "lever_root": lever_root, "slider_root": slider_root}


# ── Grocery-aisle camera, lighting, and softbox setup ────────────────────────
def aim_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_area_light(name: str, location, target, energy: float, size: float,
                   color, collection_name: str = "Stage") -> bpy.types.Object:
    data = bpy.data.lights.new(name + "_Data", "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color[:3]
    obj = bpy.data.objects.new(name, data)
    ensure_collection(collection_name).objects.link(obj)
    obj.location = location
    aim_at(obj, Vector(target))
    remember(obj)
    return obj


def add_camera_background_plate(camera: bpy.types.Object) -> bpy.types.Object:
    """Add a packed, camera-following grocery-aisle photo as a soft background plate."""
    if not GROCERY_BACKGROUND_IMAGE.is_file():
        raise FileNotFoundError(f"Grocery background image not found: {GROCERY_BACKGROUND_IMAGE}")
    image = bpy.data.images.load(str(GROCERY_BACKGROUND_IMAGE), check_existing=True)
    if not getattr(image, "packed_file", None):
        image.pack()
    aspect = 16.0 / 9.0
    image_aspect = image.size[0] / image.size[1]
    distance = 5000.0
    width = distance * camera.data.sensor_width / camera.data.lens * 1.08
    height = width / aspect
    if image_aspect > aspect:
        horizontal_crop = 0.5 * (1.0 - aspect / image_aspect)
        uv_left, uv_right = horizontal_crop, 1.0 - horizontal_crop
        uv_bottom, uv_top = 0.0, 1.0
    else:
        vertical_crop = 0.5 * (1.0 - image_aspect / aspect)
        uv_left, uv_right = 0.0, 1.0
        uv_bottom, uv_top = vertical_crop, 1.0 - vertical_crop
    mesh = bpy.data.meshes.new("Grocery_Aisle_Backplate_Mesh")
    mesh.from_pydata(((-width * 0.5, -height * 0.5, 0.0),
                      ( width * 0.5, -height * 0.5, 0.0),
                      ( width * 0.5,  height * 0.5, 0.0),
                      (-width * 0.5,  height * 0.5, 0.0)), [], ((0, 1, 2, 3),))
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="Aisle_Image_UV")
    for loop_index, uv in zip(mesh.polygons[0].loop_indices,
                              ((uv_left, uv_bottom), (uv_right, uv_bottom),
                               (uv_right, uv_top), (uv_left, uv_top))):
        uv_layer.data[loop_index].uv = uv

    material = bpy.data.materials.new("Photographic grocery aisle · camera only")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    links = material.node_tree.links
    output = nodes.new("ShaderNodeOutputMaterial")
    texcoord = nodes.new("ShaderNodeTexCoord")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Linear"
    texture.extension = "EXTEND"
    links.new(texcoord.outputs["UV"], texture.inputs["Vector"])
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Strength"].default_value = 0.90
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    light_path = nodes.new("ShaderNodeLightPath")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(light_path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], output.inputs["Surface"])

    plate = bpy.data.objects.new("Grocery_Aisle_Camera_Backplate", mesh)
    ensure_collection("Stage").objects.link(plate)
    mesh.materials.append(material)
    plate.parent = camera
    plate.matrix_parent_inverse = Matrix.Identity(4)
    plate.location = (0.0, 0.0, -distance)
    plate.hide_select = True
    if hasattr(plate, "visible_shadow"):
        plate.visible_shadow = False
    plate["Role"] = "Packed grocery aisle photo plate; follows camera and defocuses behind the product"
    remember(plate, "BackgroundPlate")
    return plate


def add_cart_contact_shadow(cart_root: bpy.types.Object) -> bpy.types.Object:
    """Overlay a subtle soft floor shadow so the cart sits naturally on the aisle photo."""
    width, depth = 1500.0, 900.0
    mesh = bpy.data.meshes.new("Cart_Contact_Shadow_Mesh")
    mesh.from_pydata(((-width * 0.5, -depth * 0.5, 0.0),
                      ( width * 0.5, -depth * 0.5, 0.0),
                      ( width * 0.5,  depth * 0.5, 0.0),
                      (-width * 0.5,  depth * 0.5, 0.0)), [], ((0, 1, 2, 3),))
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="Shadow_Falloff_UV")
    for loop_index, uv in zip(mesh.polygons[0].loop_indices,
                              ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
        uv_layer.data[loop_index].uv = uv

    material = bpy.data.materials.new("Soft contact shadow · camera composite")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    links = material.node_tree.links
    output = nodes.new("ShaderNodeOutputMaterial")
    texcoord = nodes.new("ShaderNodeTexCoord")
    distance = nodes.new("ShaderNodeVectorMath")
    distance.operation = "DISTANCE"
    distance.inputs[1].default_value = (0.5, 0.5, 0.0)
    links.new(texcoord.outputs["UV"], distance.inputs[0])
    falloff = nodes.new("ShaderNodeMapRange")
    falloff.clamp = True
    falloff.interpolation_type = "SMOOTHERSTEP"
    falloff.inputs["From Min"].default_value = 0.0
    falloff.inputs["From Max"].default_value = 0.5
    falloff.inputs["To Min"].default_value = 0.26
    falloff.inputs["To Max"].default_value = 0.0
    links.new(distance.outputs["Value"], falloff.inputs["Value"])

    transparent = nodes.new("ShaderNodeBsdfTransparent")
    shadow_tint = scale_rgba(LINEAR_PALETTE["BODY"], 0.48)
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = shadow_tint
    emission.inputs["Strength"].default_value = 1.0
    shadow_mix = nodes.new("ShaderNodeMixShader")
    links.new(falloff.outputs["Result"], shadow_mix.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], shadow_mix.inputs[1])
    links.new(emission.outputs["Emission"], shadow_mix.inputs[2])
    light_path = nodes.new("ShaderNodeLightPath")
    camera_mix = nodes.new("ShaderNodeMixShader")
    links.new(light_path.outputs["Is Camera Ray"], camera_mix.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], camera_mix.inputs[1])
    links.new(shadow_mix.outputs["Shader"], camera_mix.inputs[2])
    links.new(camera_mix.outputs["Shader"], output.inputs["Surface"])

    shadow = bpy.data.objects.new("Cart_Contact_Shadow", mesh)
    ensure_collection("Cart_Context").objects.link(shadow)
    mesh.materials.append(material)
    shadow.parent = cart_root
    shadow.matrix_parent_inverse = Matrix.Identity(4)
    shadow.location = (0.0, 0.0, -4.0)
    shadow.hide_select = True
    shadow["Role"] = "Subtle camera-only soft shadow over the grocery floor photo"
    remember(shadow, "CartShadow")
    return shadow


def setup_camera_lights(handle_center_mm) -> dict[str, bpy.types.Object]:
    """Set a product camera with close-up and wide cart-context views."""
    scene = bpy.context.scene
    hx, hy, hz = Vector(handle_center_mm)
    # Lift the product-camera target so the hero views center on the cart-mounted attachment.
    product_focus = (hx, hy, hz + 150.0)
    camera_data = bpy.data.cameras.new("Studio_35mm_Camera_Data")
    camera_data.lens = 35.0
    camera_data.sensor_width = 36.0
    camera_data.clip_start = 1.0
    camera_data.clip_end = 6000.0
    camera_data.dof.use_dof = True
    camera_data.dof.aperture_fstop = 5.6
    camera = bpy.data.objects.new("Studio_35mm_Camera", camera_data)
    ensure_collection("Stage").objects.link(camera)
    target = Vector(product_focus)
    camera.location = (hx + 1500.0, hy - 1500.0, hz + 300.0)
    aim_at(camera, target)
    scene.camera = camera
    remember(camera, "Camera")

    focus = make_empty("Camera_Focus_Target", "Stage", product_focus, "SPHERE", 3.0)
    camera_data.dof.focus_object = focus
    remember(focus, "FocusTarget")

    warm = LINEAR_PALETTE["BACKDROP"]
    cool = mix_rgba(LINEAR_PALETTE["SAGE"], LINEAR_PALETTE["BACKDROP"], 0.55)
    # Four large sources create a bright product key, gentle shadow fill, a clean
    # edge rim, and soft overhead ambience without flattening the dark attachment.
    add_area_light("Softbox_Key_Warm", (850.0, -1350.0, 2050.0), product_focus,
                   9000.0, 1250.0, warm)
    add_area_light("Softbox_Fill_Sage", (-1350.0, -350.0, 1450.0), product_focus,
                   4200.0, 1450.0, cool)
    add_area_light("Softbox_Rim_Warm", (250.0, 1450.0, 1900.0), product_focus,
                   10500.0, 1050.0, warm)
    add_area_light("Store_Ceiling_Softbox", (hx - 100.0, hy + 150.0, hz + 2350.0),
                   product_focus, 6000.0, 1900.0, warm)

    # A restrained world fill lifts shadow detail while the real camera backplate
    # carries the grocery-store context in final renders.
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld")
    background = nodes.new("ShaderNodeBackground")
    background.inputs["Color"].default_value = mix_rgba(LINEAR_PALETTE["BACKDROP"],
                                                        LINEAR_PALETTE["SAGE"], 0.32)
    background.inputs["Strength"].default_value = 0.72
    world.node_tree.links.new(background.outputs["Background"], output.inputs["Surface"])

    # Open on a wide cart-context view, then move into measured-handle close-ups
    # for clamp, swivel, and latch detail.
    camera_poses = (
        (1,   product_focus, -50.0, 1500.0, 20.0),
        (24,  (-170.0, 0.0, 850.0), -58.0, 3600.0, 17.0),
        (48,  (hx - 120.0, hy, hz - 260.0), -52.0, 1750.0, 18.0),
        (96,  product_focus, -55.0, 1500.0, 21.0),
        (144, product_focus, -52.0, 1650.0, 22.0),
        (168, product_focus, -50.0, 1850.0, 22.0),
        (192, product_focus, -50.0, 1850.0, 22.0),
        (216, product_focus, -48.0, 1900.0, 23.0),
        (240, product_focus, -48.0, 1900.0, 23.0),
        (258, product_focus, -45.0, 1750.0, 22.0),
        (276, product_focus, -45.0, 1750.0, 22.0),
        (312, product_focus, -48.0, 1900.0, 22.0),
    )
    for frame, target_xyz, azimuth, distance, elevation in camera_poses:
        camera_target = Vector(target_xyz)
        az = math.radians(azimuth)
        el = math.radians(elevation)
        horizontal = distance * math.cos(el)
        camera.location = (camera_target.x + horizontal * math.cos(az),
                           camera_target.y + horizontal * math.sin(az),
                           camera_target.z + distance * math.sin(el))
        aim_at(camera, camera_target)
        focus.location = camera_target
        key_object(camera, "location", frame)
        key_object(camera, "rotation_euler", frame)
        key_object(focus, "location", frame)
    tune_action(camera)
    tune_action(focus)
    background_plate = add_camera_background_plate(camera)
    return {"camera": camera, "focus": focus,
            "background_plate": background_plate}


# ── Curved motion arrows and camera-facing callout panels ─────────────────────
def arc_arrow(name: str, center, radius: float, plane: str,
              material: bpy.types.Material, collection_name: str,
              parent: bpy.types.Object | None = None) -> bpy.types.Object:
    points = []
    start, end = math.radians(-55.0), math.radians(55.0)
    steps = 48
    for i in range(steps + 1):
        t = start + (end - start) * i / steps
        if plane == "XY":
            p = (center[0] + radius * math.cos(t), center[1] + radius * math.sin(t), center[2])
        elif plane == "YZ":
            p = (center[0], center[1] + radius * math.cos(t), center[2] + radius * math.sin(t))
        else:
            p = (center[0] + radius * math.cos(t), center[1], center[2] + radius * math.sin(t))
        points.append(p)
    curve = add_curve(name + "_Arc", points, 0.85, material, collection_name)
    t = end
    tip = Vector(points[-1])
    if plane == "XY":
        tangent = Vector((-math.sin(t), math.cos(t), 0.0))
        normal = Vector((0.0, 0.0, 1.0))
    elif plane == "YZ":
        tangent = Vector((0.0, -math.sin(t), math.cos(t)))
        normal = Vector((1.0, 0.0, 0.0))
    else:
        tangent = Vector((-math.sin(t), 0.0, math.cos(t)))
        normal = Vector((0.0, 1.0, 0.0))
    back = -tangent * 8.0
    side = normal.cross(tangent).normalized() * 4.0
    head = add_curve(name + "_Arrowhead", (tip + back + side, tip, tip + back - side),
                     0.9, material, collection_name)
    root = make_empty(name + "_Rig", collection_name, (0.0, 0.0, 0.0), "PLAIN_AXES", 3.0)
    for obj in (curve, head):
        parent_local(obj, root)
        obj.location = (0.0, 0.0, 0.0)
    if parent is not None:
        parent_local(root, parent)
    root.scale = (0.001, 0.001, 0.001)
    return root


def make_hathed_panel(name: str, center_x: float, center_y: float,
                      z: float, camera: bpy.types.Object) -> list[bpy.types.Object]:
    # Camera-local 2D panel with light sage tint and fine diagonal sage hatching.
    width, height = 112.0, 30.0
    verts = [(-width/2, -height/2, 0), (width/2, -height/2, 0),
             (width/2, height/2, 0), (-width/2, height/2, 0)]
    panel = mesh_object(name + "_Panel", verts, [(0, 1, 2, 3)],
                        "Arrows_Labels", MATERIALS["SagePanel"])
    parent_local(panel, camera)
    panel.location = (center_x, center_y, z)
    panel["Opacity intent"] = 0.25
    created = [panel]
    # Diagonal hatch strokes are clipped approximately to the panel bounds.
    for i in range(-4, 5):
        x0 = center_x - width * 0.5 + i * 14.0
        x1 = x0 + 22.0
        y0 = center_y - height * 0.5
        y1 = center_y + height * 0.5
        if x0 < center_x - width * 0.5:
            y0 += (center_x - width * 0.5 - x0)
            x0 = center_x - width * 0.5
        if x1 > center_x + width * 0.5:
            y1 -= (x1 - (center_x + width * 0.5))
            x1 = center_x + width * 0.5
        if y0 < y1 and x0 < x1:
            hatch = add_curve(name + f"_Hatch_{i+5}",
                              ((x0, y0, z + 0.4), (x1, y1, z + 0.4)),
                              0.35, MATERIALS["Sage"], "Arrows_Labels")
            parent_local(hatch, camera)
            hatch.location = (0.0, 0.0, 0.0)
            # Curve points were created in camera-local coordinates, then are
            # parented with an identity inverse, so keep object origin at zero.
            created.append(hatch)
    for obj in created:
        obj.scale = (0.001, 0.001, 0.001)
    return created


def make_arrows_labels(camera: bpy.types.Object) -> dict[str, object]:
    """Add animated sage/terracotta arrows and final-stage PART A / PART B cards."""
    swivel = OBJECTS["SwivelAxis"]
    tilt = OBJECTS["TiltAxis"]
    swivel_arrow = arc_arrow("Swivel_Arrow_Terracotta", (0.0, 0.0, 4.0), 38.0,
                             "XY", MATERIALS["Terracotta"], "Arrows_Labels", swivel)
    tilt_arrow = arc_arrow("Tilt_Arrow_Sage", (0.0, 0.0, 0.0), 34.0,
                           "YZ", MATERIALS["Sage"], "Arrows_Labels", tilt)
    labels = []
    panels = []
    for name, x, text in (("PART_A", -128.0, "PART A"),
                          ("PART_B", 16.0, "PART B")):
        y = 84.0
        z = -610.0
        panel_objects = make_hathed_panel(name, x + 52.0, y, z, camera)
        panels.extend(panel_objects)
        label = add_text(name + "_Label", text, 9.0,
                         (x, y, z - 0.2), MATERIALS["Label"],
                         "Arrows_Labels", align_x="LEFT")
        parent_local(label, camera)
        label.location = (x, y, z - 0.2)
        labels.append(label)
    # Hairline leaders from each label card toward the product in camera space.
    leader_a = add_curve("PART_A_Callout_Leader",
                         ((-76.0, 68.0, -609.0), (-54.0, 52.0, -609.0), (-20.0, 28.0, -609.0)),
                         0.45, MATERIALS["Label"], "Arrows_Labels")
    leader_b = add_curve("PART_B_Callout_Leader",
                         ((74.0, 68.0, -609.0), (55.0, 49.0, -609.0), (22.0, 25.0, -609.0)),
                         0.45, MATERIALS["Label"], "Arrows_Labels")
    for leader in (leader_a, leader_b):
        parent_local(leader, camera)
        leader.location = (0.0, 0.0, 0.0)
    # Label/card items start hidden and scale in during the final hero hold.
    card_objs = panels + labels + [leader_a, leader_b]
    for obj in card_objs:
        obj.scale = (0.001, 0.001, 0.001)
    return {"swivel_arrow": swivel_arrow, "tilt_arrow": tilt_arrow,
            "cards": card_objs, "labels": labels}


# ── Timeline: explode, assemble, clamp, swivel, tilt, latch, hero hold ─────────
def key_scale(obj: bpy.types.Object, frame: int, value: float) -> None:
    obj.scale = (value, value, value)
    key_object(obj, "scale", frame)


def animate(rig_objects: dict[str, bpy.types.Object],
            arrow_objects: dict[str, object]) -> None:
    scene = bpy.context.scene
    controller = rig_objects["controller"]
    part_a_root = rig_objects["part_a_root"]
    slider_root = rig_objects["slider_root"]
    pulse = arrow_objects.get("latch_pulse", OBJECTS.get("LatchPulse"))

    for name, (start, end) in TIMING.items():
        scene.timeline_markers.new(name.title().replace("_", " "), frame=start)
    scene.timeline_markers.new("Rest-pad side swivel", frame=TIMING["SWIVEL"][0])
    scene.timeline_markers.new("Hero end", frame=FRAME_END)

    # The cart stays fixed as a reference. The attachment below the central clamp
    # pivots; controller properties also stage the exploded view.
    property_tracks = {
        "Explode": ((1, 0.0), (24, 0.0), (34, 0.8), (40, 1.0),
                    (52, 0.35), (64, 0.0), (96, 0.0), (312, 0.0)),
        "PartB_Insertion": ((1, 0.0), (24, 0.0), (34, 1.0), (42, 0.65),
                            (52, 0.15), (58, 0.0), (312, 0.0)),
        "BasePlate_Separation": ((1, 0.0), (24, 0.0), (36, 1.0),
                                 (48, 0.45), (60, 0.0), (312, 0.0)),
        "Collar_Insertion": ((1, 0.0), (24, 0.0), (40, 1.0), (56, 0.6),
                             (72, 0.0), (96, 0.0), (312, 0.0)),
        "Swivel": ((1, 0.0), (144, 0.0)),
        "Tilt": ((1, NEUTRAL_TILT_DEGREES), (192, NEUTRAL_TILT_DEGREES)),
        "Plate_Roll": ((1, 0.0), (312, 0.0)),
    }
    for prop, keys in property_tracks.items():
        for frame, value in keys:
            key_property(controller, prop, frame, value)

    # Start with Part A mounted below the handle; the clamp-snap stage briefly
    # pulls it clear, flexes the lips, and seats it without an initial misalignment.
    part_a_root.location.y = 0.0
    key_component(part_a_root, "location", 1, 1)
    key_component(part_a_root, "location", 1, 96)
    part_a_root.location.y = 32.0
    key_component(part_a_root, "location", 1, 104)
    part_a_root.location.y = 8.0
    key_component(part_a_root, "location", 1, 110)
    part_a_root.location.y = -1.0
    key_component(part_a_root, "location", 1, 114)
    part_a_root.location.y = 0.0
    key_component(part_a_root, "location", 1, 120)
    key_component(part_a_root, "location", 1, FRAME_END)

    # The lips open 1.5 mm each for snap-on, then settle back. A separate
    # bore-clearance key keeps the assumed Ø25 mm bar from intersecting the
    # nominal Ø22 mm bore (OD28 / wall3 would otherwise be geometrically impossible).
    clamp = OBJECTS["ClampShell"]
    keys = clamp.data.shape_keys.key_blocks
    flex = keys.get("Snap_Flex_1p5mm_per_lip")
    bore = keys.get("Bore_Clearance_for_assumed_Ø25")
    for frame, value in ((1, 0.0), (108, 0.0), (114, 1.0),
                         (119, 0.5), (126, 0.0), (FRAME_END, 0.0)):
        flex.value = value
        flex.keyframe_insert(data_path="value", frame=frame)
    for frame, value in ((1, 0.0), (108, 0.0), (114, 1.0),
                         (119, 1.0), (126, 1.0), (FRAME_END, 1.0)):
        bore.value = value
        bore.keyframe_insert(data_path="value", frame=frame)

    # Keep the cushion at its neutral 12° forward lean. The attachment sweeps
    # around its central vertical mount, pausing at 15° detents to ±45°.
    swivel_keys = (
        (145, 0.0),
        (148, 15.0), (149, 15.0),
        (152, 30.0), (153, 30.0),
        (156, 45.0), (158, 45.0),
        (161, 30.0), (162, 30.0),
        (164, 15.0), (165, 15.0),
        (168, 0.0), (169, 0.0),
        (172, -15.0), (173, -15.0),
        (176, -30.0), (177, -30.0),
        (180, -45.0), (182, -45.0),
        (185, -30.0), (186, -30.0),
        (189, -15.0), (190, -15.0),
        (192, 0.0),
    )
    for frame, value in swivel_keys:
        key_property(controller, "Swivel", frame, value)

    # The neutral 12° rest angle demonstrates a modest forward-pitch range.
    # The controller keeps its 0–90° mechanical limit for manual adjustment.
    for frame, value in ((193, NEUTRAL_TILT_DEGREES), (204, 15.0), (216, 18.0),
                         (228, 15.0), (240, NEUTRAL_TILT_DEGREES),
                         (312, NEUTRAL_TILT_DEGREES)):
        key_property(controller, "Tilt", frame, value)
    for frame in (193, 240, 312):
        key_property(controller, "Plate_Roll", frame, 0.0)

    # Slider makes a 6 mm press; the lever rotation is driven 12° by SliderRoot X.
    for frame, value in ((241, 0.0), (248, 0.0), (250, 6.0),
                         (255, 6.0), (257, 0.0), (276, 0.0), (312, 0.0)):
        slider_root.location.x = value
        key_component(slider_root, "location", 0, frame)

    # Short latch demonstration: release to a 15° detent, then re-center and lock.
    for frame, value in ((241, 0.0), (249, 0.0), (251, 15.0),
                         (257, 15.0), (262, 0.0), (276, 0.0), (312, 0.0)):
        key_property(controller, "Swivel", frame, value)

    # Use Bezier easing throughout, except the slider's crisp spring-return click.
    tune_action(controller)
    tune_action(part_a_root)
    tune_action(slider_root)
    if slider_root.animation_data and slider_root.animation_data.action:
        try:
            for fc in slider_root.animation_data.action.fcurves:
                if fc.data_path == "location" and fc.array_index == 0:
                    for point in fc.keyframe_points:
                        point.interpolation = "CONSTANT"
        except AttributeError:
            pass
    if clamp.data.shape_keys.animation_data:
        try:
            for fc in clamp.data.shape_keys.animation_data.action.fcurves:
                for point in fc.keyframe_points:
                    point.interpolation = "BEZIER"
                    point.handle_left_type = "AUTO_CLAMPED"
                    point.handle_right_type = "AUTO_CLAMPED"
        except (AttributeError, TypeError):
            pass

    # Curved arrows are visible only during their matching motion stage.
    swivel_arrow = arrow_objects["swivel_arrow"]
    for frame, value in ((1, 0.001), (140, 0.001), (147, 1.0),
                         (188, 1.0), (196, 0.001), (312, 0.001)):
        key_scale(swivel_arrow, frame, value)
    tune_action(swivel_arrow)
    tilt_arrow = arrow_objects["tilt_arrow"]
    for frame, value in ((1, 0.001), (188, 0.001), (196, 1.0),
                         (236, 1.0), (244, 0.001), (312, 0.001)):
        key_scale(tilt_arrow, frame, value)
    tune_action(tilt_arrow)
    for frame, value in ((1, 0.001), (249, 0.001), (251, 1.0),
                         (258, 1.0), (264, 0.001), (312, 0.001)):
        key_scale(OBJECTS["LatchPulse"], frame, value)
    tune_action(OBJECTS["LatchPulse"])
    pulse_node = MATERIALS["Pulse"].node_tree.nodes["Pulse_Emission"]
    strength_socket = pulse_node.inputs["Strength"]
    for frame, strength in ((1, 0.0), (249, 0.0), (251, 1.4),
                            (257, 1.4), (260, 0.0), (312, 0.0)):
        strength_socket.default_value = strength
        strength_socket.keyframe_insert(data_path="default_value", frame=frame)
    if MATERIALS["Pulse"].node_tree.animation_data:
        try:
            for curve in MATERIALS["Pulse"].node_tree.animation_data.action.fcurves:
                for point in curve.keyframe_points:
                    point.interpolation = "BEZIER"
                    point.handle_left_type = "AUTO_CLAMPED"
                    point.handle_right_type = "AUTO_CLAMPED"
        except (AttributeError, TypeError):
            pass

    for obj in arrow_objects["cards"]:
        for frame, value in ((1, 0.001), (276, 0.001), (288, 1.0), (312, 1.0)):
            key_scale(obj, frame, value)
        tune_action(obj)

    # Camera focus and view framing are keyed above; the cart stays stationary.
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
    scene.frame_set(FRAME_START)
    print("Animation stages:")
    for name, (start, end) in TIMING.items():
        print(f"  {name.title():9s} {start:>3d}–{end:<3d}  ({(end-start+1)/FPS:.2f} s)")
    print(f"  Total: {FRAME_END - FRAME_START + 1} frames at {FPS} fps "
          f"({(FRAME_END - FRAME_START + 1)/FPS:.2f} s)")


# ── Render settings, file organization, and deterministic build ───────────────
def render_setup() -> None:
    """Configure Cycles, Eevee preview, AgX, 4K option, and H.264 output."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if PREVIEW_EEVEE else "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 128
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.render.resolution_x = 3840 if USE_4K else 1920
    scene.render.resolution_y = 2160 if USE_4K else 1080
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGB"
    try:
        # Blender 4.x builds with an enabled FFmpeg encoder accept this output.
        scene.render.image_settings.file_format = "FFMPEG"
    except (TypeError, ValueError):
        # Some embedded/headless bpy builds expose the enum but cannot activate
        # the encoder. Keep the script portable and record the full-build setup.
        scene.render.image_settings.file_format = "PNG"
        scene["FFmpeg availability"] = "Enable FFmpeg Video in a full Blender build; H.264/MPEG-4 is preselected below."
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.filepath = "//render/animation.mp4"
    scene.render.fps = FPS
    scene.view_settings.view_transform = "AgX"
    # A restrained higher-contrast AgX look keeps the cart wirework and pad edges legible.
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.render.use_file_extension = True
    scene["Preview Engine"] = "BLENDER_EEVEE_NEXT (set PREVIEW_EEVEE=True at the script top for a fast preview)"
    scene["RENDER flag"] = bool(RENDER)
    scene["Units"] = "Metric, scale length 0.001; model coordinates in millimeters"
    scene["Design Status"] = "Parametric visual concept; dimensions/fit/load safety not validated"


def configure_startup_view() -> None:
    """Open in the camera at frame 1 with materials visible, not a blank viewport."""
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            try:
                space.region_3d.view_perspective = "CAMERA"
                space.overlay.show_overlays = False
                space.shading.type = "MATERIAL"
                space.shading.use_scene_lights = True
                space.shading.use_scene_world = True
            except (AttributeError, TypeError, RuntimeError):
                continue


def clear_scene() -> None:
    # Remove startup objects and project collections without touching other files.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    # Purge unlinked construction data from a previous run so rerunning the
    # script from an existing file does not create duplicate .001 materials.
    for datablocks in (bpy.data.materials, bpy.data.meshes, bpy.data.curves,
                       bpy.data.cameras, bpy.data.lights, bpy.data.actions):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)
    COLLECTIONS.clear()
    OBJECTS.clear()
    MATERIALS.clear()


def organize_collections() -> None:
    for name in ("Cart_Context", "PartA_Clamp", "PartB_Axle", "Pad_Body", "Pad_BasePlate",
                 "Latch_Assembly", "Handlebar", "Rig", "Arrows_Labels", "Stage"):
        ensure_collection(name)


def main() -> None:
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.render.resolution_percentage = 100
    organize_collections()
    make_materials()
    cart_context = make_cart_context()
    add_cart_contact_shadow(cart_context["root"])

    clamp_parts = make_clamp()
    handlebar = make_handlebar()
    axle_parts = make_axle()
    pad_parts = make_pad()
    base_parts = make_baseplate()
    latch_parts = make_latch()
    rig_objects = rig(cart_context["root"], cart_context["handle"])
    parent_local(handlebar, rig_objects["controller"])
    handlebar.location = (0.0, 0.0, 0.0)
    stage = setup_camera_lights(cart_context["handle"]["center"])
    arrows = make_arrows_labels(stage["camera"])
    animate(rig_objects, arrows)
    render_setup()
    scene.frame_set(STARTUP_FRAME)
    configure_startup_view()

    # Product mesh transforms are applied; a small allowlist uses scale as the
    # intentionally animated reveal control requested for arrows, labels and pulse.
    animated_scale_prefixes = ("Swivel_Arrow_", "Tilt_Arrow_", "PART_A_", "PART_B_")
    intentional_scale_names = {"Latch_Click_Pulse_Ring", "Shopping_Cart_Context"}
    bad_scales = [obj.name for obj in bpy.data.objects
                  if obj.type not in {"CAMERA", "LIGHT", "EMPTY"}
                  and not obj.name.startswith(animated_scale_prefixes)
                  and obj.name not in intentional_scale_names
                  and any(abs(value - 1.0) > 1e-6 for value in obj.scale)]
    if bad_scales:
        print("Unexpected unapplied product scale (review):", bad_scales)
    else:
        print("Product mesh scales applied; animated graphic scales are intentional.")
    scene["Product"] = "Swivel Rest-Pad Cart Attachment"
    scene["Built with Blender"] = bpy.app.version_string
    source_handle = cart_context["handle"]
    scene["Handlebar prop"] = f"Ø{HANDLEBAR_DIAMETER_MM:.0f} × {HANDLEBAR_LENGTH_MM:.0f} mm; visual overlay"
    scene["Measured cart handle"] = (
        f"Ø{source_handle['diameter']:.1f} × {source_handle['length']:.1f} mm, "
        f"center {tuple(round(v, 1) for v in source_handle['center'])} mm")
    scene["Clamp fit note"] = (
        "OD28 / nominal 3 mm wall gives ID22; flex is modeled around the copied-cart "
        "handle geometry. Visual concept only; fit, tolerances, and loads are not validated.")
    scene["Part A"] = "One central snap C-clamp + downward 90° branch + windowed rib collar"
    scene["Part B"] = "Ø18 × 100 mm slotted pivot axle with latch pin"
    scene["Pad size"] = "280 × 160 × 35 mm visual scale target; not an engineering recommendation"
    scene["Intended use"] = "Cart-mounted cushioned leaning support; not a seat"
    scene["Cart context source"] = "Copied Shopping Cart mesh from blender/source/hcd mockup.blend; original untouched"
    scene["Cart motion"] = "Stationary context; no cart-root animation; attachment rig moves independently"
    scene["Rest-pad orientation"] = (
        "Neutral 12° forward-leaning cushion; ±45° swivel; "
        "12–18° pitch demonstration returns to 12°")
    scene["Scene context"] = (
        "Shopper figure omitted; product shown on the fixed cart in a grocery-aisle setting")
    scene["Startup frame"] = STARTUP_FRAME
    scene["Palette"] = "F2EFE9 cream · 3A4C40 forest · 8BA892 sage · C4694A terracotta"
    scene["Export note"] = "No animation render is started unless RENDER=True"

    # Save next to this script. The render path remains Blender-relative //render/animation.mp4.
    OUTPUT_BLEND.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))
    print(f"Saved animated Blender model: {OUTPUT_BLEND}")
    print(f"Ready at frame {STARTUP_FRAME} (product hero view). Press Spacebar to play; Render > Render Animation to export H.264.")
    print(f"Camera: 35 mm, {scene.render.resolution_x} × {scene.render.resolution_y}; "
          f"Cycles {scene.cycles.samples} samples; denoising enabled; render flag={RENDER}")
    if RENDER:
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
