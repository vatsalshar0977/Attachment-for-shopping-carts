# Foldable cart-mounted leaning support (sketch study)

A new, separate Blender study based on the user's hand sketch. The interpretation
is a **folding leaning support for the shopping cart**, not a seat for sitting.
The supplied cart model is included only as reference/mounting context; the
sketch contains no dimensions, so the proportions are visual approximations and
are not claims of exact fit or manufacturing scale.

## Model

- `source/foldable_cart_leaning_support.blend` — assembled cart context, split
  handle collars, transverse hinge, ribbed Part A leaning panel, paired
  telescoping Part B lock/support struts, and three saved cameras.
- The scene opens in the **deployed** pose. In the Outliner, toggle
  `POSE — Deployed leaning support` and `POSE — Folded / stowed` to compare the
  two concept states.
- `reference/concept_sketch.jpeg` — the supplied drawing used as the visual
  reference.
- `exports/renders/` — deployed overview, hinge/mount detail, folded view, and
  a labeled comparison sheet.
- `scripts/build_foldable_support.py` — builds this separate scene from
  `blender/source/hcd mockup.blend`; it does not save over the input or any
  existing brake/support project.
- `scripts/render_foldable_support.py` and `scripts/contact_sheet.py` — render
  and assemble the preview views.

This is a concept visualization only. It is not a dimensioned, load-rated,
safety-certified, or fit-validated design. Confirm measurements, attachment
strength, pinch-point clearances, panel loads, and locking behavior with a
qualified engineer before prototyping or use.

## Rebuild

From the repository root with `bpy==5.0.1` and Pillow installed:

```bash
export LD_LIBRARY_PATH=$HOME/tools/bpy-stubs
python3 blender/foldable_cart_support_sketch/scripts/build_foldable_support.py
python3 blender/foldable_cart_support_sketch/scripts/render_foldable_support.py
python3 blender/foldable_cart_support_sketch/scripts/contact_sheet.py
```
