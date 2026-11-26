#!/usr/bin/env python3
"""Build, render, and animate an original TYTO compact microphone concept.

Usage with Blender installed:
    blender -b --python build_tyto.py -- --stills --animation

For headless Python with the bpy wheel:
    python3 build_tyto.py --stills --animation

The product model and all deliverable imagery are generated in Blender/Cycles.
No reference image or AI-generated render is used.
"""

from __future__ import annotations

import argparse
import bisect
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
RENDER_DIR = ROOT / "renders"
FRAMES_DIR = RENDER_DIR / "animation_frames"
ANIMATION_DIR = ROOT / "animation"
BLEND_PATH = ROOT / "source" / "tyto_microphone.blend"
FPS = 24
FRAME_START = 1
FRAME_END = 144

# Cross-sections for a single swept, sculpted shell. Each row is
# (height, centre_x, half_width_x, half_depth_y), in metres.
# The gentle shift in the centreline creates the neck-to-whorl flow.
BODY_PROFILE = [
    (0.000,  0.012, 0.155, 0.170),
    (0.018,  0.012, 0.205, 0.215),
    (0.070,  0.014, 0.255, 0.245),
    (0.145,  0.020, 0.305, 0.275),
    (0.255,  0.030, 0.330, 0.287),
    (0.430,  0.055, 0.372, 0.302),
    (0.625,  0.075, 0.387, 0.305),
    (0.805,  0.055, 0.370, 0.292),
    (0.965,  0.010, 0.330, 0.270),
    (1.105, -0.055, 0.286, 0.245),
    (1.235, -0.105, 0.248, 0.224),
    (1.365, -0.125, 0.216, 0.205),
    (1.485, -0.120, 0.193, 0.184),
    (1.575, -0.115, 0.153, 0.153),
    (1.645, -0.112, 0.082, 0.090),
    (1.675, -0.110, 0.034, 0.043),
]


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.materials, bpy.data.meshes, bpy.data.curves,
                       bpy.data.cameras, bpy.data.lights, bpy.data.worlds):
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)


