# TYTO compact microphone

An original, independently conceived compact microphone concept, modeled procedurally from scratch in Blender. The design uses a flowing bronze monocoque, a restrained graphite-and-amber front inlay, and a short precision-finished acoustic capsule. The model and all product imagery are Blender/Cycles output; no reference image or AI-generated render is used.

## Deliverables

- `source/tyto_microphone.blend` — editable Blender scene with the complete model, materials, studio setup, five cameras, and turntable animation.
- `build_tyto.py` — reproducible scene builder and render/animation script.
- `renders/tyto_hero.png` — three-quarter studio hero.
- `renders/tyto_front_shell.png` — straight-on product view.
- `renders/tyto_top_spiral.png` — close view of the graphite whorl and amber light detail.
- `renders/tyto_side_profile.png` — side profile showing the swept housing and capsule angle.
- `renders/tyto_knurl_macro.png` — microphone port, woven grille, and diamond-cut retaining ring.
- `animation/tyto_orbit_6s.mp4` — six-second, 24 fps product turntable with a short amber-light reveal.

## Rebuild

With Blender 4.5+ and FFmpeg available (or `imageio-ffmpeg` installed):

```sh
blender -b --python build_tyto.py -- --stills --animation
```

This saves the editable `.blend`, renders five Cycles stills, renders 144 turntable frames, and encodes the MP4. Intermediate animation frames are written under `renders/animation_frames/` and excluded from Git. For a quick visual check, run:

```sh
blender -b --python build_tyto.py -- --preview
```

## Design notes

This is a visual product concept, not a production-ready microphone or acoustically validated design. It intentionally has no logo, text, extra buttons, cable, or hands; the restrained amber light is its only color accent.
