# Foldable cart leaning support — revised AI-render reference

This is a **fresh replacement study** made from the newer AI render and the
original shopping-cart reference. The earlier sketch-proportion model was not
used as the starting point and has not been modified. The product is interpreted
as a padded leaning support, not a seat.

## New model

- `source/foldable_leaning_support.blend` — rounded charcoal cushion, Part A
  open C-clamps with cam levers and indexed pivot mount, and Part B slotted
  telescopic angle strut. It includes the cart as visual context and saved
  overview/component cameras.
- The file opens in the deployed pose. Toggle `POSE — Deployed support` and
  `POSE — Folded panel` in the Outliner to compare the two positions.
- `reference/ai_render_reference.png` — the new reference image.
- `exports/renders/` — deployed and folded overviews, Part A and Part B detail
  views, and a labeled comparison sheet. The cart is hidden only for the two
  close-up detail renders so the clamp and strut are easier to inspect.
- `scripts/build_ai_reference_support.py` — creates the new scene from the
  original cart file; it does not read or save over the earlier support model.
- `scripts/render_ai_reference_support.py` and `scripts/contact_sheet.py` —
  produce the preview renders and comparison sheet.

The render contains no dimensions. The Blender geometry is proportioned to the
cart context for visualization, not claimed to be dimensionally exact or fit-
validated. This is not a load-rated, safety-certified, or physically tested
product. Confirm tube dimensions, clamp strength, pivot locking, pinch clearances,
and panel loads with qualified engineering review before prototyping or use.

## Rebuild

From the repository root with `bpy==5.0.1` and Pillow installed:

```bash
export LD_LIBRARY_PATH=$HOME/tools/bpy-stubs
python3 blender/foldable_support_ai_reference/scripts/build_ai_reference_support.py
python3 blender/foldable_support_ai_reference/scripts/render_ai_reference_support.py
python3 blender/foldable_support_ai_reference/scripts/contact_sheet.py
```
