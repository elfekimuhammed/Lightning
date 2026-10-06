"""Locate the one Android CPython header tree unpacked by cibuildwheel."""

import sys
from pathlib import Path


matches = sorted(Path("/tmp").glob("cibw-run-*/cp313-android_arm64_v8a/python/**/Python.h"))
if len(matches) != 1:
    raise SystemExit(f"Expected one Android Python.h, found {len(matches)}")
# "lib": the folder holding libpython3.13.so (prefix/lib), which extension modules must link on Android.
print(matches[0].parent.parent.parent / "lib" if sys.argv[1:] == ["lib"] else matches[0].parent)
