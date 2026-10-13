#!/usr/bin/env python3
"""Export the HCD to print-ready STL (mm) and GLB for viewing.

STL contains the actual mesh geometry in millimetres. It writes one assembled
file plus one file per part so the soft pad and rigid snap clip can be made from
different materials. GLB keeps both materials and is useful for previews.

Usage:
    LD_LIBRARY_PATH=$HOME/tools/bpy-stubs python3 scripts/export.py
"""

import os

import bpy
import mathutils

BLEND = "blender/source/hcd mockup.blend"
OUT_DIR = "blender/exports"
PARTS = ("HCD_Pad", "HCD_Clip")


def stl_export(path: str) -> None:
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, global_scale=1000.0)
    else:
        bpy.ops.export_mesh.stl(filepath=path, use_selection=True, global_scale=1000.0)
    print(f"  {os.path.basename(path):<28} {os.path.getsize(path) / 1024:>7.0f} KB")


def select_names(names) -> None:
    for obj in bpy.data.objects:
        obj.select_set(obj.name in names)


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(root, BLEND))
    out = os.path.join(root, OUT_DIR)
    os.makedirs(out, exist_ok=True)

    # The assembly sits on the 1.09 m-high trolley bar. Detach each part and
    # clear its transform for a clean origin-centred STL/GLB, leaving the source
    # .blend untouched.
    for name in PARTS:
        obj = bpy.data.objects[name]
        obj.parent = None
        obj.matrix_basis = mathutils.Matrix.Identity(4)
    bpy.context.view_layer.update()

    # Full, two-material assembly STL (mm)
    select_names(PARTS)
    bpy.context.view_layer.objects.active = bpy.data.objects["HCD_Pad"]
    stl_export(os.path.join(out, "hcd_attachment_mm.stl"))

    # Separate printable components
    for name, filename in (("HCD_Pad", "hcd_pad_mm.stl"),
                           ("HCD_Clip", "hcd_clip_mm.stl")):
        select_names((name,))
        bpy.context.view_layer.objects.active = bpy.data.objects[name]
        stl_export(os.path.join(out, filename))

    # GLB retains the colour materials for product previews
    glb = os.path.join(out, "hcd_attachment.glb")
    select_names(PARTS)
    bpy.context.view_layer.objects.active = bpy.data.objects["HCD_Pad"]
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True)
    print(f"  {os.path.basename(glb):<28} {os.path.getsize(glb) / 1024:>7.0f} KB")
    print(f"\nexports in {OUT_DIR}")


if __name__ == "__main__":
    main()
