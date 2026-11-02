#!/usr/bin/env python3
"""Export the separate stackable iteration as an animated GLB and deployed STL."""

from __future__ import annotations

from pathlib import Path

import bpy
from mathutils import Matrix

REPO = Path(__file__).resolve().parents[3]
BLEND = REPO / "blender/stackable_iteration/source/stackable leaning support.blend"
OUT = REPO / "blender/stackable_iteration/exports"
COLLECTION = "HCD - Stackable Iteration"


def select(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]


def export_stl(path: Path):
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True,
                              global_scale=1000.0, apply_modifiers=True)
    else:
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True,
                                global_scale=1000.0, use_mesh_modifiers=True)
    print(f"  {path.name}: {path.stat().st_size / 1024:.0f} KB")


def main():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    OUT.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    assembly = list(bpy.data.collections[COLLECTION].objects)
    scene.frame_set(1)
    bpy.context.view_layer.update()

    select(assembly)
    glb = OUT / "hcd_stackable_lean_rest.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB",
                              use_selection=True, export_animations=True,
                              export_cameras=False, export_lights=False)
    print(f"  {glb.name}: {glb.stat().st_size / 1024:.0f} KB (animation included)")

    meshes = [obj for obj in assembly if obj.type == "MESH"]
    moving_root = bpy.data.objects["HCD_Stackable_Fold_Root"]
    origin = moving_root.matrix_world.translation.copy()
    worlds = {obj: obj.matrix_world.copy() for obj in meshes}
    for obj in meshes:
        obj.parent = None
    translate = Matrix.Translation(-origin)
    for obj, matrix in worlds.items():
        obj.matrix_world = translate @ matrix
    bpy.context.view_layer.update()
    select(meshes)
    export_stl(OUT / "hcd_stackable_lean_rest_deployed_mm.stl")
    print("STL is static at deployed frame 1, in millimetres; not load-rated/manufacturing validated.")


if __name__ == "__main__":
    main()
