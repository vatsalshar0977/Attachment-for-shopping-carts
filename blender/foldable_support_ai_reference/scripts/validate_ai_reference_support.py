#!/usr/bin/env python3
"""Structural checks for the AI-render-reference Blender study."""

from pathlib import Path

import bpy

REPO = Path(__file__).resolve().parents[3]
PROJECT = REPO / "blender/foldable_support_ai_reference"
BLEND = PROJECT / "source/foldable_leaning_support.blend"
RENDERS = PROJECT / "exports/renders"
REQUIRED_COLLECTIONS = (
    "AI-render reference assembly",
    "PART A — Tube clamp and pivot mount",
    "POSE — Deployed support",
    "POSE — Folded panel",
    "Part B — Slotted telescopic support",
    "Part B — Folded telescopic support",
)
REQUIRED_OBJECTS = (
    "Shopping Cart",
    "AIREF_Deployed_Panel_Shell",
    "AIREF_Deployed_Soft_Pad",
    "AIREF_Deployed_Hinge_Barrel",
    "AIREF_PartA_Handle_Clamp_1_C_Strap",
    "AIREF_PartA_Handle_Clamp_1_Quick_Release_Lever",
    "AIREF_PartB_Outer_Telescopic_Tube",
    "AIREF_PartB_Inner_Sliding_Rod",
    "AIREF_PartB_Adjustment_Slot",
    "AIREF_Camera_Overview",
    "AIREF_Camera_PartA_Clamp_Detail",
    "AIREF_Camera_PartB_Strut_Detail",
    "AIREF_Camera_Folded_Overview",
)
REQUIRED_RENDERS = (
    "deployed_overview.png",
    "part_a_clamp_detail.png",
    "part_b_strut_detail.png",
    "folded_overview.png",
    "ai_reference_support_comparison.png",
)


def main():
    if not BLEND.exists():
        raise FileNotFoundError(BLEND)
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    missing_collections = [name for name in REQUIRED_COLLECTIONS if bpy.data.collections.get(name) is None]
    missing_objects = [name for name in REQUIRED_OBJECTS if bpy.data.objects.get(name) is None]
    missing_renders = [name for name in REQUIRED_RENDERS if not (RENDERS / name).is_file()]
    assert not missing_collections, f"Missing collections: {missing_collections}"
    assert not missing_objects, f"Missing objects: {missing_objects}"
    assert not missing_renders, f"Missing renders: {missing_renders}"
    assert bpy.context.scene["Use"] == "Leaning support only — not a seat"
    assert bpy.context.scene["Status"] == "Not fit-validated, load-rated, or safety-certified"
    assert not bpy.data.collections["POSE — Deployed support"].hide_render
    assert bpy.data.collections["POSE — Folded panel"].hide_render
    assert bpy.data.objects["Shopping Cart"].type == "MESH"
    print(f"Validated readable Blender scene: {BLEND}")
    print(f"  objects: {len(bpy.data.objects)}")
    print(f"  collections: {len(bpy.data.collections)}")
    print(f"  renders: {len(REQUIRED_RENDERS)} present")


if __name__ == "__main__":
    main()
