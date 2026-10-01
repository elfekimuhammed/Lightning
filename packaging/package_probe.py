"""Package only the generated probe bundle, with licenses and an SHA-256 digest."""
from __future__ import annotations

import hashlib
import importlib.metadata
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def package() -> None:
    bundle = ROOT / "dist" / "LightningProbe"
    if not (bundle / "LightningProbe.exe").is_file():
        raise RuntimeError("Missing Windows probe executable")
    shutil.copyfile(ROOT / "packaging" / "PROBE_README.txt", bundle / "README.txt")
    notices = bundle / "licenses"
    notices.mkdir(exist_ok=True)
    inventory = []
    for dist in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        inventory.append(f"{name}=={dist.version}")
        for entry in dist.files or ():
            if any(part.lower().startswith(("license", "copying", "notice")) for part in entry.parts):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    destination = notices / name / Path(*entry.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
    (notices / "dependency-versions.txt").write_text("\n".join(inventory) + "\n", encoding="utf-8")
    # Do not let a data directory or developer environment enter a downloadable artifact.
    forbidden = {"data", "backups", "logs", ".venv", ".git"}
    for path in bundle.rglob("*"):
        relative = path.relative_to(bundle)
        if any(part in forbidden for part in relative.parts) or path.name == "keys.json" or path.suffix in {".db", ".sqlite", ".sqlite3"}:
            raise RuntimeError(f"Unexpected data artifact in bundle: {relative}")
    archive = Path(shutil.make_archive(str(ROOT / "dist" / "LightningProbe-windows-x64"), "zip", bundle.parent, bundle.name))
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    (ROOT / "dist" / "SHA256SUMS").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")


if __name__ == "__main__":
    package()
