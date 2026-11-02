# Stackable fold-path iteration

This is a **separate iteration** of the shopping-cart leaning support. It reads
`blender/source/hcd mockup.blend` as its cart reference, but writes its scene,
exports, scripts, and renders only inside `blender/stackable_iteration/`. The
previous Blender file and its exports are left untouched.

## Fold path

I interpreted the request as: while in use, the padded panel hangs below the
handle; to stow, it swings up and over the handle, passes above the rear basket
rim, then lowers upright into the cart's rear child-seat plane. Unlike the
previous version, it does **not** lie across the top of the basket. The carrier
arms telescope between the handle and the moving panel pivot.

| Frame | Pose |
| ---: | --- |
| 1 | Deployed, cushioned face toward the shopper |
| 8 | Panel swings up over the handle |
| 16–22 | Panel travels above the basket mouth |
| 29–35 | Panel rests upright in the child-seat area, leaving the basket top open |

The cart mesh has a child-seat/rear-frame zone; the final panel is positioned
parallel to that area. This is a **visual stackability concept**, not proof that
real carts will nest. Verify clearances, the carrier/hinge mechanics, child-seat
operation, and full cart nesting with a physical prototype before use.

> The panel remains a **leaning support, not a seat**. This concept is not
> load-rated or safety-certified. Do not sit or lean on a physical version until
> a qualified engineer has designed and validated its attachment and load path.

## Files in this folder

- `source/stackable leaning support.blend` — new scene, cart reference, model,
  and keyed fold path.
- `exports/hcd_stackable_lean_rest.glb` — animated attachment preview.
- `exports/hcd_stackable_lean_rest_deployed_mm.stl` — static deployed geometry
  in millimetres; fit/layout review only.
- `exports/renders/` — individual key-pose renders and a contact sheet.
- `scripts/build_stackable_iteration.py` — rebuilds this scene without writing
  to the prior `.blend`.
- `scripts/render_stackable.py` — renders the separate scene's animation poses.
- `scripts/export_stackable.py` — exports the animated GLB and deployed STL.
- `scripts/contact_sheet.py` — creates the image overview.

## Rebuild

From the repository root with `bpy==5.0.1` and Pillow installed (`python3 -m pip install Pillow`):

```bash
export LD_LIBRARY_PATH=$HOME/tools/bpy-stubs
python3 blender/stackable_iteration/scripts/build_stackable_iteration.py
python3 blender/stackable_iteration/scripts/render_stackable.py
python3 blender/stackable_iteration/scripts/contact_sheet.py
python3 blender/stackable_iteration/scripts/export_stackable.py
```
