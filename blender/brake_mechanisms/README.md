# Cart brake mechanism alternatives

A separate, schematic comparison scene for five alternative rear-brake
mechanisms on the supplied shopping-cart reference. The existing leaning-rest
and stackable-iteration files are not modified. In the Blender scene, each
alternative is a separate `BRK Variant ...` collection at the same cart
location; toggle collections in the Outliner to compare them. The common red
brake shoes are shown in the applied position.

## Comparison

Costs and notes below are reproduced from the user-provided estimates; they
have not been independently quoted or validated.

| # | Mechanism | How it works | Notes | Estimate per cart |
| ---: | --- | --- | --- | ---: |
| 1 | Spring-applied cable with dead-man grip | Holding the grip pulls a cable to release the brake; opening the grip lets springs apply it. | Fail-safe intent: a cable break should remove release force so the cart locks. This depends on the actual spring/brake geometry and needs testing. | ₹150–300 |
| 2 | Push-rod with bell cranks | Rigid rods run along the frame and actuate a bell crank at each rear caster. | Stiff with little stretch; needs protected routing room and joints. | ₹300–500 |
| 3 | Over-centre toggle lever on the handle | The lever passes dead centre and bears against a stop, holding the locked state without continuous force. | Needs a positive stop and guarding around the toggle/pinch points. | ₹200–400 |
| 4 | Pad-linked lock | Loading the leaning pad pushes a plunger that keeps the brake latch applied. | Prevents the brake releasing during a lean; linkage must not create a misleading safe state. | ₹100–200 |
| 5 | Cross-bar cam lock | One bar across the rear axle rotates cams that press both brake shoes. | Locks both rear wheels together. No cost or extra notes were supplied. | Not supplied |

## Files

- `source/cart brake alternatives.blend` — cart reference, shared shoes, five
  toggleable mechanism collections, and a camera/light setup.
- `exports/renders/` — five full-system views, focused detail renders, and
  labeled overview/detail comparison sheets.
- `scripts/build_brake_mechanisms.py` — rebuilds this separate scene from the
  supplied cart file without saving over it.
- `scripts/render_brake_mechanisms.py` — renders each alternative and selected
  handle, pad, or rear-wheel details.
- `scripts/contact_sheet.py` — builds the labeled overview and detail sheets.

The geometry is **schematic only**: it is not dimensioned for manufacture,
load-rated, safety-certified, or verified on a physical cart. A qualified
engineer should define the braking force, fail-safe state, caster compatibility,
actuation effort, and tests before any prototype is used. In particular, the
spring-applied/cable-break behavior must be verified rather than assumed.

## Rebuild

From the repository root with `bpy==5.0.1` and Pillow installed:

```bash
export LD_LIBRARY_PATH=$HOME/tools/bpy-stubs
python3 blender/brake_mechanisms/scripts/build_brake_mechanisms.py
python3 blender/brake_mechanisms/scripts/render_brake_mechanisms.py
python3 blender/brake_mechanisms/scripts/contact_sheet.py
```
