#!/usr/bin/env python3
"""Dump a structured report of a .blend file: objects, sizes, materials, topology.

Usage:
    LD_LIBRARY_PATH=$HOME/tools/bpy-stubs python3 blender/scripts/report_blend.py 'blender/source/hcd mockup.blend'
"""

import sys

import bpy

MM = 1000.0  # Blender metres -> millimetres


def main(path: str) -> None:
    bpy.ops.wm.open_mainfile(filepath=path)
    print(f"file           : {path}")
    print(f"blender version: {bpy.app.version_string}")
    print(f"units          : scale={bpy.context.scene.unit_settings.scale_length}, "
          f"system={bpy.context.scene.unit_settings.system}")
    print(f"frame range    : {bpy.context.scene.frame_start}-{bpy.context.scene.frame_end}")
    print()

    print("collections:")
    for col in bpy.data.collections:
        print(f"  - {col.name} ({len(col.objects)} objects)")
    print()

    print("objects:")
    for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        dim = [round(v * MM, 2) for v in obj.dimensions]
        loc = [round(v * MM, 2) for v in obj.location]
        extra = ""
        if obj.type == "MESH":
            me = obj.data
            extra = (f"verts={len(me.vertices):>6}  faces={len(me.polygons):>6}  "
                     f" tris={sum(len(p.vertices) - 2 for p in me.polygons):>6}  "
                     f"ngons={sum(1 for p in me.polygons if len(p.vertices) > 4):>4}  "
                     f"mats={len(me.materials)}")
        elif obj.type == "CURVE":
            extra = f"splines={len(obj.data.splines)}"
        elif obj.type == "EMPTY":
            extra = f"empty_type={obj.empty_display_type}"
        elif obj.type in {"CAMERA", "LIGHT"}:
            extra = obj.data.type
        mods = ",".join(m.type for m in obj.modifiers) or "-"
        print(f"  {obj.name:<28} {obj.type:<8} dim(mm)={dim}  loc(mm)={loc}")
        print(f"  {'':<28} mods={mods}  {extra}")
        if obj.type == "MESH":
            for slot in obj.material_slots:
                m = slot.material
                base = "none"
                if m and m.use_nodes:
                    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                    if bsdf:
                        col = bsdf.inputs["Base Color"].default_value
                        rough = bsdf.inputs["Roughness"].default_value
                        base = f"rgba=({col[0]:.2f},{col[1]:.2f},{col[2]:.2f},{col[3]:.2f}) rough={rough:.2f}"
                print(f"  {'':<28} mat: {m.name if m else '-'} -> {base}")
    print()

    print("materials:")
    for mat in bpy.data.materials:
        print(f"  - {mat.name} (users={mat.users})")
    print()
    print("worlds:", [w.name for w in bpy.data.worlds])
    print("cameras:", [c.name for c in bpy.data.cameras])
    print("lights:", [(l.name, l.type) for l in bpy.data.lights])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python3 inspect.py <file.blend>")
    main(sys.argv[1])
