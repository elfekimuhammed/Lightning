"""Package the Windows app bundle with dependency notices and its own digest."""
from __future__ import annotations

import hashlib
import importlib.metadata
import shutil
from pathlib import Path

from lightning import DISPLAY_VERSION

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_DIRS = {"data", "profiles", "backups", "logs", ".venv", ".git"}
DATABASE_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm",
    ".sqlite-wal", ".sqlite-shm", ".sqlite3-wal", ".sqlite3-shm", ".partial",
    ".db-journal", ".sqlite-journal", ".sqlite3-journal",
}


def _is_user_data(path: Path) -> bool:
    relative = path
    return (
        any(part.casefold() in FORBIDDEN_DIRS for part in relative.parts)
        or path.name.casefold() == "keys.json"
        or path.suffix.casefold() in DATABASE_SUFFIXES
    )


def package() -> Path:
    bundle = ROOT / "dist" / "Lightning"
    if not (bundle / "Lightning.exe").is_file():
        raise RuntimeError("Missing Windows Lightning executable")

    readme = (ROOT / "packaging" / "APP_README.txt").read_text(encoding="utf-8")
    (bundle / "README.txt").write_text(readme.replace("@VERSION@", DISPLAY_VERSION), encoding="utf-8")
    notices = bundle / "licenses"
    notices.mkdir(exist_ok=True)
    inventory = []
    for dist in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].casefold()):
        name = dist.metadata["Name"]
        inventory.append(f"{name}=={dist.version}")
        for entry in dist.files or ():
            if any(part.casefold().startswith(("license", "copying", "notice")) for part in entry.parts):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    destination = notices / name / Path(*entry.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
    (notices / "dependency-versions.txt").write_text("\n".join(inventory) + "\n", encoding="utf-8")

    # Inspect the staged one-folder bundle before creating a distributable ZIP.
    for path in bundle.rglob("*"):
        if _is_user_data(path.relative_to(bundle)):
            raise RuntimeError(f"Unexpected user data in bundle: {path.relative_to(bundle)}")

    archive = Path(shutil.make_archive(str(ROOT / "dist" / "Lightning-windows-x64"), "zip", bundle.parent, bundle.name))
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    (ROOT / "dist" / "APP_SHA256SUMS").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive


if __name__ == "__main__":
    package()
