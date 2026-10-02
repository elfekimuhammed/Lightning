from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_desktop_version_and_one_extract_artifact_agree():
    from lightning import DISPLAY_VERSION, __version__

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["version"] == __version__
    assert DISPLAY_VERSION == __version__.replace("b", "-beta.")
    workflow = (ROOT / ".github" / "workflows" / "desktop-probe.yml").read_text(encoding="utf-8")
    assert "dist/Lightning-windows-x64.zip" in workflow
    assert "dist/APP_SHA256SUMS" in workflow
    assert "name: ${{ env.LIGHTNING_ARTIFACT_NAME }}" in workflow
    assert "dist/LightningProbe-windows-x64.zip" not in workflow


def test_packaging_script_imports_outside_source_directory(tmp_path):
    script = ROOT / "packaging" / "package_app.py"
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import runpy; runpy.run_path({str(script)!r}, run_name='packaging_probe')"],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_profile_acceptance_checks_only_use_temporary_data():
    from lightning.runtime.selfcheck import run_profile_checks
    checks = run_profile_checks()
    assert checks and all(checks.values()), checks


def _packager():
    spec = importlib.util.spec_from_file_location("lightning_package_app", ROOT / "packaging" / "package_app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_app_spec_bundles_application_resources_and_desktop_entry():
    spec = (ROOT / "packaging" / "desktop-app.spec").read_text(encoding="utf-8")
    assert 'root / "desktop_app.py"' in spec
    assert 'collect_data_files("lightning")' in spec
    assert 'collect_data_files("tzdata")' in spec
    for resource in (
        "lightning/ui/templates/profiles.html",
        "lightning/ui/static/profiles.css",
        "lightning/ui/static/fonts/fonts.css",
        "lightning/database/migrations/0001_initial.sql",
    ):
        assert (ROOT / resource).is_file(), resource
    assert 'name="Lightning"' in spec
    assert 'lightning" / "ui" / "static" / "lightning.ico' in spec
    assert (ROOT / "lightning/ui/static/lightning.ico").is_file()


def test_package_guard_rejects_profile_data_and_secrets():
    package_app = _packager()
    for value in (
        Path("profiles/Home.db"),
        Path("backups/old.sqlite3"),
        Path("logs/session.log"),
        Path("keys.json"),
        Path("lightning/private.sqlite"),
        Path("lightning/Home.db-wal"),
        Path(".venv/anything"),
    ):
        assert package_app._is_user_data(value), value
    for value in (
        Path("Lightning.exe"),
        Path("lightning/database/migrations/0001_initial.sql"),
        Path("lightning/ui/static/profiles.css"),
        Path("licenses/dependency-versions.txt"),
    ):
        assert not package_app._is_user_data(value), value


def test_package_stops_before_zipping_any_user_database(tmp_path, monkeypatch):
    package_app = _packager()
    monkeypatch.setattr(package_app, "ROOT", tmp_path)
    monkeypatch.setattr(package_app.importlib.metadata, "distributions", lambda: ())
    bundle = tmp_path / "dist" / "Lightning"
    bundle.mkdir(parents=True)
    (bundle / "Lightning.exe").write_bytes(b"test executable")
    (bundle / "profiles").mkdir()
    (bundle / "profiles" / "Home.db").write_bytes(b"synthetic user data")
    packaging_dir = tmp_path / "packaging"
    packaging_dir.mkdir()
    (packaging_dir / "APP_README.txt").write_text("test", encoding="utf-8")

    try:
        package_app.package()
    except RuntimeError as exc:
        assert "Unexpected user data" in str(exc)
    else:
        raise AssertionError("packager created a ZIP containing profile data")
    assert not (tmp_path / "dist" / "Lightning-windows-x64.zip").exists()


def test_packaged_readme_displays_current_version(tmp_path, monkeypatch):
    from lightning import DISPLAY_VERSION

    package_app = _packager()
    monkeypatch.setattr(package_app, "ROOT", tmp_path)
    monkeypatch.setattr(package_app.importlib.metadata, "distributions", lambda: ())
    bundle = tmp_path / "dist" / "Lightning"
    bundle.mkdir(parents=True)
    (bundle / "Lightning.exe").write_bytes(b"test executable")
    packaging_dir = tmp_path / "packaging"
    packaging_dir.mkdir()
    (packaging_dir / "APP_README.txt").write_text("Lightning v@VERSION@\n", encoding="utf-8")

    package_app.package()

    assert (bundle / "README.txt").read_text(encoding="utf-8") == f"Lightning v{DISPLAY_VERSION}\n"
