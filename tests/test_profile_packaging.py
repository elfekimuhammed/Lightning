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
    assert "dist/Lightning-v*-Windows-x64.zip" in workflow
    assert "branches: [main]" in workflow and "tags: ['v*']" in workflow
    assert "dist/APP_SHA256SUMS" in workflow
    assert "name: ${{ steps.package.outputs.artifact }}" in workflow
    assert "dist/LightningProbe-windows-x64.zip" not in workflow


def test_workflow_ships_only_what_passed_the_full_suite_and_its_own_checks():
    """The Windows build waits for the full suite; the ZIP that is uploaded is the one that was
    extracted and checked; a release needs the Windows job and publishes that same artifact."""
    import re

    workflow = (ROOT / ".github" / "workflows" / "desktop-probe.yml").read_text(encoding="utf-8")
    jobs = workflow.split("\njobs:\n", 1)[1]
    windows = jobs.split("\n  windows:\n", 1)[1].split("\n  release:\n", 1)[0]
    release = jobs.split("\n  release:\n", 1)[1]
    assert "needs: tests" in windows and "needs.tests.outputs.build_windows == 'true'" in windows
    steps = windows.index
    assert steps("package_app.py --strict") < steps("Expand-Archive") < steps("-Arguments '--self-check'",
                                                                            steps("Expand-Archive"))
    assert steps("steps.shipped.outputs.exe") < steps("actions/upload-artifact")
    assert "needs: [tests, windows]" in release and "startsWith(github.ref, 'refs/tags/v')" in release
    assert "needs.windows.outputs.artifact" in release and "publish_release.sh" in release
    assert "secrets.LIGHTNING_DOWNLOADS_TOKEN" in release
    # Every third-party action is pinned to a full commit.
    for action in re.findall(r"uses: ([^\s]+)", workflow):
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", action), action


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
        package_app.package(env={})
    except RuntimeError as exc:
        assert "Unexpected user data" in str(exc)
    else:
        raise AssertionError("packager created a ZIP containing profile data")
    assert not list((tmp_path / "dist").glob("Lightning-v*-Windows-x64.zip"))


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

    package_app.package(env={})

    assert (bundle / "README.txt").read_text(encoding="utf-8") == f"Lightning v{DISPLAY_VERSION}\n"
    assert (tmp_path / "dist" / f"Lightning-v{DISPLAY_VERSION}-Windows-x64.zip").is_file()
    # Read by the release job's Linux tools: "\n" line endings even when packaged on Windows.
    for name in ("APP_SHA256SUMS", "BUILD_INFO.txt"):
        assert b"\r" not in (tmp_path / "dist" / name).read_bytes(), name


def test_frozen_self_check_renders_finance_pages_and_fails_on_a_missing_file(c, tmp_path, monkeypatch):
    from lightning.runtime import selfcheck
    from lightning.ui.web import create_app

    app = create_app(c)
    assert selfcheck.get(app, "/accounts/new")[0] == 200
    assert selfcheck.get(app, "/no-such-page")[0] == 404
    checks = selfcheck.finance_page_checks(c)
    assert checks["page /budget"] and checks["file /static/style.css"]
    assert all(checks.values()), {name: ok for name, ok in checks.items() if not ok}

    # A font named in fonts.css but missing from the build fails the check.
    fonts = tmp_path / "static" / "fonts"
    fonts.mkdir(parents=True)
    (fonts / "fonts.css").write_text('@font-face{src:url(./Missing-400.woff2) format("woff2")}', encoding="utf-8")
    monkeypatch.setattr(selfcheck, "UI_DIR", tmp_path)
    assert selfcheck.finance_page_checks(c)["file /static/fonts/Missing-400.woff2"] is False


