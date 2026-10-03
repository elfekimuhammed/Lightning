"""packaging/publish_release.sh against a fake GitHub (tests/fake_gh.py): a release is published only
from the tested files, read back byte for byte, and never replaces a version that already exists."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "packaging" / "publish_release.sh"
TAG = "v0.5.0-beta.1"
ZIP = f"Lightning-{TAG}-Windows-x64.zip"

pytestmark = pytest.mark.skipif(not all(shutil.which(tool) for tool in ("bash", "jq", "sha256sum", "cmp")),
                                reason="needs bash, jq, sha256sum and cmp (present on Linux CI)")


def publish(tmp_path: Path, state: dict, **env) -> tuple[subprocess.CompletedProcess, dict]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "gh"
    fake.write_text(f"#!/bin/sh\nexec {sys.executable} {ROOT / 'tests' / 'fake_gh.py'} \"$@\"\n", encoding="utf-8")
    fake.chmod(0o755)
    release = tmp_path / "release"
    release.mkdir()
    payload = os.urandom(50_000)
    (release / ZIP).write_bytes(payload)
    (release / "APP_SHA256SUMS").write_text(f"{hashlib.sha256(payload).hexdigest()}  {ZIP}\n", encoding="utf-8")
    (release / "BUILD_INFO.txt").write_text(f"Lightning 0.5.0-beta.1 for Windows x64\nBuild: release {TAG}\n"
                                            "Commit: abc123\nRun: workflow run 22, attempt 1\n", encoding="utf-8")
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    environment = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "MOCK_STATE": str(state_file),
                   "DOWNLOADS_REPO": "owner/Lightning-downloads", "TAG": TAG, "ZIP": ZIP, "GH_TOKEN": "token",
                   "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"), **env}
    result = subprocess.run(["bash", str(SCRIPT)], cwd=release, env=environment, capture_output=True, text=True)
    return result, json.loads(state_file.read_text(encoding="utf-8"))


def published(state: dict) -> list[dict]:
    return [r for r in state["releases"] if not r["draft"]]


def test_a_tested_build_is_published_with_both_files_and_its_checksum(tmp_path):
    result, state = publish(tmp_path, {"releases": [], "tags": ["v0.4.0-beta.1"]})
    assert result.returncode == 0, result.stdout + result.stderr
    [release] = published(state)
    assert release["tag_name"] == TAG and release["prerelease"] and release["target_commitish"] == "main"
    assert release["name"] == "Lightning 0.5.0 beta 1 for Windows"
    assert [a["name"] for a in release["assets"]] == [ZIP, "APP_SHA256SUMS"]
    assert hashlib.sha256((tmp_path / "release" / ZIP).read_bytes()).hexdigest() in release["body"]
    assert "does not make releases immutable" in result.stdout  # a reminder until the setting is on


@pytest.mark.parametrize("state, env, message", [
    ({"releases": [], "tags": []}, {"GH_TOKEN": ""}, "LIGHTNING_DOWNLOADS_TOKEN secret is not set"),
    ({"releases": [], "tags": [], "auth_fail": True}, {}, "token cannot read"),
    ({"releases": [{"id": 7, "tag_name": TAG, "draft": False, "assets": []}], "tags": [TAG]}, {},
     "already has a release"),
    ({"releases": [], "tags": [TAG]}, {}, "already has a tag"),
    ({"releases": [], "tags": []}, {"ZIP": "Lightning-v0.5.0-beta.1-dev-r21-abcdef12-Windows-x64.zip"},
     "development build cannot be published"),
])
def test_nothing_is_published_or_replaced_when_a_release_cannot_be_trusted(tmp_path, state, env, message):
    before = json.loads(json.dumps(state))
    result, after = publish(tmp_path, state, **env)
    assert result.returncode != 0 and message in result.stdout, result.stdout + result.stderr
    assert published(after) == published(before)


def test_an_upload_that_changed_in_transit_is_never_published(tmp_path):
    result, state = publish(tmp_path, {"releases": [], "tags": [], "corrupt_upload": True})
    assert result.returncode != 0 and "differs from the tested file" in result.stdout
    assert not published(state) and state["releases"][0]["draft"]


def test_a_draft_left_by_a_failed_attempt_is_replaced_by_the_new_attempt(tmp_path):
    state = {"releases": [{"id": 9, "tag_name": TAG, "draft": True, "assets": []}], "tags": [], "immutable": True}
    result, after = publish(tmp_path, state)
    assert result.returncode == 0, result.stdout + result.stderr
    assert [r["id"] for r in after["releases"]] != [9] and len(published(after)) == 1
    assert "immutable" not in result.stdout  # no reminder once the downloads repository locks releases
