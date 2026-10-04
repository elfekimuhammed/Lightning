"""Locate the one Android CPython header tree unpacked by cibuildwheel."""

from pathlib import Path


matches = sorted(Path("/tmp").glob("cibw-run-*/cp313-android_arm64_v8a/python/**/Python.h"))
if len(matches) != 1:
    raise SystemExit(f"Expected one Android Python.h, found {len(matches)}")
print(matches[0].parent)
