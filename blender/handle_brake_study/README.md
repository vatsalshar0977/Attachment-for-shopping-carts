# Handle-operated rear-brake study

A separate Blender scene focused on a **hand-operated brake lever mounted at
the shopping-cart handle**. Squeezing the lever pulls a Bowden cable down the
frame to an equalizer, which applies shoes at both rear wheels. The hand control
is at the handle; the friction shoes remain at the wheels so they can stop the
cart.

## File and views

- `source/handle_lever_rear_brake.blend` — cart reference, handle lever, cable,
  rear equalizer, applied shoes, and three saved cameras (overview, handle, wheel).
- `exports/renders/handle_brake_study_comparison.png` — overview and two details.
- `exports/renders/` — individual views.
- `scripts/build_handle_brake.py` — builds this file from the supplied cart
  reference without saving over the input.
- `scripts/render_handle_brake.py` and `scripts/contact_sheet.py` — render and
  assemble the preview sheet.

No cost estimate was supplied. This is a concept schematic, not a dimensioned,
load-rated, safety-certified, or physically validated brake. Cable-break
behaviour, shoe force, return springs, caster compatibility, and stopping
performance need qualified engineering review and testing.

## Rebuild

From the repository root with `bpy==5.0.1` and Pillow installed:

```bash
export LD_LIBRARY_PATH=$HOME/tools/bpy-stubs
python3 blender/handle_brake_study/scripts/build_handle_brake.py
python3 blender/handle_brake_study/scripts/render_handle_brake.py
python3 blender/handle_brake_study/scripts/contact_sheet.py
```
