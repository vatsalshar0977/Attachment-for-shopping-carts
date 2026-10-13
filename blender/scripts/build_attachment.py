#!/usr/bin/env python3
"""Build the HCD (Handle Comfort Device) attachment into the mockup .blend.

What it makes
-------------
A cushioned pad that snaps onto a shopping-cart handle bar so the user can lean
on it:

  HCD_Clip  - rigid C-channel (PP/PA) that grips the tube. Its lips sit in the
              pad's slot, and it sticks out at both ends so you can see the
              two-material construction.
  HCD_Pad   - soft TPE roll with a slot down the underside. The slot lets the
              whole thing be pressed onto the bar from below and spring back.

Everything is parametric: change the values in the PARAMS block and re-run.

Usage:
    LD_LIBRARY_PATH=$HOME/tools/bpy-stubs python3 scripts/build_attachment.py
"""

from __future__ import annotations

import math
import os
import sys

import bpy

# --------------------------------------------------------------------------- #
# PARAMS  (all lengths in metres unless the name says _MM)
# --------------------------------------------------------------------------- #

SRC_BLEND = "blender/source/hcd mockup.blend"
DST_BLEND = "blender/source/hcd mockup.blend"   # edited in place

# The cart in the source file is 4x oversized (1.03 x 0.53 x 1.11 m once fixed).
# Set to 1.0 to leave it exactly as it was.
CART_SCALE = 0.25

# --- handle bar (measured from the model; override to design for a different bar)
HANDLE_DIA_MM = 23.3          # measured: 23.3 mm tube
HANDLE_DETECT = True          # re-measure from the cart geometry instead
HANDLE_AXIS = "Y"             # bar runs along world Y

# --- rigid clip
CLIP_WALL_MM = 3.0
CLIP_BORE_CLEARANCE_MM = 0.4  # accommodate handle / print tolerances
CLIP_WRAP_DEG = 260.0         # how far the C wraps the tube
CLIP_LEN_MM = 320.0
CLIP_FLARE_MM = 3.0           # lead-in flare at the lips
CLIP_FLARE_DEG = 30.0
CLIP_BEVEL_MM = 1.0           # edge break on the extruded ends

# --- soft pad
PAD_LEN_MM = 300.0
PAD_OUTER_X_MM = 52.0         # semi-axis, depth
PAD_OUTER_Z_MM = 58.0         # semi-axis, height
PAD_OUTER_N = 3.0             # superellipse exponent: 2 = ellipse, higher = boxier
PAD_OFFSET_X_MM = -8.0        # shift the roll toward the user (-X)
PAD_OFFSET_Z_MM = 12.0        # shift the roll up, so more of it sits above the bar
PAD_SLOT_BORE_MM = 10.0       # half-width of the slot where it meets the bore
PAD_SLOT_OUTER_MM = 12.0      # half-width at the outside (lead-in)
PAD_BORE_CLEARANCE_MM = 0.4   # soft pad slips over the hard clip
PAD_BEVEL_MM = 5.0            # big soft rounding on the extruded ends

# --- look
PAD_COLOR = "#14366E"         # deep cobalt soft-touch TPE
CLIP_COLOR = "#9AA0A8"        # engineering grey
RIB_PITCH_MM = 9.0            # moulded rib pattern on the contact face
RIB_DEPTH = 0.35

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def mm(v: float) -> float:
    return v / 1000.0


def srgb_hex_to_linear(hex_str: str):
    h = hex_str.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out + [1.0]


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def superellipse_r(theta, a, b, n):
    """Radius of a superellipse |x/a|^n + |z/b|^n = 1 at angle `theta`."""
    ct, st = abs(math.cos(theta)), abs(math.sin(theta))
    return 1.0 / ((ct / a) ** n + (st / b) ** n) ** (1.0 / n)


# --------------------------------------------------------------------------- #
# geometry builders
# --------------------------------------------------------------------------- #


def ccw(pts):
    """Deduplicate and normalise a closed outline to positive signed area."""
    clean = []
    for point in pts:
        if not clean or math.hypot(point[0] - clean[-1][0], point[1] - clean[-1][1]) > 1e-9:
            clean.append(point)
    if len(clean) > 1 and math.hypot(clean[0][0] - clean[-1][0], clean[0][1] - clean[-1][1]) <= 1e-9:
        clean.pop()
    area = 0.0
    for i in range(len(clean)):
        x0, z0 = clean[i]
        x1, z1 = clean[(i + 1) % len(clean)]
        area += x0 * z1 - x1 * z0
    return clean if area >= 0 else clean[::-1]


