# TYTO compact microphone

Reference-guided Blender concept for a compact microphone for a camera hot-shoe or phone rig. The shell proportions, tilted top port, coiled navy inlay, bronze shell, and amber light trace are based on the supplied bronze product render. Product imagery in this folder is rendered by Blender (Cycles), not AI-generated.

## Deliverables

- `source/tyto_microphone.blend` — editable Blender scene, with the procedural shell, recessed port/grille, materials, lights, cameras, and six-second animation controls.
- `build_tyto.py` — reproducible scene builder and render/animation script.
- `renders/tyto_hero.png` — three-quarter studio hero.
- `renders/tyto_front_shell.png` — front shell and spiral detail.
- `renders/tyto_top_spiral.png` — elevated spiral-shell view.
- `renders/tyto_side_profile.png` — side profile.
- `renders/tyto_knurl_macro.png` — microphone port, woven grille, and diamond-knurled collar detail.
- `animation/tyto_orbit_6s.mp4` — six-second, 24 fps camera orbit with an amber LED reveal.
- `references/tyto_bronze_render_reference.png` — supplied visual reference.

## Rebuild

With Blender 4.5+ and an FFmpeg executable available (or `imageio-ffmpeg` installed):

```sh
blender -b --python build_tyto.py -- --stills --animation
```

The script saves the `.blend`, renders five Cycles stills, renders 144 animation frames, and encodes the MP4. Intermediate animation frames are written under `renders/animation_frames/` and excluded from Git.

For background Python using the `bpy` wheel, install `bpy` and `imageio-ffmpeg`, then run `python3 build_tyto.py --stills --animation` from this directory.

## Design notes

The model is a visual product concept—not a production-ready microphone or acoustically validated design. It intentionally has no logo, text, extra buttons, cable, or hands; the amber LED is the only color accent.