def set_active(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def recalculate_normals(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def shade_smooth(obj):
    if obj.type == "MESH":
        for polygon in obj.data.polygons:
            polygon.use_smooth = True


def catmull_rom(rows, samples_per_segment=8):
    """Sample a smooth Catmull-Rom curve through equal-parameter rows."""
    if len(rows) < 2:
        return list(rows)
    result = []
    n = len(rows)
    for i in range(n - 1):
        p0 = rows[max(0, i - 1)]
        p1 = rows[i]
        p2 = rows[i + 1]
        p3 = rows[min(n - 1, i + 2)]
        for j in range(samples_per_segment):
            t = j / samples_per_segment
            t2, t3 = t * t, t * t * t
            row = []
            for k in range(len(p1)):
                value = 0.5 * (
                    2.0 * p1[k]
                    + (-p0[k] + p2[k]) * t
                    + (2.0*p0[k] - 5.0*p1[k] + 4.0*p2[k] - p3[k]) * t2
                    + (-p0[k] + 3.0*p1[k] - 3.0*p2[k] + p3[k]) * t3
                )
                row.append(value)
            result.append(tuple(row))
    result.append(tuple(rows[-1]))
    return result


def body_profile_at(z):
    """Smoothly interpolate the shell centre and radii at height z."""
    z = min(max(z, BODY_PROFILE[0][0]), BODY_PROFILE[-1][0])
    heights = [row[0] for row in BODY_PROFILE]
    i = max(0, min(len(BODY_PROFILE) - 2, bisect.bisect_right(heights, z) - 1))
    p0 = BODY_PROFILE[max(0, i - 1)]
    p1 = BODY_PROFILE[i]
    p2 = BODY_PROFILE[i + 1]
    p3 = BODY_PROFILE[min(len(BODY_PROFILE) - 1, i + 2)]
    span = max(1e-8, p2[0] - p1[0])
    t = (z - p1[0]) / span
    t2, t3 = t * t, t * t * t
    values = []
    for k in range(1, 4):
        value = 0.5 * (
            2.0 * p1[k]
            + (-p0[k] + p2[k]) * t
            + (2.0*p0[k] - 5.0*p1[k] + 4.0*p2[k] - p3[k]) * t2
            + (-p0[k] + 3.0*p1[k] - 3.0*p2[k] + p3[k]) * t3
        )
        values.append(value)
    cx, rx, ry = values
    return cx, max(0.012, rx), max(0.012, ry)


def front_surface_y(x, z):
    """Front-facing surface of the swept body at a front-view x/z point."""
    cx, rx, ry = body_profile_at(z)
    q = (x - cx) / rx
    q = max(-0.985, min(0.985, q))
    return -ry * math.sqrt(max(0.02, 1.0 - q*q))


def plane_basis(axis):
    axis = Vector(axis).normalized()
    trial = Vector((1.0, 0.0, 0.0))
    u = trial - axis * trial.dot(axis)
    if u.length < 1e-6:
        trial = Vector((0.0, 1.0, 0.0))
        u = trial - axis * trial.dot(axis)
    u.normalize()
    v = axis.cross(u).normalized()
    return u, v


def material_principled(name, color, metallic, roughness,
                         noise_scale=None, bump_strength=0.035,
                         bump_distance=0.002):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    if noise_scale:
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = noise_scale
        noise.inputs["Detail"].default_value = 2.0
        noise.inputs["Roughness"].default_value = 0.56
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = bump_strength
        bump.inputs["Distance"].default_value = bump_distance
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return mat


def material_emission(name, color=(1.0, 0.22, 0.035), strength=1.2):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*color, 1.0)
    emission.inputs["Strength"].default_value = strength
    output = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def create_materials():
    return {
        "shell": material_principled(
            "TYTO_Satin_Aged_Bronze", (0.205, 0.112, 0.062), 0.78, 0.32,
            noise_scale=210, bump_strength=0.025, bump_distance=0.0016,
        ),
        "bright": material_principled(
            "TYTO_Machined_Bronze_Edges", (0.34, 0.205, 0.118), 0.84, 0.24,
        ),
        "barrel": material_principled(
            "TYTO_Deep_Bronze_Barrel", (0.088, 0.056, 0.034), 0.82, 0.29,
            noise_scale=280, bump_strength=0.018, bump_distance=0.0012,
        ),
        "channel": material_principled(
            "TYTO_Graphite_Spiral_Inlay", (0.014, 0.016, 0.017), 0.48, 0.31,
            noise_scale=180, bump_strength=0.012, bump_distance=0.0008,
        ),
        "grille": material_principled(
            "TYTO_Matte_Black_Grille", (0.004, 0.005, 0.006), 0.18, 0.52,
        ),
        "weave": material_principled(
            "TYTO_Graphite_Grille_Weave", (0.036, 0.040, 0.043), 0.42, 0.39,
        ),
        "seam": material_principled(
            "TYTO_Lower_Shell_Seam", (0.034, 0.026, 0.019), 0.68, 0.39,
        ),
        "backdrop": material_principled(
            "TYTO_Studio_Charcoal", (0.026, 0.024, 0.022), 0.0, 0.88,
        ),
        "led": material_emission("TYTO_Subtle_Amber_Light", (1.0, 0.205, 0.025), 1.15),
    }


def make_bezier_curve(name, points, bevel_depth, material, radii=None,
                      resolution=18, bevel_resolution=5):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = resolution
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = bevel_resolution
    curve.use_fill_caps = True
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for i, (point, co) in enumerate(zip(spline.bezier_points, points)):
        point.co = co
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
        if radii is not None:
            point.radius = radii[i]
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def make_poly_curve(name, splines, bevel_depth, material,
                    bevel_resolution=3, spline_radii=None):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = bevel_resolution
    curve.use_fill_caps = True
    for spline_index, coords in enumerate(splines):
        if len(coords) < 2:
            continue
        spline = curve.splines.new("POLY")
        spline.points.add(len(coords) - 1)
        for point_index, (point, co) in enumerate(zip(spline.points, coords)):
            point.co = (co[0], co[1], co[2], 1.0)
            if spline_radii is not None and spline_index < len(spline_radii):
                point.radius = spline_radii[spline_index][point_index]
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def make_oriented_cylinder(name, radius, depth, center, axis, material,
                           bevel=0.012, vertices=144):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth, location=tuple(center),
    )
    obj = bpy.context.object
    obj.name = name
    axis = Vector(axis).normalized()
    obj.rotation_euler = axis.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(material)
    if bevel > 0:
        bevel_mod = obj.modifiers.new("Precision_Radiused_Edges", "BEVEL")
        bevel_mod.width = bevel
        bevel_mod.segments = 4
        bevel_mod.limit_method = "ANGLE"
        normals = obj.modifiers.new("Machined_Surface_Normals", "WEIGHTED_NORMAL")
        normals.keep_sharp = True
    shade_smooth(obj)
    return obj


def make_oriented_torus(name, major_radius, minor_radius, center, axis, material,
                         major_segments=144, minor_segments=24):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=major_segments, minor_segments=minor_segments,
        major_radius=major_radius, minor_radius=minor_radius,
        location=tuple(center),
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = Vector(axis).normalized().to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(material)
    shade_smooth(obj)
    return obj