def clip_profile(r_in, r_out, a0, a1, flare, flare_span, n=160):
    """Closed outline of a C-channel wrapping the tube, as (x, z) points."""
    pts = []
    span = a1 - a0

    def inner_r(a):
        # lead-in flare: the bore opens up over the last `flare_span` degrees
        f = smoothstep(0.0, flare_span, a1 - a) * smoothstep(0.0, flare_span, a - a0)
        return r_in + flare * (1.0 - f)

    # inner arc, tip -> tip
    for i in range(n + 1):
        a = a0 + span * i / n
        r = inner_r(a)
        pts.append((r * math.cos(a), r * math.sin(a)))
    # cap at a1
    ri, ro = inner_r(a1), r_out
    rc, rm = (ro - ri) / 2.0, (ro + ri) / 2.0
    for i in range(1, 24):
        a = a1 + math.pi * i / 24
        pts.append((rm * math.cos(a1) + rc * math.cos(a), rm * math.sin(a1) + rc * math.sin(a)))
    # outer arc back
    for i in range(n + 1):
        a = a1 - span * i / n
        pts.append((r_out * math.cos(a), r_out * math.sin(a)))
    # cap at a0
    ri = inner_r(a0)
    rc, rm = (r_out - ri) / 2.0, (r_out + ri) / 2.0
    for i in range(1, 24):
        a = a0 + math.pi * (1 + i / 24)
        pts.append((rm * math.cos(a0) + rc * math.cos(a), rm * math.sin(a0) + rc * math.sin(a)))
    return ccw(pts)


def pad_profile(r_bore, ax, az, n_exp, off_x, off_z,
                slot_bore, slot_outer, n=240):
    """Closed outline of the soft roll with a snap slot underneath.

    Built from four runs, in order:
      1. the bore arc (the long way round, so the slot is the only opening)
      2. down the -x slot wall to the outside
      3. around the outside -- over the top -- to the +x slot wall
      4. back up the +x slot wall
    """
    half = min(slot_bore, r_bore * 0.8)
    z_meet = -math.sqrt(max(r_bore ** 2 - half ** 2, 1e-12))

    def outer_pt(theta):
        r = superellipse_r(theta, ax, az, n_exp)
        return (off_x + r * math.cos(theta), off_z + r * math.sin(theta))

    def outer_x(theta):
        return outer_pt(theta)[0]

    def find_exit(t_lo, t_hi, target):
        """First angle in [t_lo, t_hi] where the outer x crosses `target`."""
        steps, prev = 3000, outer_x(t_lo)
        for i in range(1, steps + 1):
            t = t_lo + (t_hi - t_lo) * i / steps
            x = outer_x(t)
            if (prev - target) * (x - target) <= 0.0:
                return t
            prev = x
        return t_hi

    # where the slot walls break out through the outside of the roll
    t_left = find_exit(math.pi, 1.5 * math.pi, -slot_outer)     # lower-left
    t_right = find_exit(1.5 * math.pi, 2 * math.pi, slot_outer)  # lower-right

    pts = []
    # 1. bore, long way round: +x mouth -> over the top -> -x mouth
    a_start = math.atan2(z_meet, half)
    a_end = math.atan2(z_meet, -half)
    sweep = (a_end - a_start) % (2 * math.pi)
    for i in range(n + 1):
        a = a_start + sweep * i / n
        pts.append((r_bore * math.cos(a), r_bore * math.sin(a)))

    # 2. down the -x slot wall
    pts.append((-slot_outer, outer_pt(t_left)[1]))

    # 3. outside, the long way (over the top) from the -x exit to the +x exit
    sweep = ((t_right - t_left) % (2 * math.pi)) - 2 * math.pi
    steps = int(n * 2)
    for i in range(steps + 1):
        pts.append(outer_pt(t_left + sweep * i / steps))

    # 4. up the +x slot wall (closes back onto the bore start)
    pts.append((slot_outer, outer_pt(t_right)[1]))
    return ccw(pts)


