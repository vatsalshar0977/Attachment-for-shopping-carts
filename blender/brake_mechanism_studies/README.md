# Additional cart-brake mechanism studies (M6–M9)

This is a **separate exploratory Blender project** containing four more brake
concepts on the supplied shopping-cart reference. Each `.blend` file holds the
cart and one grouped mechanism study; these files do not change the original
cart or the earlier M1–M5 alternatives project.

## Concepts

| ID | Mechanism | Schematic idea | Design questions |
| --- | --- | --- | --- |
| M6 | Foot treadle with twin cables | A transverse foot pedal pulls two cables to apply both rear-wheel shoes. | Pedal clearance/guarding, cable adjustment, and release behaviour. |
| M7 | Ratchet ring and spring pawl | A spring-engaged pawl locks a toothed ring at each rear wheel; a handle cable lifts the pawls to release. | Discrete engagement, tooth strength, guarding, and bidirectional holding. |
| M8 | Hydraulic master cylinder and twin calipers | A handle lever pressurizes a master cylinder and two rear calipers acting on small rotors. | Seals, bleeding, hose routing, maintenance, and caster/rotor packaging. |
| M9 | External band brake on rear drums | A lever tightens flexible friction bands around dedicated small drums at both rear wheels. | Drum clearance, dirt, wear adjustment, heat, and caster packaging. |

No costs or extra notes were supplied for these four concepts, so this project
adds **no price estimates**. The questions above are exploratory design prompts,
not verified engineering conclusions.

## Files

- `source/M6_foot_treadle_cable.blend`
- `source/M7_ratchet_pawl_lock.blend`
- `source/M8_hydraulic_dual_caliper.blend`
- `source/M9_external_band_brake.blend`
- `exports/renders/` — one focused render per concept and a four-up comparison.
- `scripts/build_additional_mechanisms.py` — builds all four separate scenes
  from `blender/source/hcd mockup.blend` without saving over the input.
- `scripts/render_additional_mechanisms.py` and `scripts/contact_sheet.py` —
  render and assemble the preview sheet.

**All geometry is schematic only.** These concepts are not dimensioned for
manufacture, load-rated, safety-certified, or validated on a physical cart.
None should be treated as a working brake or built without qualified engineering
review, prototyping, and testing. In particular, the ratchet, hydraulic, and
band-brake concepts require detailed checks of locking behaviour, load paths,
wear, and failure modes.

## Rebuild

From the repository root with `bpy==5.0.1` and Pillow installed:

```bash
export LD_LIBRARY_PATH=$HOME/tools/bpy-stubs
python3 blender/brake_mechanism_studies/scripts/build_additional_mechanisms.py
python3 blender/brake_mechanism_studies/scripts/render_additional_mechanisms.py
python3 blender/brake_mechanism_studies/scripts/contact_sheet.py
```
