# Blender — shopping-cart leaning cushion

A concept attachment that clips over a supermarket cart's handle and adds a
soft, broad contact surface for a shopper to lean against. The model was built
from the uploaded `hcd mockup.blend`; I inspected the cart mesh and used its
handle as the fit reference before replacing the blue block mock-up with a
parametric two-part assembly.

## Design

| Component | Concept | Model dimensions |
| --- | --- | --- |
| `HCD_Pad` | Soft-touch, ribbed TPE cushion with a snap slot on the underside | 300 × 104 × 116 mm |
| `HCD_Clip` | Rigid PP C-channel; wraps 260° around the tube and projects 10 mm past each pad end | 320 × 30 × 25 mm |
| `HCD_Attachment` | Parent/assembly at the cart handle | On-cart position |

The source cart's handle measures about **23.3 mm diameter × 513 mm long** in
the uploaded model. The design uses a 0.4 mm radial allowance at the handle
and between the clip and cushion. The cart was scaled from the source's
4×-oversized geometry and placed on a ground plane; its handle height is about
1.09 m. `Reference_Mockup` is retained in a hidden collection in the blend file.

The blue pad has subtle circumferential anti-slip ribs and rounded ends. The
rigid clip's flared lips face down so the assembly can be pressed onto the bar
from below. The pad is 300 mm long; the 320 mm clip leaves a small, visible
retaining lip at either end.

> **Prototype only:** the geometry is a visual/fit concept, not a load-rated or
> safety-certified part. It has not been stress-tested or validated for someone
> leaning on it. Before use or production, verify the actual cart-handle size,
> materials, clip retention, deflection, fatigue, hygiene/cleanability, and
> edge safety with physical tests.

## Files

| Path | Contents |
| --- | --- |
| `source/hcd mockup.blend` | Edited Blender scene: cart, HCD assembly, materials, hidden reference, and a hero camera/studio rig |
| `exports/hcd_attachment_mm.stl` | Both parts together, millimetres |
| `exports/hcd_pad_mm.stl` | Cushion only, millimetres |
| `exports/hcd_clip_mm.stl` | Clip only, millimetres |
| `exports/hcd_attachment.glb` | Coloured assembly for preview/viewers |
| `exports/renders/` | Eight studio/cart views and contact sheet |
| `scripts/build_attachment.py` | Parametric rebuild; edit dimensions in its `PARAMS` block |
| `scripts/render_studio.py` | Cycles CPU product views |
| `scripts/export.py` | Re-export STL / GLB files |
| `scripts/report_blend.py` | Object/material/dimension report |
| `scripts/make_bpy_stubs.py` | X11/OpenGL link stubs for headless `bpy` |

## Rebuilding

This environment has no Blender GUI; Blender runs as Python's `bpy` module.
After installing `bpy`, build the headless link stubs once, then run:

```bash
python3 scripts/make_bpy_stubs.py ~/tools/bpy-stubs
export LD_LIBRARY_PATH=$HOME/tools/bpy-stubs
python3 scripts/build_attachment.py
python3 scripts/render_studio.py
python3 scripts/contact_sheet.py
python3 scripts/export.py
```

The build is safe to re-run: it replaces only the generated HCD objects, keeps
the cart and hidden reference, and saves the edited `.blend` in `source/`.
Cycles CPU is used for render previews; EEVEE needs an EGL/OpenGL driver that
is not available in this container.