def _ci_scope():
    spec = importlib.util.spec_from_file_location("lightning_ci_scope", ROOT / "packaging" / "ci_scope.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_documentation_skips_the_windows_build():
    scope = _ci_scope()
    for path in ("docs/ARCHITECTURE.md", "CHANGELOG.md", "README.md", "user feedback/batch.md",
                 "Claude outputs/x.zip", "run.sh", "Lightning.desktop"):
        assert scope.cannot_reach_app(path), path
    for path in ("lightning/ui/web.py", "lightning/samples/notes.md", "packaging/APP_README.txt",
                 "packaging/package_app.py", "tests/test_ui.py", "requirements/desktop-probe-win.lock",
                 ".github/workflows/desktop-probe.yml", "pyproject.toml", "desktop_app.py", "run.bat"):
        assert not scope.cannot_reach_app(path), path
    # Anything uncertain builds.
    assert scope.build_windows("workflow_dispatch", "refs/heads/main", None, "HEAD")[0]
    assert scope.build_windows("push", "refs/tags/v1.0.0", "a" * 40, "HEAD")[0]
    assert scope.build_windows("push", "refs/heads/main", None, "HEAD")[0]  # no earlier successful build
    assert scope.build_windows("push", "refs/heads/main", "f" * 40, "HEAD")[0]  # unknown commit


def test_the_docs_only_skip_compares_with_the_last_successful_windows_build(monkeypatch):
    """A docs-only push is skipped only against the last commit whose Windows build succeeded, so
    a code push whose build was cancelled or failed still gets built by the next push."""
    import subprocess

    scope = _ci_scope()
    code, docs = "2241c3abdf147c50d917bececc8b38a0661a4020", "20c62a669b7811b58754e0621fd2c0a632401230"
    available = all(subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=ROOT).returncode == 0
                    for sha in (code, docs, "5518572"))
    if available:  # needs full history (the Linux job checks out with fetch-depth 0)
        assert not scope.build_windows("push", "refs/heads/main", code, docs)[0]  # docs only since the build
        assert scope.build_windows("push", "refs/heads/main", "5518572", docs)[0]  # code changed since
        assert scope.build_windows("push", "refs/heads/main", docs, docs)[0]  # a re-run builds again

    runs = {"workflow_runs": [{"id": 3, "head_sha": "c" * 40}, {"id": 2, "head_sha": "b" * 40},
                              {"id": 1, "head_sha": "a" * 40}]}
    jobs = {3: [{"name": "Full test suite (Linux)", "conclusion": "success"},
                {"name": "Build and test the Windows app", "conclusion": "cancelled"}],
            2: [{"name": "Build and test the Windows app", "conclusion": "skipped"}],
            1: [{"name": "windows-probe", "conclusion": "success"}]}

    def api(path):
        if "/jobs" in path:
            return {"jobs": jobs[int(path.split("/runs/")[1].split("/")[0])]}
        assert "branch=main" in path and "desktop-probe.yml" in path
        return runs

    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/Lightning")
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", "owner/Lightning/.github/workflows/desktop-probe.yml@refs/heads/main")
    monkeypatch.setenv("GH_TOKEN", "token")
    assert scope.last_windows_build(api) == "a" * 40  # cancelled and skipped Windows jobs are not a baseline

    def broken(path):
        raise OSError("no network")

    assert scope.last_windows_build(broken) is None  # no answer: build


def test_build_names_keep_test_builds_apart_from_the_release():
    from lightning import DISPLAY_VERSION

    package_app = _packager()
    release = package_app.build_identity({"GITHUB_SHA": "a" * 40, "GITHUB_REF_TYPE": "tag",
                                          "GITHUB_REF_NAME": f"v{DISPLAY_VERSION}", "GITHUB_RUN_NUMBER": "7"})
    assert release["archive"] == f"Lightning-v{DISPLAY_VERSION}-Windows-x64"
    assert "Build: release v" in package_app.build_info_text(release)
    dev = package_app.build_identity({"GITHUB_SHA": "b" * 40, "GITHUB_RUN_NUMBER": "8", "GITHUB_RUN_ATTEMPT": "2"})
    assert dev["archive"] == f"Lightning-v{DISPLAY_VERSION}-dev-r8-bbbbbbbb-Windows-x64"
    assert dev["artifact"].endswith("-r8-bbbbbbbb-a2-Windows-x64")
    try:
        package_app.build_identity({"GITHUB_SHA": "c" * 40, "GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": "v0.0.1"})
    except RuntimeError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("a tag that differs from the source version was packaged")


def test_notices_cover_what_ships_and_strict_mode_stops_on_a_gap(tmp_path, monkeypatch):
    package_app = _packager()
    bundle = tmp_path / "Lightning"
    bundle.mkdir()
    package_app.write_notices(bundle, strict=False)
    listed = (bundle / "licenses" / "dependency-versions.txt").read_text(encoding="utf-8")
    assert listed.startswith("Python==") and "fastapi==" in listed
    assert "pytest==" not in listed and "pyinstaller==" not in listed.lower()  # build tools are not shipped
    assert (bundle / "licenses" / "Python" / "LICENSE.txt").is_file()
    third_party = {path.name for path in (bundle / "licenses" / "third-party").iterdir()}
    assert {"SQLCipher-LICENSE.txt", "Microsoft-WebView2-SDK-LICENSE.txt", "NETStandard.Library-LICENSE.txt",
            "Python-3.13-incorporated-software.txt", "OpenSSL-and-Rust-crates-NOTICE.txt"} <= third_party

    class NoLicence:  # like proxy-tools, built from a source distribution that has no licence file
        metadata, version, files = {"Name": "proxy_tools"}, "0.1.0", ()

    monkeypatch.setattr(package_app, "runtime_distributions", lambda: ([NoLicence()], []))
    package_app.write_notices(bundle, strict=False)
    assert "Armin Ronacher" in (bundle / "licenses" / "proxy_tools" / "LICENSE.txt").read_text(encoding="utf-8")
    monkeypatch.setattr(package_app, "python_licence", lambda: None)
    try:
        package_app.write_notices(bundle, strict=True)
    except RuntimeError as exc:
        assert "Python's LICENSE" in str(exc)
    else:
        raise AssertionError("strict packaging accepted a missing licence")
