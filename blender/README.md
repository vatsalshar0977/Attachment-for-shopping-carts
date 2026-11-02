# Blender — fold-out shopping-cart leaning support

This revision replaces the original handle-only pad concept with a broad,
padded **leaning support** based on the user's sketch. It swings down behind
(and just below) the cart handle for use, then folds inward and lies inside the
basket opening for storage. It is not a seat: it is designed as a back/leaning
surface, and must not be used for sitting.

The attachment was built on the supplied `hcd mockup.blend`. The cart mesh was
inspected and normalized as the fit reference; its handle measures about
**23.3 mm diameter × 513 mm long**, at roughly **1.09 m** above the ground.

## Design and animation

| Component | Concept | Approximate size |
| --- | --- | --- |
| `HCD_Rest_Panel_Shell` | Rounded, stiff-looking backing plate | 460 × 270 × 26 mm |
| `HCD_Rest_Cushion` | Continuous soft-touch contact face with subtle horizontal texture | 430 × 238 × 60 mm |
| `HCD_Drop_Bracket_Left/Right` | Pair of handle clamps and drop links positioning the lower hinge axis over the basket rim | Cart-specific fit |
| `HCD_Hinge_*` | Paired pivot ears, pins, and conceptual two-position release tabs | Cart-specific fit |
| `HCD_Stay_*` | Two telescoping side stays that brace the deployed support and retract as it folds | About 117 mm deployed; 282 mm stowed |

The assembly is animated in the Blender timeline:

- **Frame 1 — deployed:** the broad cushion faces the shopper as a leaning rest.
- **Frame 18 — mid-fold:** the panel and telescoping stays move inward.
- **Frame 35 — stowed:** the panel lies horizontally within the top of the cart basket.

The lower pivot is carried by drop brackets that clamp to the measured handle.
The stays attach to the rear basket sides and telescope as the panel rotates.
This models a plausible fold path for visualization; it does not validate a
real hinge, lock, cart fit, or load path.

> **Prototype only:** this is a visual/fit concept, not load-rated or
> safety-certified. Do not sit on it, and do not rely on it for body support
> before physical engineering and testing. Verify the actual cart geometry,
> attachment retention, hinge/lock strength, telescoping stays, material
> selection, clearances, hygiene/cleanability, and leaning loads. A qualified
> engineer must establish a safe working load and test the physical prototype.

## Files

| Path | Contents |
| --- | --- |
| `source/hcd mockup.blend` | Source scene with cart, fold-out support, materials, animation, and inspection camera/lights |
| `exports/hcd_foldable_lean_rest.glb` | Coloured, animated GLB preview of the attachment |
| `exports/hcd_foldable_lean_rest_deployed_mm.stl` | Deployed assembly geometry in millimetres, origin at the lower hinge axis |
| `exports/hcd_rest_panel_shell_mm.stl` | Backing plate only, millimetres |
| `exports/hcd_rest_cushion_mm.stl` | Cushioned face only, millimetres |
| `exports/hcd_fold_hardware_deployed_mm.stl` | Deployed hinge, clamp, bracket, and telescoping-stay geometry, millimetres |
| `exports/renders/` | Deployed, mid-fold, and stowed render views plus contact sheet |
| `scripts/build_attachment.py` | Rebuild the foldable support on the supplied cart |
| `scripts/render_studio.py` | Render deployed and stowed Cycles CPU views |
| `scripts/contact_sheet.py` | Tile the views for review |
| `scripts/export.py` | Re-export animated GLB and static STLs |
| `scripts/report_blend.py` | Object/material/dimension report |
| `scripts/make_bpy_stubs.py` | Headless `bpy` runtime link-stub helper |

The exported STL files are static geometry at frame 1; they do not contain the
fold animation and are for fit/layout review only. The GLB carries the animated
assembly but does not include the cart reference.

## Rebuilding

From the repository root, with `bpy==5.0.1` installed, run:

```bash
python3 blender/scripts/make_bpy_stubs.py ~/tools/bpy-stubs
export LD_LIBRARY_PATH=$HOME/tools/bpy-stubs
python3 blender/scripts/build_attachment.py
python3 blender/scripts/render_studio.py
python3 blender/scripts/contact_sheet.py
python3 blender/scripts/export.py
```

The build is safe to re-run: it replaces generated HCD objects while retaining
the supplied cart reference and saves the updated `.blend`. Cycles CPU is used
for render previews because this headless environment has no EGL/OpenGL driver.
