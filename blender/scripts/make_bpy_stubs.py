#!/usr/bin/env python3
"""Generate stub shared libraries so Blender's Python module (``bpy``) can be
imported on a headless Linux box that has no X11 / OpenGL runtime installed.

Why this exists
---------------
``bpy`` links against libXrender / libXi / libXfixes / libxkbcommon / libSM /
libICE / libGL. On a minimal container those files are absent, so
``import bpy`` dies with ``ImportError: libXrender.so.1: cannot open shared
object file``. Blender is only ever run in background mode here (no window is
ever opened), so those entry points are never actually called -- they just have
to *exist* for the dynamic linker.

This script inspects the real undefined symbols in Blender's binaries and
compiles a tiny ``return 0`` stub for each one, producing .so files with the
SONAMEs the linker is looking for. Symbols are grouped per library, and the
libxkbcommon stub carries a proper ``V_0.5.0`` version script because Blender
references those symbols versioned (an unversioned definition trips an
assertion inside ld.so).

Usage
-----
    python3 make_bpy_stubs.py [output_dir]

    output_dir defaults to $BPY_STUB_DIR or ./bpy-stubs

Then run Blender with the stubs on the library path:

    LD_LIBRARY_PATH=<output_dir> python3 your_script.py

Verified against bpy 5.0.1 (cp311, manylinux_2_28) on Debian 12.
"""

from __future__ import annotations

import glob
import os
import re
import subprocess
import sys

# Blender links these; on a GUI-less box they are missing entirely.
STUB_LIBS = (
    "libXrender.so.1",
    "libXi.so.6",
    "libXfixes.so.3",
    "libxkbcommon.so.0",
    "libSM.so.6",
    "libICE.so.6",
    "libGL.so.1",
)

# Anything the real system libs already provide must NOT be stubbed, otherwise
# the stub would shadow the genuine implementation.
SYSTEM_LIB_GLOBS = (
    "/usr/lib/x86_64-linux-gnu/*.so*",
    "/lib/x86_64-linux-gnu/*.so*",
    "/usr/lib/*/libX11.so*",
)

XKB_VERSION = "V_0.5.0"


def _nm(path: str, mode: str) -> set[str]:
    """Return dynamic symbols from `nm -D [--undefined-only|--defined-only]`."""
    out = subprocess.run(
        ["nm", "-D", mode, path], capture_output=True, text=True, errors="replace"
    ).stdout
    syms: set[str] = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "U":
            syms.add(parts[1])
        elif len(parts) >= 3 and parts[1] == "U":
            syms.add(parts[2])
        elif mode == "--defined-only" and len(parts) >= 3 and parts[1] in "TWtiRrDdBbGgSsVvWw":
            syms.add(parts[2].split("@")[0])
    return syms


def find_bpy() -> str:
    """Locate bpy's compiled extension module."""
    try:
        import bpy  # noqa: F401
    except Exception:
        pass
    for cand in glob.glob(
        os.path.join(os.path.dirname(os.__file__), "..", "**", "bpy", "__init__.so"),
        recursive=True,
    ):
        return os.path.abspath(cand)
    hits = glob.glob("/usr/local/lib/python3*/dist-packages/bpy/__init__.so")
    hits += glob.glob("/usr/lib/python3/dist-packages/bpy/__init__.so")
    if not hits:
        sys.exit("Could not find bpy/__init__.so -- pip install bpy first.")
    return hits[0]


def collect_symbols(bpy_so: str) -> dict[str, set[str]]:
    bpy_root = os.path.dirname(bpy_so)  # .../site-packages/bpy
    targets = [bpy_so] + sorted(glob.glob(os.path.join(bpy_root, "lib", "*.so*")))

    undefined: set[str] = set()
    for tgt in targets:
        try:
            undefined |= _nm(tgt, "--undefined-only")
        except Exception as exc:  # unreadable / stripped file
            print(f"  skip {os.path.basename(tgt)}: {exc}")

    provided: set[str] = set()
    for pattern in SYSTEM_LIB_GLOBS:
        for lib in glob.glob(pattern):
            if os.path.islink(lib) or not os.path.isfile(lib):
                continue
            try:
                provided |= _nm(lib, "--defined-only")
            except Exception:
                pass
    # glibc / libstdc++ symbols carry @GLIBC_2.x version suffixes.
    provided |= {s.split("@")[0] for s in provided}

    missing = {s for s in undefined if s.split("@")[0] not in provided}

    groups: dict[str, set[str]] = {name: set() for name in STUB_LIBS}
    for sym in missing:
        name = sym.split("@")[0]
        if re.match(r"^(gl|GL|glX|GLX|glu|egl|EGL|OSMesa)", name):
            groups["libGL.so.1"].add(name)
        elif name.startswith("xkb_"):
            groups["libxkbcommon.so.0"].add(name)
        elif name.startswith("XFixes"):
            groups["libXfixes.so.3"].add(name)
        elif name.startswith("X") or name.startswith("_Xi"):
            # Belongs to libX11 (present), libXi (missing) or libXt (unused);
            # a no-op stub is harmless because nothing here opens a window.
            groups["libXi.so.6"].add(name)
    return groups


def compile_stubs(groups: dict[str, set[str]], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for lib, syms in groups.items():
        body = (
            "\n".join(f"int {s}(void) {{ return 0; }}" for s in sorted(syms))
            or "int __bpy_stub_dummy(void) { return 0; }"
        )
        src = os.path.join(out_dir, "_stub.c")
        with open(src, "w") as fh:
            fh.write(body + "\n")

        cmd = [
            "gcc", "-shared", "-fPIC", "-o", os.path.join(out_dir, lib),
            f"-Wl,-soname,{lib}", src,
        ]
        if lib == "libxkbcommon.so.0" and syms:
            vscript = os.path.join(out_dir, "_xkb.map")
            with open(vscript, "w") as fh:
                fh.write(f"{XKB_VERSION} {{\n  global:\n")
                fh.write("".join(f"    {s};\n" for s in sorted(syms)))
                fh.write("  local: *;\n};\n")
            cmd.insert(-1, f"-Wl,--version-script={vscript}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"  {lib:<20} {len(syms):>3} symbols")


def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "BPY_STUB_DIR", os.path.join(os.getcwd(), "bpy-stubs")
    )
    bpy_so = find_bpy()
    print(f"bpy module : {bpy_so}")
    print(f"stub dir   : {os.path.abspath(out_dir)}")
    groups = collect_symbols(bpy_so)
    compile_stubs(groups, out_dir)
    print(f"\nDone. Run blender with:\n  LD_LIBRARY_PATH={os.path.abspath(out_dir)} python3 your_script.py")


if __name__ == "__main__":
    main()