def curve_solid(name, profile, length, bevel, bevel_res=6, axis="Y"):
    """Build a clean watertight prism from a 2D outline, then round its ends.

    Direct mesh construction avoids the duplicate vertices / zero-area quads
    that Blender's curve-to-mesh conversion can leave along a slotted profile.
    The closed profile is extruded along Y; a small angle-limited bevel rounds
    the perimeter and gives the cushion its soft end radii.
    """
    import bmesh

    profile = ccw(profile)
    count = len(profile)
    half_len = length / 2.0
    verts = []
    for y in (-half_len, half_len):
        for x, z in profile:
            verts.append((x, y, z) if axis == "Y" else (x, z, y))

    front = tuple(range(count))
    back = tuple(range(count, 2 * count))
    faces = [front, tuple(reversed(back))]
    for i in range(count):
        j = (i + 1) % count
        # side quad winding is corrected below, but follows the profile edges
        faces.append((i, j, count + j, count + i))

    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    # Consistent outward normals for the cap n-gons and every side quad.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()

    new = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(new)
    if bevel > 1e-9:
        bev = new.modifiers.new("Soft edge radius", "BEVEL")
        bev.width = bevel
        bev.segments = bevel_res
        bev.limit_method = "ANGLE"
        bev.angle_limit = math.radians(60)
        bev.harden_normals = True
        bev.use_clamp_overlap = True
    wn = new.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    wn.keep_sharp = True
    wn.weight = 100
    bpy.context.view_layer.objects.active = new
    new.select_set(True)
    bpy.ops.object.shade_smooth()
    return new


# --------------------------------------------------------------------------- #
# materials
# --------------------------------------------------------------------------- #


