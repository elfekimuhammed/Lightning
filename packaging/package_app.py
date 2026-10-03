"""Package the Windows app bundle: licence notices for what it ships, its build identity, and a ZIP
with its SHA-256 digest.

    python packaging/package_app.py            # a local build
    python packaging/package_app.py --strict   # CI: every required notice must be found

Release, development and local builds are told apart by GitHub's environment variables:
- a tag build (GITHUB_REF_TYPE=tag) must be tagged v<DISPLAY_VERSION> and makes
  Lightning-v<version>-Windows-x64.zip, the name a published release carries;
- any other CI build makes Lightning-v<version>-dev-r<run>-<commit>-Windows-x64.zip, so a test build
  can never be mistaken for, or published as, the release;
- a build outside CI keeps the plain versioned name.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import platform
import re
import shutil
import sys
import sysconfig
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # Script execution on Windows starts with packaging/ on sys.path.
from lightning import DISPLAY_VERSION

SOURCE = ROOT  # where pyproject.toml lives; tests point ROOT at a scratch folder, not this
# The app's runtime packages: pyproject's dependencies plus these extras. Build and test tools
# (PyInstaller, pytest, import-linter, httpx…) are not shipped, so their licences are not listed.
RUNTIME_EXTRAS = ("encrypted", "desktop")
FORBIDDEN_DIRS = {"data", "profiles", "backups", "logs", ".venv", ".git"}
DATABASE_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm",
    ".sqlite-wal", ".sqlite-shm", ".sqlite3-wal", ".sqlite3-shm", ".partial",
    ".db-journal", ".sqlite-journal", ".sqlite3-journal",
}
_NOTICE = re.compile(r"^(licen[cs]e|copying|notice|authors)", re.IGNORECASE)
# The Python minor version that packaging/notices/Python-<minor>-incorporated-software.txt describes.
NOTICED_PYTHON = "3.13"


def _is_user_data(path: Path) -> bool:
    relative = path
    return (
        any(part.casefold() in FORBIDDEN_DIRS for part in relative.parts)
        or path.name.casefold() == "keys.json"
        or path.suffix.casefold() in DATABASE_SUFFIXES
    )


# ---------------------------------------------------------------- build identity
def build_identity(env=os.environ) -> dict[str, str]:
    """What this build is: its kind, ZIP and artifact names, and where it came from."""
    sha = env.get("GITHUB_SHA", "")
    run, attempt = env.get("GITHUB_RUN_NUMBER", ""), env.get("GITHUB_RUN_ATTEMPT", "1")
    built = datetime.now(timezone.utc).replace(microsecond=0)
    release_name = f"Lightning-v{DISPLAY_VERSION}-Windows-x64"
    if env.get("GITHUB_REF_TYPE") == "tag":
        tag = env.get("GITHUB_REF_NAME", "")
        if tag != f"v{DISPLAY_VERSION}":
            raise RuntimeError(f"Tag {tag!r} does not match the source version v{DISPLAY_VERSION}")
        kind, archive, artifact = f"release {tag}", release_name, release_name
    elif sha:
        stamp = f"r{run or 0}-{sha[:8]}"
        kind = "development (not a release)"
        archive = f"Lightning-v{DISPLAY_VERSION}-dev-{stamp}-Windows-x64"
        artifact = f"Lightning-v{DISPLAY_VERSION}-dev-{built:%Y-%m-%d}-{stamp}-a{attempt}-Windows-x64"
    else:
        kind, archive, artifact = "local", release_name, release_name
    return {
        "version": DISPLAY_VERSION, "kind": kind, "archive": archive, "artifact": artifact,
        "commit": sha or "unknown (local build)",
        "run": f"workflow run {run}, attempt {attempt}" if run else "local build",
        "built": built.isoformat().replace("+00:00", "Z"),
        "python": platform.python_version(), "platform": f"{platform.system()} {platform.machine()}",
    }


def build_info_text(identity: dict[str, str]) -> str:
    return (f"Lightning {identity['version']} for Windows x64\n"
            f"Build: {identity['kind']}\n"
            f"Commit: {identity['commit']}\n"
            f"Run: {identity['run']}\n"
            f"Built: {identity['built']}\n"
            f"Python: {identity['python']} ({identity['platform']})\n")


# ---------------------------------------------------------------- notices
def runtime_distributions() -> tuple[list[importlib.metadata.Distribution], list[str]]:
    """The installed distributions the app runs on (its runtime requirements, followed through
    their own requirements with environment markers evaluated for this machine), and any that a
    requirement names but are not installed."""
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    project = tomllib.loads((SOURCE / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    wanted = [(Requirement(text), "") for text in project.get("dependencies", [])]
    for extra in RUNTIME_EXTRAS:
        wanted += [(Requirement(text), "") for text in project.get("optional-dependencies", {}).get(extra, [])]
    found: dict[str, importlib.metadata.Distribution] = {}
    missing: list[str] = []
    while wanted:
        requirement, extra = wanted.pop()
        if requirement.marker and not requirement.marker.evaluate({"extra": extra}):
            continue
        name = canonicalize_name(requirement.name)
        if name in found:
            continue
        try:
            dist = importlib.metadata.distribution(requirement.name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(requirement.name)
            continue
        found[name] = dist
        for text in dist.requires or ():
            child = Requirement(text)
            # Follow a child requirement without an extra, or one gated on an extra we asked for.
            for chosen in {""} | set(requirement.extras):
                if not child.marker or child.marker.evaluate({"extra": chosen}):
                    wanted.append((child, chosen))
                    break
    return sorted(found.values(), key=lambda d: canonicalize_name(d.metadata["Name"])), sorted(set(missing))


def python_licence() -> Path | None:
    """CPython's own LICENSE (on Windows it also carries the bundled OpenSSL, SQLite, libffi… notices)."""
    for folder in (Path(sys.base_prefix), Path(sysconfig.get_paths()["stdlib"])):
        for name in ("LICENSE.txt", "LICENSE"):
            if (folder / name).is_file():
                return folder / name
    return None


