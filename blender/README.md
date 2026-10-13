# blender/

Home for the Blender work in this repo (the shopping-cart attachment model).

## Layout

| Path              | What goes here                                              |
| ----------------- | ----------------------------------------------------------- |
| `source/`         | The `.blend` file(s). This is what gets edited.             |
| `scripts/`        | Python (`bpy`) scripts used to make the edits reproducibly. |
| `exports/`        | Exported geometry (glTF / OBJ / STL) for use elsewhere.     |

Edits are done headlessly with Blender's Python module (`bpy`), so every change
to `source/*.blend` has a matching script in `scripts/` that can be re-run.