def soft_pad_material(name, hex_color, rib_pitch_m, rib_depth):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt, nodes = mat.node_tree, mat.node_tree.nodes
    for n in list(nodes):
        nodes.remove(n)

    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = srgb_hex_to_linear(hex_color)
    bsdf.inputs["Roughness"].default_value = 0.74
    bsdf.inputs["Specular IOR Level"].default_value = 0.18
    bsdf.inputs["IOR"].default_value = 1.42
    bsdf.inputs["Sheen Weight"].default_value = 0.10
    bsdf.inputs["Sheen Roughness"].default_value = 0.75

    # Shallow circumferential grip bands: repeat along the bar's local Y axis.
    # Object coordinates are fed as a vector (not a scalar split axis), giving
    # a clean moulded texture rather than noisy diagonal bumps.
    tc = nodes.new("ShaderNodeTexCoord")
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 1.0 / rib_pitch_m
    wave.inputs["Distortion"].default_value = 0.0
    wave.inputs["Detail"].default_value = 0.0
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = rib_depth
    bump.inputs["Distance"].default_value = 0.00035

    # Fine, soft-touch grain sits below the broad anti-slip ribs.
    grain = nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 420.0
    grain.inputs["Detail"].default_value = 2.0
    grain.inputs["Roughness"].default_value = 0.72
    grain_bump = nodes.new("ShaderNodeBump")
    grain_bump.inputs["Strength"].default_value = 0.12
    grain_bump.inputs["Distance"].default_value = 0.00008

    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(tc.outputs["Object"], grain.inputs["Vector"])
    nt.links.new(grain.outputs["Fac"], grain_bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], grain_bump.inputs["Normal"])
    nt.links.new(grain_bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _layout(nt, out)
    return mat


def rigid_clip_material(name, hex_color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt, nodes = mat.node_tree, mat.node_tree.nodes
    for n in list(nodes):
        nodes.remove(n)
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = srgb_hex_to_linear(hex_color)
    bsdf.inputs["Roughness"].default_value = 0.38
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
    bsdf.inputs["Coat Weight"].default_value = 0.18
    bsdf.inputs["Coat Roughness"].default_value = 0.25
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _layout(nt, out)
    return mat


def _layout(nt, out):
    x = 0.0
    for node in nt.nodes:
        if node.type == "OUTPUT_MATERIAL":
            node.location = (600, 0)
        else:
            node.location = (x, 0)
            x -= 260


# --------------------------------------------------------------------------- #
# scene
# --------------------------------------------------------------------------- #


def scale_about_bbox(obj, factor, anchor="bottom-centre"):
    """Scale an object about its bounding box, not its (arbitrary) origin.

    Keeps the footprint centred and the wheels on the ground, which a plain
    `obj.scale *= f` does not: the cart's origin sits up in the basket.
    """
    import numpy as np

    def corners():
        mw = np.array(obj.matrix_world)
        c = np.array([tuple(v) for v in obj.bound_box])
        w = np.c_[c, np.ones(len(c))] @ mw.T
        return w[:, :3]

    before = corners()
    obj.scale = tuple(s * factor for s in obj.scale)
    bpy.context.view_layer.update()
    after = corners()

    delta = (before.min(0) + before.max(0)) / 2 - (after.min(0) + after.max(0)) / 2
    if anchor == "bottom-centre":
        # keep the lowest point where it was instead of centring on Z
        delta[2] = before[:, 2].min() - after[:, 2].min()
    obj.location = tuple(obj.location[i] + delta[i] for i in range(3))
    bpy.context.view_layer.update()


def find_handle(cart):
    """Measure the top tube of the cart: centre (x, z), diameter, Y span."""
    import numpy as np

    mw = np.array(cart.matrix_world)
    v = np.array([tuple(p.co) for p in cart.data.vertices])
    w = (np.c_[v, np.ones(len(v))] @ mw.T)[:, :3]
    zmax = w[:, 2].max()
    top = w[w[:, 2] > zmax - 0.05]
    ymid = (w[:, 1].min() + w[:, 1].max()) / 2.0
    band = top[np.abs(top[:, 1] - ymid) < 0.10]
    p = band[:, [0, 2]]

    best = None
    for cx in np.arange(p[:, 0].min() - 0.01, p[:, 0].max() + 0.01, 0.0005):
        for cz in np.arange(p[:, 1].min() - 0.01, p[:, 1].max() + 0.01, 0.0005):
            r = np.hypot(p[:, 0] - cx, p[:, 1] - cz)
            s = float(r.std())
            if best is None or s < best[0]:
                best = (s, cx, cz, float(r.mean()))
    return best[1], best[2], best[3] * 2, float(top[:, 1].min()), float(top[:, 1].max())


def ensure_collection(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def move_to_collection(obj, collection):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    collection.objects.link(obj)


def clear_previous_design():
    """Remove only generated HCD objects, leaving the cart and reference intact."""
    for obj in list(bpy.data.objects):
        generated = (
            obj.name == "HCD_Attachment"
            or obj.name.startswith(("HCD_Pad", "HCD_Clip", "HCD_Attachment.",
                                    "HCD_Studio_", "HCD_Presentation_"))
        )
        if generated:
            bpy.data.objects.remove(obj, do_unlink=True)
    presentation = bpy.data.collections.get("HCD - Presentation")
    if presentation is not None and not presentation.objects and not presentation.children:
        bpy.data.collections.remove(presentation, do_unlink=True)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for data in list(datablocks):
            if data.users == 0 and data.name.startswith(("HCD_Pad", "HCD_Clip", "HCD_Soft", "HCD_Rigid", "HCD_Studio", "HCD_Presentation")):
                datablocks.remove(data)


def add_presentation_setup(target_location):
    """Leave the edited blend ready to preview/render when opened in Blender."""
    import mathutils

    scene = bpy.context.scene
    collection = ensure_collection("HCD - Presentation")

    # Floor for context and soft contact shadows.
    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0.0, 0.0, -0.004))
    floor = bpy.context.active_object
    floor.name = "HCD_Studio_Floor"
    floor.data.name = "HCD_Studio_Floor_Mesh"
    move_to_collection(floor, collection)
    floor_mat = bpy.data.materials.new("HCD_Studio_Floor_Mat")
    floor_mat.diffuse_color = srgb_hex_to_linear("#555B64")
    floor_mat.use_nodes = True
    floor_bsdf = next(n for n in floor_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    floor_bsdf.inputs["Base Color"].default_value = srgb_hex_to_linear("#555B64")
    floor_bsdf.inputs["Roughness"].default_value = 0.82
    floor.data.materials.append(floor_mat)

    # Dark world so the blue TPE and silvery clip read clearly.
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    bg = nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = srgb_hex_to_linear("#171A1E")
    bg.inputs["Strength"].default_value = 1.0
    out = nodes.new("ShaderNodeOutputWorld")
    world.node_tree.links.new(bg.outputs["Background"], out.inputs["Surface"])

    def add_area(name, offset, energy, size_x, size_y):
        data = bpy.data.lights.new(name, "AREA")
        data.shape = "RECTANGLE"
        data.size = size_x
        data.size_y = size_y
        data.energy = energy
        obj = bpy.data.objects.new(name, data)
        collection.objects.link(obj)
        obj.location = tuple(target_location[i] + offset[i] for i in range(3))
        direction = mathutils.Vector(target_location) - obj.location
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        return obj

    add_area("HCD_Studio_Key", (-0.55, -0.75, 0.62), 60, 0.9, 0.55)
    add_area("HCD_Studio_Fill", (-1.10, 0.55, 0.28), 18, 1.4, 1.0)
    add_area("HCD_Studio_Rim", (0.85, 0.70, 0.55), 48, 0.8, 0.5)
    add_area("HCD_Studio_Bounce", (-0.30, 0.10, -0.45), 10, 1.2, 0.8)

    # A single polished hero camera with the same broad three-quarter view as
    # the preview render. Its target is the centre of the pad, not the cart.
    az, el, distance = math.radians(38), math.radians(16), 1.15
    camera_data = bpy.data.cameras.new("HCD_Presentation_Camera")
    camera_data.lens = 65
    camera = bpy.data.objects.new("HCD_Presentation_Camera", camera_data)
    collection.objects.link(camera)
    camera.location = (
        target_location[0] - distance * math.cos(el) * math.cos(az),
        target_location[1] - distance * math.cos(el) * math.sin(az),
        target_location[2] + distance * math.sin(el),
    )
    direction = mathutils.Vector(target_location) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1200, 820
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.16
    bpy.context.view_layer.update()


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = os.path.join(root, SRC_BLEND)
    bpy.ops.wm.open_mainfile(filepath=src)

    clear_previous_design()
    cart = bpy.data.objects.get("Shopping Cart")
    if cart is None:
        sys.exit("No object named 'Shopping Cart' in the file.")
    mock = bpy.data.objects.get("Cube.001") or bpy.data.objects.get("Reference_Mockup")

    # The cart ships 4x oversized (4.45 m tall). Bring it to real size once --
    # the guard keeps repeat runs from shrinking it again. Then park the cart on
    # the origin so the ground plane is z=0.
    if abs(CART_SCALE - 1.0) > 1e-9 and cart.dimensions[2] > 2.0:
        scale_about_bbox(cart, CART_SCALE)
    for _ in range(2):
        mw = cart.matrix_world
        c = [mw @ __import__("mathutils").Vector(v) for v in cart.bound_box]
        xs = [v.x for v in c]
        ys = [v.y for v in c]
        zs = [v.z for v in c]
        cart.location = (cart.location[0] - (min(xs) + max(xs)) / 2,
                         cart.location[1] - (min(ys) + max(ys)) / 2,
                         cart.location[2] - min(zs))
        bpy.context.view_layer.update()

    hx, hz, hdia, y0, y1 = find_handle(cart)
    if not HANDLE_DETECT:
        hdia = mm(HANDLE_DIA_MM)
    bar_mid_y = (y0 + y1) / 2.0
    print(f"handle: dia={hdia * 1000:.1f}mm  centre X={hx:.4f} Z={hz:.4f}  "
          f"bar Y {y0:.3f}..{y1:.3f} (len {y1 - y0:.3f} m)")

    # ---------------------------------------------------------------- parts --
    r_tube = hdia / 2.0
    r_in = r_tube + mm(CLIP_BORE_CLEARANCE_MM)
    r_out = r_in + mm(CLIP_WALL_MM)
    r_pad_bore = r_out + mm(PAD_BORE_CLEARANCE_MM)

    # clip: C-channel whose opening sits underneath, so it presses on from below
    b_clip = mm(CLIP_BEVEL_MM)
    half = math.radians(CLIP_WRAP_DEG) / 2.0
    clip_pts = clip_profile(r_in, r_out,
                            math.pi / 2 - half, math.pi / 2 + half,
                            mm(CLIP_FLARE_MM), math.radians(CLIP_FLARE_DEG))
    clip = curve_solid("HCD_Clip", clip_pts, mm(CLIP_LEN_MM), b_clip, bevel_res=3)

    # pad: soft roll, bore sits on the clip OD, snap slot underneath
    b_pad = mm(PAD_BEVEL_MM)
    pad_pts = pad_profile(r_pad_bore, mm(PAD_OUTER_X_MM), mm(PAD_OUTER_Z_MM),
                          PAD_OUTER_N, mm(PAD_OFFSET_X_MM), mm(PAD_OFFSET_Z_MM),
                          mm(PAD_SLOT_BORE_MM), mm(PAD_SLOT_OUTER_MM))
    pad = curve_solid("HCD_Pad", pad_pts, mm(PAD_LEN_MM), b_pad, bevel_res=6)

    # ------------------------------------------------------------ materials --
    pad.data.materials.append(soft_pad_material("HCD_Soft_TPE", PAD_COLOR,
                                                mm(RIB_PITCH_MM), RIB_DEPTH))
    clip.data.materials.append(rigid_clip_material("HCD_Rigid_PP", CLIP_COLOR))

    # ------------------------------------------------------------- assembly --
    design_collection = ensure_collection("HCD - Attachment")
    reference_collection = ensure_collection("HCD - Reference")
    cart_collection = ensure_collection("Cart")
    move_to_collection(cart, cart_collection)

    holder = bpy.data.objects.new("HCD_Attachment", None)
    holder.location = (hx, bar_mid_y, hz)
    holder.empty_display_type = "PLAIN_AXES"
    holder.empty_display_size = 0.025
    design_collection.objects.link(holder)
    bpy.context.view_layer.update()

    import mathutils
    for obj in (pad, clip):
        move_to_collection(obj, design_collection)
        obj.parent = holder
        # The mesh is drawn in handle-centred local coordinates: apply only the
        # holder's translation, with no accidental parent-inverse cancellation.
        obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        obj.location = (0.0, 0.0, 0.0)
    pad.name, clip.name = "HCD_Pad", "HCD_Clip"

    # Preserve the uploaded block as a hidden, unparented reference object.
    if mock is not None:
        mock.name = "Reference_Mockup"
        mock.parent = None
        mock.display_type = "WIRE"
        mock.hide_render = True
        mock.color = (0.9, 0.4, 0.1, 1.0)
        mock.hide_set(True)
        move_to_collection(mock, reference_collection)

    # The uploaded file's default Collection is now empty; drop it rather than
    # leaving a confusing blank collection beside the named product groups.
    for old_collection in list(bpy.data.collections):
        if old_collection.name == "Collection" and not old_collection.objects and not old_collection.children:
            bpy.data.collections.remove(old_collection, do_unlink=True)

    bpy.context.view_layer.update()

    # Save a studio camera/lights in the .blend, so it is immediately useful
    # when opened in Blender (the multi-view render script builds its own rig).
    pad_corners = [pad.matrix_world @ mathutils.Vector(v) for v in pad.bound_box]
    pad_center = tuple((min(v[i] for v in pad_corners) + max(v[i] for v in pad_corners)) / 2
                       for i in range(3))
    add_presentation_setup(pad_center)

    # Make the two editable product parts the active selection when the file opens.
    for selected in list(bpy.context.selected_objects):
        selected.select_set(False)
    pad.select_set(True)
    clip.select_set(True)
    bpy.context.view_layer.objects.active = pad

    # ---------------------------------------------------------- diagnostics --
    print()
    for obj in (pad, clip):
        d = obj.dimensions
        print(f"{obj.name:<10} size(mm) = {d[0] * 1000:7.1f} x {d[1] * 1000:7.1f} x {d[2] * 1000:7.1f}"
              f"   verts={len(obj.data.vertices):<6} faces={len(obj.data.polygons)}")

    # does the pad foul the cart?
    import mathutils
    import numpy as np

    def world_pts(obj):
        m = obj.matrix_world
        return np.array([tuple(m @ mathutils.Vector(v.co)) for v in obj.data.vertices])

    pv = world_pts(pad)
    cw = world_pts(cart)
    lo, hi = pv.min(0) - 0.05, pv.max(0) + 0.05
    near = cw[np.all((cw > lo) & (cw < hi), axis=1)]
    if len(near):
        d = np.sqrt(((near[:, None, :] - pv[None, :, :]) ** 2).sum(-1)).min()
        print(f"clearance to cart: {d * 1000:.1f} mm  ({len(near)} cart verts nearby)")
    else:
        print("clearance to cart: nothing within 50 mm of the pad")

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(root, DST_BLEND))
    print(f"\nsaved -> {DST_BLEND}")


if __name__ == "__main__":
    main()