def _copy_licence_files(dist: importlib.metadata.Distribution, folder: Path) -> int:
    copied = 0
    for entry in dist.files or ():
        if any(_NOTICE.match(part) for part in entry.parts):
            source = Path(dist.locate_file(entry))
            if source.is_file():
                destination = folder / Path(*entry.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                copied += 1
    return copied


def write_notices(bundle: Path, strict: bool) -> list[str]:
    """Copy into licenses/ the licence files of every shipped distribution, Python's licence, the
    vendored notices in packaging/notices/ (code linked into extension modules: SQLCipher, OpenSSL,
    the WebView2 SDK, .NET facades) and PyInstaller's licence (its loader runs the app), and list the
    versions. Returns the problems found; in strict mode any problem stops the build."""
    from packaging.utils import canonicalize_name

    notices = bundle / "licenses"
    if notices.exists():
        shutil.rmtree(notices)
    notices.mkdir()
    vendored = SOURCE / "packaging" / "notices"
    problems: list[str] = []
    dists, missing = runtime_distributions()
    problems += [f"runtime requirement {name} is not installed" for name in missing]
    inventory = [f"Python=={platform.python_version()}"]
    for dist in dists:
        name = dist.metadata["Name"]
        inventory.append(f"{name}=={dist.version}")
        copied = _copy_licence_files(dist, notices / name)
        stand_in = vendored / f"{canonicalize_name(name)}-LICENSE.txt"
        if not copied and stand_in.is_file():  # e.g. proxy-tools, whose source distribution has none
            (notices / name).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(stand_in, notices / name / "LICENSE.txt")
            copied = 1
        if not copied:
            problems.append(f"{name} {dist.version} ships no licence file "
                            f"(add packaging/notices/{canonicalize_name(name)}-LICENSE.txt)")
    python = python_licence()
    if python is None:
        problems.append("Python's LICENSE file was not found")
    else:
        (notices / "Python").mkdir()
        shutil.copyfile(python, notices / "Python" / "LICENSE.txt")
    minor = ".".join(platform.python_version_tuple()[:2])
    if minor != NOTICED_PYTHON:
        problems.append(f"packaging/notices describes Python {NOTICED_PYTHON}, but this build uses Python {minor}: "
                        "refresh Python-<minor>-incorporated-software.txt from CPython's Doc/license.rst")
    third_party = notices / "third-party"
    third_party.mkdir()
    texts = [source for source in sorted(vendored.glob("*.txt")) if source.name != "README.txt"]
    if not texts:
        problems.append("packaging/notices holds no third-party notices")
    for source in texts:
        shutil.copyfile(source, third_party / source.name)
    try:
        pyinstaller = importlib.metadata.distribution("pyinstaller")
    except importlib.metadata.PackageNotFoundError:
        problems.append("PyInstaller is not installed, so its licence cannot be included")
    else:
        inventory.append(f"pyinstaller=={pyinstaller.version} (bootloader and loader)")
        if not _copy_licence_files(pyinstaller, notices / "PyInstaller"):
            problems.append("PyInstaller ships no licence file")
    (notices / "dependency-versions.txt").write_text("\n".join(inventory) + "\n", encoding="utf-8")
    if strict and problems:
        raise RuntimeError("Licence notices are incomplete: " + "; ".join(problems))
    return problems


# ---------------------------------------------------------------- package
def package(strict: bool = False, env=os.environ) -> Path:
    bundle = ROOT / "dist" / "Lightning"
    if not (bundle / "Lightning.exe").is_file():
        raise RuntimeError("Missing Windows Lightning executable")
    identity = build_identity(env)

    readme = (ROOT / "packaging" / "APP_README.txt").read_text(encoding="utf-8")
    (bundle / "README.txt").write_text(readme.replace("@VERSION@", DISPLAY_VERSION), encoding="utf-8")
    info = build_info_text(identity)
    (bundle / "BUILD_INFO.txt").write_text(info, encoding="utf-8", newline="\n")
    for problem in write_notices(bundle, strict):
        print(f"warning: {problem}", file=sys.stderr)

    # Inspect the staged one-folder bundle before creating a distributable ZIP.
    for path in bundle.rglob("*"):
        if _is_user_data(path.relative_to(bundle)):
            raise RuntimeError(f"Unexpected user data in bundle: {path.relative_to(bundle)}")

    dist = ROOT / "dist"
    for old in (*dist.glob("Lightning-v*-Windows-x64.zip"), dist / "APP_SHA256SUMS", dist / "BUILD_INFO.txt"):
        old.unlink(missing_ok=True)  # never upload a ZIP left over from an earlier build
    archive = Path(shutil.make_archive(str(dist / identity["archive"]), "zip", bundle.parent, bundle.name))
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    # "\n" on every platform: the release job checks these files with Linux tools.
    (dist / "APP_SHA256SUMS").write_text(f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n")
    (dist / "BUILD_INFO.txt").write_text(info, encoding="utf-8", newline="\n")

    output = env.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"zip={archive.name}\nartifact={identity['artifact']}\n")
    print(f"Packaged {archive.name} ({identity['kind']}), SHA-256 {digest}")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="fail when a licence notice is missing")
    package(strict=parser.parse_args().strict)