def make_annular_collar(name, origin, axis, t_bottom, t_top,
                        inner_radius, outer_radius, material):
    """A lathed, hollow, chamfered collar with a clean machined profile."""
    axis = Vector(axis).normalized()
    u, v = plane_basis(axis)
    chamfer = min(0.012, (t_top - t_bottom) * 0.12,
                  (outer_radius - inner_radius) * 0.20)
    profile = [
        (t_bottom + chamfer, inner_radius),
        (t_bottom + chamfer, outer_radius - chamfer),
        (t_bottom, outer_radius),
        (t_top, outer_radius),
        (t_top - chamfer, outer_radius - chamfer),
        (t_top - chamfer, inner_radius + chamfer),
        (t_top, inner_radius),
        (t_bottom, inner_radius),
    ]
    segments = 160
    vertices = []
    for axial, radius in profile:
        center = Vector(origin) + axis * axial
        for i in range(segments):
            theta = 2.0 * math.pi * i / segments
            vertices.append(tuple(center + radius * (u * math.cos(theta) + v * math.sin(theta))))
    faces = []
    for row in range(len(profile)):
        next_row = (row + 1) % len(profile)
        for i in range(segments):
            nxt = (i + 1) % segments
            faces.append((row*segments+i, row*segments+nxt,
                          next_row*segments+nxt, next_row*segments+i))
    mesh = bpy.data.meshes.new(f"{name}_Turned_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    recalculate_normals(mesh)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    shade_smooth(obj)
    return obj


# ---------------------------------------------------------------------------
# Sculpted shell and continuous enamel/amber inlay
# ---------------------------------------------------------------------------

def make_diamond_knurled_collar(name, origin, axis, t_bottom, t_top,
                                  inner_radius, outer_radius, material,
                                  line_count=48, turns=5.4):
    """Build a closed collar with a true, evenly pitched diamond-cut surface."""
    axis = Vector(axis).normalized()
    u, v = plane_basis(axis)
    around_count = line_count * 10
    axial_count = int(turns * 32) + 1
    outer_vertices = []
    inner_vertices = []

    def triangle_wave(value):
        fraction = value - math.floor(value)
        return 1.0 - 2.0 * abs(fraction - 0.5)

    for row in range(axial_count):
        t = row / (axial_count - 1)
        axial = t_bottom + (t_top - t_bottom) * t
        center = Vector(origin) + axis * axial
        for around in range(around_count):
            theta = 2.0 * math.pi * around / around_count
            phase = line_count * around / around_count
            diamond = min(triangle_wave(phase - turns * t),
                          triangle_wave(phase + turns * t))
            edge_fade = min(1.0, t / 0.06, (1.0 - t) / 0.06)
            radius = outer_radius - 0.0012 + 0.0024 * diamond * edge_fade
            radial = u * math.cos(theta) + v * math.sin(theta)
            outer_vertices.append(tuple(center + radius * radial))
            inner_vertices.append(tuple(center + inner_radius * radial))

    vertices = outer_vertices + inner_vertices
    outer_total = axial_count * around_count
    faces = []
    for row in range(axial_count - 1):
        for around in range(around_count):
            nxt = (around + 1) % around_count
            a = row * around_count + around
            b = row * around_count + nxt
            c = (row + 1) * around_count + nxt
            d = (row + 1) * around_count + around
            faces.append((a, b, c, d))
    outer_face_count = len(faces)
    for row in range(axial_count - 1):
        for around in range(around_count):
            nxt = (around + 1) % around_count
            a = outer_total + row * around_count + around
            b = outer_total + (row + 1) * around_count + around
            c = outer_total + (row + 1) * around_count + nxt
            d = outer_total + row * around_count + nxt
            faces.append((a, b, c, d))
    inner_face_count = len(faces) - outer_face_count

    bottom_outer = 0
    bottom_inner = outer_total
    top_outer = (axial_count - 1) * around_count
    top_inner = outer_total + top_outer
    for around in range(around_count):
        nxt = (around + 1) % around_count
        faces.append((bottom_outer + around,
                      bottom_inner + around,
                      bottom_inner + nxt,
                      bottom_outer + nxt))
        faces.append((top_outer + around,
                      top_outer + nxt,
                      top_inner + nxt,
                      top_inner + around))

    mesh = bpy.data.meshes.new(f"{name}_Diamond_Cut_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    recalculate_normals(mesh)
    # Keep the tiny knurl facets crisp while the inside wall remains smooth.
    for polygon in list(mesh.polygons)[:outer_face_count]:
        polygon.use_smooth = False
    for polygon in list(mesh.polygons)[outer_face_count:outer_face_count + inner_face_count]:
        polygon.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_swept_shell(material):
    z_min = BODY_PROFILE[0][0]
    z_max = BODY_PROFILE[-1][0]
    ring_count = 190
    around_count = 160
    vertices = []
    for ring in range(ring_count):
        z = z_min + (z_max - z_min) * ring / (ring_count - 1)
        cx, rx, ry = body_profile_at(z)
        for around in range(around_count):
            theta = 2.0 * math.pi * around / around_count
            x = cx + rx * math.cos(theta)
            y = ry * math.sin(theta)
            vertices.append((x, y, z))
    faces = []
    for ring in range(ring_count - 1):
        for around in range(around_count):
            nxt = (around + 1) % around_count
            a = ring * around_count + around
            b = ring * around_count + nxt
            c = (ring + 1) * around_count + nxt
            d = (ring + 1) * around_count + around
            faces.append((a, b, c, d))
    bottom_center = len(vertices)
    cx0, _, _ = body_profile_at(z_min)
    vertices.append((cx0, 0.0, z_min))
    top_center = len(vertices)
    cx1, _, _ = body_profile_at(z_max)
    vertices.append((cx1, 0.0, z_max))
    for around in range(around_count):
        nxt = (around + 1) % around_count
        faces.append((bottom_center, nxt, around))
        a = (ring_count - 1) * around_count + around
        b = (ring_count - 1) * around_count + nxt
        faces.append((top_center, a, b))
    mesh = bpy.data.meshes.new("TYTO_Swept_Monocoque_Shell_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    recalculate_normals(mesh)
    obj = bpy.data.objects.new("TYTO_Swept_Bronze_Monocoque", mesh)
    bpy.context.collection.objects.link(obj)
    shade_smooth(obj)
    return obj


def path_frame(samples, index):
    before = samples[max(0, index - 1)]
    after = samples[min(len(samples) - 1, index + 1)]
    dx, dz = after[0] - before[0], after[1] - before[1]
    length = max(1e-8, math.hypot(dx, dz))
    tangent = (dx / length, dz / length)
    normal = (-tangent[1], tangent[0])
    return tangent, normal


def make_channel_path():
    # A slim graphite accent descends along the swept chassis and resolves into
    # a restrained, mathematically clean whorl near the lower front.
    control = [
        (-0.238, 1.325, 0.050),
        (-0.267, 1.145, 0.051),
        (-0.239, 0.960, 0.051),
        (-0.176, 0.775, 0.052),
        (-0.148, 0.600, 0.052),
    ]
    cx, cz = 0.070, 0.470
    outer_radius, inner_radius = 0.225, 0.014
    turns = 1.12
    for i in range(81):
        t = i / 80.0
        theta = math.pi + turns * 2.0 * math.pi * t
        radius = outer_radius * (1.0 - t) + inner_radius * t
        width = 0.052 * (0.72 + 0.28 * (radius / outer_radius))
        control.append((cx + radius * math.cos(theta),
                        cz + radius * math.sin(theta), width))
    return catmull_rom(control, samples_per_segment=3), (cx, cz)


def make_ribbon_mesh(name, samples, material, width_scale=1.0,
                     surface_lift=0.004, cross_segments=10):
    vertices = []
    for i, (x, z, width) in enumerate(samples):
        _, normal = path_frame(samples, i)
        taper = min(1.0, i / 9.0, (len(samples) - 1 - i) / 12.0)
        taper = max(0.035, taper)
        half_width = 0.5 * width * width_scale * taper
        for j in range(cross_segments + 1):
            side = -1.0 + 2.0 * j / cross_segments
            q = side * half_width
            px = x + normal[0] * q
            pz = z + normal[1] * q
            py = front_surface_y(px, pz) - surface_lift
            vertices.append((px, py, pz))
    faces = []
    row_size = cross_segments + 1
    for i in range(len(samples) - 1):
        for j in range(cross_segments):
            a = i * row_size + j
            b = a + row_size
            faces.append((a, b, b + 1, a + 1))
    mesh = bpy.data.meshes.new(f"{name}_Surface_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    recalculate_normals(mesh)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    solid = obj.modifiers.new("Enamel_Insert_Thickness", "SOLIDIFY")
    solid.thickness = 0.0035
    solid.offset = 0.0
    bevel = obj.modifiers.new("Softened_Insert_Edges", "BEVEL")
    bevel.width = 0.002
    bevel.segments = 3
    return obj


def points_on_ribbon(samples, lateral_factor, lift):
    result = []
    for i, (x, z, width) in enumerate(samples):
        _, normal = path_frame(samples, i)
        taper = min(1.0, i / 9.0, (len(samples) - 1 - i) / 12.0)
        taper = max(0.035, taper)
        q = 0.5 * width * taper * lateral_factor
        px = x + normal[0] * q
        pz = z + normal[1] * q
        py = front_surface_y(px, pz) - lift
        result.append((px, py, pz))
    return result


def make_shell_inlay(materials):
    samples, eye_center = make_channel_path()
    make_ribbon_mesh("Graphite_Whorl_Inlay", samples, materials["channel"],
                     width_scale=1.0, surface_lift=0.0035)

    # A fine bronze guard traces one edge; the amber light is nested in the other.
    bronze_points = points_on_ribbon(samples, -0.78, 0.012)
    make_poly_curve("Whorl_Bronze_Edge_Bead", [bronze_points], 0.0034,
                    materials["bright"], bevel_resolution=4)

    led_points = points_on_ribbon(samples, 0.32, 0.012)
    led = make_poly_curve("Continuous_Amber_Whorl_Light", [led_points], 0.0042,
                          materials["led"], bevel_resolution=4)
    led.data.bevel_factor_start = 0.0
    led.data.bevel_factor_end = 0.08
    led.data.keyframe_insert(data_path="bevel_factor_end", frame=FRAME_START)
    led.data.bevel_factor_end = 1.0
    led.data.keyframe_insert(data_path="bevel_factor_end", frame=24)
    led.data.bevel_factor_end = 1.0
    led.data.keyframe_insert(data_path="bevel_factor_end", frame=FRAME_END)

    # A small, raised metallic spiral eye is the deliberate focal point of the inlay.
    cx, cz = eye_center
    eye_points = []
    eye_radii = []
    count = 80
    for i in range(count):
        t = i / (count - 1)
        theta = -0.30 * math.pi + 2.0 * math.pi * 1.05 * t
        radius = 0.052 * (1.0 - t) + 0.004
        x = cx + radius * math.cos(theta)
        z = cz + radius * math.sin(theta)
        y = front_surface_y(x, z) - 0.018
        eye_points.append((x, y, z))
        eye_radii.append(0.78 - 0.58 * t)
    make_bezier_curve("Raised_Spiral_Eye_Ridge", eye_points, 0.009,
                      materials["bright"], eye_radii,
                      resolution=12, bevel_resolution=5)
    return led


def make_lower_seam(material):
    # A quiet, continuous parting line follows the lower contour of the body.
    z = 0.148
    cx, rx, ry = body_profile_at(z)
    points = []
    for i in range(193):
        theta = 2.0 * math.pi * i / 192
        nx = math.cos(theta) / rx
        ny = math.sin(theta) / ry
        length = math.hypot(nx, ny)
        nx, ny = nx / length, ny / length
        x = cx + rx * math.cos(theta) + 0.004 * nx
        y = ry * math.sin(theta) + 0.004 * ny
        points.append((x, y, z))
    return make_poly_curve("Continuous_Lower_Shell_Seam", [points], 0.0032,
                           material, bevel_resolution=3)


# ---------------------------------------------------------------------------
# Short acoustic barrel, precision knurl, and recessed woven grille
# ---------------------------------------------------------------------------

def make_grille_disk(name, center, axis, radius, material):
    axis = Vector(axis).normalized()
    u, v = plane_basis(axis)
    segments = 160
    vertices = [tuple(center)]
    for i in range(segments):
        theta = 2.0 * math.pi * i / segments
        vertices.append(tuple(Vector(center) + radius * (u * math.cos(theta) + v * math.sin(theta))))
    faces = [(0, i + 1, (i + 1) % segments + 1) for i in range(segments)]
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    recalculate_normals(mesh)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_microphone_head(materials):
    axis = Vector((0.090, -0.065, 0.994)).normalized()
    origin = Vector((-0.115, 0.010, 1.365))
    u, v = plane_basis(axis)
    barrel_start, barrel_end = -0.040, 0.455
    barrel_center = origin + axis * ((barrel_start + barrel_end) * 0.5)
    make_oriented_cylinder(
        "Integrated_Acoustic_Barrel", 0.207, barrel_end - barrel_start,
        barrel_center, axis, materials["barrel"], bevel=0.016, vertices=160,
    )
    # One exposed machined bead marks the clean emergence of the capsule from
    # the sculpted housing; the hidden lower junction stays uninterrupted.
    make_oriented_torus("Barrel_Transition_Bead", 0.208, 0.0075,
                        origin + axis * 0.305, axis, materials["bright"])

    band_bottom, band_top = 0.405, 0.622
    outer_radius, inner_radius = 0.252, 0.199
    make_diamond_knurled_collar(
        "Diamond_Knurled_Bronze_Retaining_Ring", origin, axis,
        band_bottom, band_top, inner_radius, outer_radius,
        materials["shell"], line_count=48, turns=5.4,
    )
    make_oriented_torus("Knurl_Lower_Polished_Lip", 0.246, 0.0065,
                        origin + axis * (band_bottom + 0.010), axis, materials["bright"])
    make_oriented_torus("Knurl_Upper_Polished_Lip", 0.246, 0.0070,
                        origin + axis * (band_top - 0.009), axis, materials["bright"])

    # The grille is recessed below a slim, softly radiused port lip.
    port_lip_t = band_top + 0.002
    make_oriented_torus("Sculpted_Port_Lip", 0.220, 0.016,
                        origin + axis * port_lip_t, axis, materials["bright"])
    make_oriented_torus("Inner_Port_Seat", 0.198, 0.0055,
                        origin + axis * (band_top - 0.024), axis, materials["seam"])
    disk_t = band_top - 0.041
    disk_center = origin + axis * disk_t
    grille_radius = 0.190
    make_grille_disk("Recessed_Black_Grille_Backing", disk_center, axis,
                     grille_radius, materials["grille"])

    # A pair of fine, offset wire families reads as woven graphite mesh.
    weave_splines = []
    pitch = 0.0092
    steps = int((2.0 * grille_radius) / pitch)
    for i in range(-steps // 2, steps // 2 + 1):
        q = i * pitch
        if abs(q) >= grille_radius:
            continue
        half = math.sqrt(grille_radius * grille_radius - q*q)
        p1 = disk_center + u * (-half) + v * q + axis * 0.0020
        p2 = disk_center + u * ( half) + v * q + axis * 0.0020
        weave_splines.append([tuple(p1), tuple(p2)])
        p3 = disk_center + u * q + v * (-half) + axis * 0.0032
        p4 = disk_center + u * q + v * ( half) + axis * 0.0032
        weave_splines.append([tuple(p3), tuple(p4)])
    make_poly_curve("Precision_Woven_Black_Microphone_Grille", weave_splines,
                    0.00075, materials["weave"], bevel_resolution=2)

    for index, radius in enumerate((0.070, 0.128, 0.176), start=1):
        make_oriented_torus(f"Grille_Internal_Retainer_{index}", radius, 0.0014,
                            disk_center + axis * 0.0042, axis, materials["seam"],
                            major_segments=128, minor_segments=12)
    return axis, origin, origin + axis * (band_top + 0.02)


# ---------------------------------------------------------------------------
# Turntable, cameras, and studio
# ---------------------------------------------------------------------------

def make_camera(name, location, target, lens):
    data = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(cam)
    cam.location = location
    data.lens = lens
    data.sensor_fit = "VERTICAL"
    target_obj = bpy.data.objects.new(f"{name}_Aim", None)
    bpy.context.collection.objects.link(target_obj)
    target_obj.location = target
    target_obj.empty_display_type = "SPHERE"
    target_obj.empty_display_size = 0.02
    track = cam.constraints.new("TRACK_TO")
    track.target = target_obj
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    return cam


def make_area_light(name, location, target, power, color, size,
                    shape="DISK", size_y=None):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = power
    data.color = color
    data.shape = shape
    data.size = size
    if shape == "RECTANGLE" and size_y is not None:
        data.size_y = size_y
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def make_cyclorama(material):
    """A wide, seamless floor-to-wall sweep, fixed behind the rotating product."""
    x_extent = 80.0
    floor_start, floor_end, floor_z = -80.0, 1.45, 0.0
    radius = 1.15
    section = [(floor_start, floor_z), (0.0, floor_z), (floor_end, floor_z)]
    for i in range(1, 25):
        angle = 0.5 * math.pi * i / 24.0
        y = floor_end + radius * math.sin(angle)
        z = floor_z + radius * (1.0 - math.cos(angle))
        section.append((y, z))
    wall_y = floor_end + radius
    wall_z = floor_z + radius
    section.extend((wall_y, wall_z + dz) for dz in (0.8, 2.0, 6.0, 18.0, 40.0))
    vertices = []
    for y, z in section:
        vertices.extend(((-x_extent, y, z), (x_extent, y, z)))
    faces = []
    for i in range(len(section) - 1):
        a = i * 2
        b = a + 2
        faces.append((a, a + 1, b + 1, b))
    mesh = bpy.data.meshes.new("TYTO_Seamless_Studio_Sweep_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new("TYTO_Fixed_Charcoal_Cyclorama", mesh)
    bpy.context.collection.objects.link(obj)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return obj


def animate_turntable(turntable):
    turntable.rotation_euler = (0.0, 0.0, 0.0)
    turntable.keyframe_insert(data_path="rotation_euler", index=2, frame=FRAME_START)
    turntable.rotation_euler.z = 2.0 * math.pi
    turntable.keyframe_insert(data_path="rotation_euler", index=2, frame=FRAME_END + 1)
    action = turntable.animation_data.action if turntable.animation_data else None
    if action:
        for curve in action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"


def setup_studio(scene, materials, turntable):
    make_cyclorama(materials["backdrop"])

    world = bpy.data.worlds.new("TYTO_Studio_World")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.080, 0.071, 0.061, 1.0)
    background.inputs["Strength"].default_value = 0.30
    scene.world = world

    target = bpy.data.objects.new("TYTO_Hero_Focus", None)
    bpy.context.collection.objects.link(target)
    target.location = (0.04, 0.0, 1.03)
    target.empty_display_type = "SPHERE"
    target.empty_display_size = 0.04

    hero_data = bpy.data.cameras.new("TYTO_Studio_Hero_Camera")
    hero = bpy.data.objects.new("TYTO_Studio_Hero_Camera", hero_data)
    bpy.context.collection.objects.link(hero)
    hero.location = (2.05, -7.35, 3.05)
    hero_data.lens = 66
    hero_data.sensor_fit = "VERTICAL"
    track = hero.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    # Turntable rotation affects only the microphone; studio and shadows stay fixed.
    animate_turntable(turntable)

    make_area_light("Warm_Key_Softbox", (-3.3, -4.2, 4.1), (0.0, 0.0, 0.95),
                    420, (1.0, 0.80, 0.64), 3.5, "RECTANGLE", 2.8)
    make_area_light("Cool_Fill_Softbox", (3.8, -3.0, 2.5), (0.05, 0.0, 0.9),
                    185, (0.78, 0.86, 1.0), 2.7, "DISK")
    make_area_light("Bronze_Rim_Strip", (0.7, 2.7, 3.5), (0.0, 0.0, 1.0),
                    360, (1.0, 0.72, 0.49), 3.0, "RECTANGLE", 1.1)
    make_area_light("Top_Softbox", (-0.6, 0.1, 5.2), (0.0, 0.0, 0.7),
                    290, (1.0, 0.93, 0.84), 2.6, "RECTANGLE", 1.2)
    make_area_light("Edge_Kicker", (-4.0, -0.2, 1.6), (-0.1, 0.0, 0.9),
                    130, (1.0, 0.68, 0.43), 2.8, "RECTANGLE", 0.55)

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.cycles.use_preview_denoising = True
    scene.cycles.use_persistent_data = True
    scene.cycles.max_bounces = 8
    scene.render.threads_mode = "FIXED"
    scene.render.threads = max(4, min(12, os.cpu_count() or 8))
    scene.render.resolution_x = 1240
    scene.render.resolution_y = 1536
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scene.view_settings.exposure = -0.08
    scene.view_settings.gamma = 1.0
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
    scene.camera = hero
    scene.frame_set(FRAME_START)
    return target, hero


def preserve_parent_transform(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def build_scene():
    clear_scene()
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    ANIMATION_DIR.mkdir(parents=True, exist_ok=True)
    BLEND_PATH.parent.mkdir(parents=True, exist_ok=True)
    materials = create_materials()

    body = make_swept_shell(materials["shell"])
    led = make_shell_inlay(materials)
    make_lower_seam(materials["seam"])
    axis, axis_origin, top_center = make_microphone_head(materials)

    # Capture and parent only the product parts, not cameras, lights, or studio.
    product_parts = list(bpy.context.scene.objects)
    turntable = bpy.data.objects.new("TYTO_Product_Turntable", None)
    bpy.context.collection.objects.link(turntable)
    turntable.location = (0.0, 0.0, 0.0)
    turntable.empty_display_type = "CIRCLE"
    turntable.empty_display_size = 0.13
    for obj in product_parts:
        preserve_parent_transform(obj, turntable)

    scene = bpy.context.scene
    focus, hero = setup_studio(scene, materials, turntable)
    scene["TYTO_design_note"] = (
        "Original sculptural compact microphone concept: swept bronze monocoque, "
        "graphite whorl inlay, recessed woven grille, and subtle amber light path."
    )
    scene["microphone_axis"] = tuple(axis)
    scene["microphone_axis_origin"] = tuple(axis_origin)
    scene["microphone_top_center"] = tuple(top_center)

    front = make_camera("TYTO_Front_Studio_Camera", (0.10, -7.65, 1.75), (0.02, 0.0, 1.02), 72)
    spiral = make_camera("TYTO_Whorl_Detail_Camera", (1.30, -5.35, 2.40), (0.06, -0.10, 0.70), 86)
    profile = make_camera("TYTO_Side_Profile_Camera", (7.10, -2.4, 2.65), (0.02, 0.0, 1.00), 72)
    grille_u, grille_v = plane_basis(axis)
    grille_cam = make_camera(
        "TYTO_Port_Macro_Camera",
        tuple(top_center + axis * 1.45 + grille_u * 0.72 + grille_v * 0.20),
        tuple(top_center), 62,
    )

    scene.camera = hero
    scene.frame_set(FRAME_START)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    return {
        "scene": scene,
        "hero": hero,
        "front": front,
        "spiral": spiral,
        "profile": profile,
        "grille": grille_cam,
        "turntable": turntable,
        "led": led,
    }


# ---------------------------------------------------------------------------
# Actual Blender renders and H.264 turntable
# ---------------------------------------------------------------------------

def set_render_quality(scene, width, height, samples):
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"


def mute_led_animation(led_obj):
    muted = []
    action = led_obj.data.animation_data.action if led_obj.data.animation_data else None
    if action:
        for curve in action.fcurves:
            if curve.data_path == "bevel_factor_end":
                muted.append((curve, curve.mute))
                curve.mute = True
    return muted


def render_stills(bundle, preview=False):
    scene = bundle["scene"]
    turntable = bundle["turntable"]
    led = bundle["led"]
    scene.frame_set(FRAME_START)
    turntable.rotation_euler.z = 0.0
    muted = mute_led_animation(led)
    led.data.bevel_factor_end = 1.0
    bpy.context.view_layer.update()

    specs = [
        ("hero", bundle["hero"], "tyto_hero.png", 1240, 1536, 48),
        ("front", bundle["front"], "tyto_front_shell.png", 1040, 1280, 36),
        ("whorl", bundle["spiral"], "tyto_top_spiral.png", 1040, 1280, 40),
        ("profile", bundle["profile"], "tyto_side_profile.png", 1040, 1280, 36),
        ("port macro", bundle["grille"], "tyto_knurl_macro.png", 1200, 1000, 40),
    ]
    for label, camera, filename, width, height, samples in specs:
        scene.camera = camera
        if preview:
            width, height, samples = 720, 900, 14
        set_render_quality(scene, width, height, samples)
        output = RENDER_DIR / ("_tyto_preview.png" if preview else filename)
        scene.render.filepath = str(output)
        print(f"[TYTO] Rendering {label}: {width}x{height}, {samples} Cycles samples -> {output}", flush=True)
        bpy.ops.render.render(write_still=True)
        if preview:
            break

    for curve, was_muted in muted:
        curve.mute = was_muted
    scene.frame_set(FRAME_START)
    turntable.rotation_euler.z = 0.0
    scene.camera = bundle["hero"]
    set_render_quality(scene, 1240, 1536, 48)
    scene.render.filepath = str(RENDER_DIR / "tyto_hero.png")
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))


def locate_ffmpeg():
    if os.environ.get("FFMPEG"):
        return os.environ["FFMPEG"]
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def render_animation(bundle):
    scene = bundle["scene"]
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    scene.camera = bundle["hero"]
    set_render_quality(scene, 480, 600, 8)
    scene.render.filepath = str(FRAMES_DIR / "tyto_")
    for frame in range(FRAME_START, FRAME_END + 1):
        scene.frame_set(frame)
        scene.render.filepath = str(FRAMES_DIR / f"tyto_{frame:04d}.png")
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=True)
        if frame % 12 == 0 or frame == FRAME_START:
            print(f"[TYTO] Turntable frame {frame}/{FRAME_END}", flush=True)

    ffmpeg = locate_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg not found. Install imageio-ffmpeg or set FFMPEG.")
    output = ANIMATION_DIR / "tyto_orbit_6s.mp4"
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(FPS), "-start_number", str(FRAME_START),
        "-i", str(FRAMES_DIR / "tyto_%04d.png"),
        "-frames:v", str(FRAME_END), "-c:v", "libx264", "-preset", "medium",
        "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output),
    ]
    print(f"[TYTO] Encoding six-second turntable -> {output}", flush=True)
    subprocess.run(command, check=True)
    scene.frame_set(FRAME_START)
    scene.camera = bundle["hero"]
    set_render_quality(scene, 1240, 1536, 48)
    scene.render.filepath = str(RENDER_DIR / "tyto_hero.png")
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print(f"[TYTO] Turntable complete: {output.stat().st_size:,} bytes", flush=True)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stills", action="store_true", help="Render five product stills")
    parser.add_argument("--animation", action="store_true", help="Render 144 turntable frames and encode MP4")
    parser.add_argument("--preview", action="store_true", help="Render one fast hero preview")
    parser.add_argument("--no-save", action="store_true", help="Do not save the .blend")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    bundle = build_scene()
    if args.preview:
        render_stills(bundle, preview=True)
    if args.stills:
        render_stills(bundle, preview=False)
    if args.animation:
        render_animation(bundle)
    if not args.no_save:
        bundle["scene"].frame_set(FRAME_START)
        bundle["scene"].camera = bundle["hero"]
        bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print(f"[TYTO] Editable original scene saved at {BLEND_PATH}", flush=True)


if __name__ == "__main__":
    main()
