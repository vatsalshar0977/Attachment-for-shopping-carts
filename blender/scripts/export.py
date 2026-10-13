#!/usr/bin/env python3
"""Export the fold-out leaning support as an animated GLB and static STLs.

The GLB retains the deploy-to-stow animation. STL files are static geometry at
the deployed pose and are exported in millimetres about the lower hinge axis;
they are for fit/layout review, not production-ready tooling.

Run from the repository root:
    LD_LIBRARY_PATH=$HOME/tools/bpy-stubs python3 blender/scripts/export.py
"""

from __future__ import annotations

import os

import bpy
from mathutils import Matrix

BLEND = "blender/source/hcd mockup.blend"
OUT_DIR = "blender/exports"
ASSEMBLY_COLLECTION = "HCD - Foldable Lean Rest"
DEPLOYED_FRAME = 1


def stl_export(path: str) -> None:
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True,
                               global_scale=1000.0, apply_modifiers=True)
    else:
        bpy.ops.export_mesh.stl(filepath=path, use_selection=True,
                                global_scale=1000.0, use_mesh_modifiers=True)
    print(f"  {os.path.basename(path):<42} {os.path.getsize(path) / 1024:>8.0f} KB")


def select_objects(objects) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]


def main() -> None:
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(root_dir, BLEND))
    scene = bpy.context.scene
    collection = bpy.data.collections[ASSEMBLY_COLLECTION]
    out = os.path.join(root_dir, OUT_DIR)
    os.makedirs(out, exist_ok=True)
    scene.frame_set(DEPLOYED_FRAME)
    bpy.context.view_layer.update()

    # Animated, coloured presentation asset. The support's root/rod actions are
    # preserved by glTF's animation exporter; the source cart is not selected.
    assembly_objects = list(collection.objects)
    select_objects(assembly_objects)
    glb = os.path.join(out, "hcd_foldable_lean_rest.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB",
                              use_selection=True, export_animations=True,
                              export_cameras=False, export_lights=False)
    print(f"  {os.path.basename(glb):<42} {os.path.getsize(glb) / 1024:>8.0f} KB")

    # Snapshot world matrices at the deployed pose, detach the geometry, and
    # shift it to the lower hinge origin for clean, standalone STL files. This
    # is an export-only in-memory transform; the saved .blend is untouched.
    mesh_objects = [obj for obj in assembly_objects if obj.type == "MESH"]
    root = bpy.data.objects["HCD_Fold_Root"]
    origin = root.matrix_world.translation.copy()
    world_matrices = {obj: obj.matrix_world.copy() for obj in mesh_objects}
    for obj in mesh_objects:
        obj.parent = None
    shift = Matrix.Translation(-origin)
    for obj, matrix in world_matrices.items():
        obj.matrix_world = shift @ matrix
    bpy.context.view_layer.update()

    panel = bpy.data.objects["HCD_Rest_Panel_Shell"]
    cushion = bpy.data.objects["HCD_Rest_Cushion"]
    all_meshes = mesh_objects
    select_objects(all_meshes)
    stl_export(os.path.join(out, "hcd_foldable_lean_rest_deployed_mm.stl"))

    select_objects([panel])
    stl_export(os.path.join(out, "hcd_rest_panel_shell_mm.stl"))
    select_objects([cushion])
    stl_export(os.path.join(out, "hcd_rest_cushion_mm.stl"))
    hardware = [obj for obj in all_meshes if obj not in (panel, cushion)]
    select_objects(hardware)
    stl_export(os.path.join(out, "hcd_fold_hardware_deployed_mm.stl"))
    print(f"\nExports written to {OUT_DIR}")
    print("STLs use millimetres and the deployed pose. Prototype fit/layout only.")


if __name__ == "__main__":
    main()
