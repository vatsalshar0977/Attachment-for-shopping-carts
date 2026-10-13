# blender/

Home for the Blender work in this repo: the shopping-cart handle attachment
(a cushioned pad that clips onto the handle so users can lean on it
comfortably).

## Layout

| Path              | What goes here                                              |
| ----------------- | ----------------------------------------------------------- |
| `source/`         | The `.blend` file(s). This is what gets edited.             |
| `scripts/`        | Python (`bpy`) scripts used to make the edits reproducibly. |
| `exports/`        | Exported geometry (glTF / OBJ / STL) for use elsewhere.     |

Every change to `source/*.blend` has a matching script in `scripts/`, so any
edit can be re-run or reverted by editing numbers in one place.

## Running Blender here

There is no GUI in this environment, so Blender runs as a Python module
(`bpy`) in background mode.

```bash
pip install bpy                                  # Blender as a Python module
python3 scripts/make_bpy_stubs.py ~/tools/bpy-stubs
LD_LIBRARY_PATH=$HOME/tools/bpy-stubs python3 scripts/<your_script>.py
```

`make_bpy_stubs.py` builds the handful of X11/OpenGL stub libraries that
Blender's binaries link against but never call in background mode — without
them `import bpy` fails on a machine with no X server. See the docstring in
that script for the details.

### Rendering

Cycles works with the CPU device and is used for all preview renders:

```python
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
```

EEVEE and Workbench are unavailable here: they need a real OpenGL/EGL driver
(`libEGL.so.1`), which this box does not have.
