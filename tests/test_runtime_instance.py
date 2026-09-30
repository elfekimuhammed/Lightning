from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from lightning.runtime.instance import InstanceAlreadyRunning, InstanceLock
from lightning.runtime.paths import resolve_profile


def test_lock_reentry_conflict_and_idempotent_close(tmp_path):
    paths = resolve_profile(db_path=tmp_path / "ledger.db")
    paths.prepare()
    first = InstanceLock(paths.lock_path).acquire()
    try:
        with pytest.raises(InstanceAlreadyRunning):
            InstanceLock(paths.lock_path).acquire()
        with pytest.raises(InstanceAlreadyRunning):
            first.acquire()
        assert f"pid={os.getpid()}" in paths.lock_path.read_text()
    finally:
        first.close()
        first.close()

    assert not first.acquired
    assert paths.lock_path.exists()  # persistent inode: never unlink on release


def test_subprocess_cannot_enter_until_descriptor_is_released(tmp_path):
    paths = resolve_profile(db_path=tmp_path / "ledger.db")
    paths.prepare()
    lock = InstanceLock(paths.lock_path).acquire()
    script = """
import sys
from lightning.runtime.instance import InstanceAlreadyRunning, InstanceLock
try:
    with InstanceLock(sys.argv[1]):
        print('acquired')
except InstanceAlreadyRunning:
    print('busy')
"""
    env = os.environ.copy()
    repo_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")

    try:
        occupied = subprocess.run(
            [sys.executable, "-c", script, str(paths.lock_path)],
            cwd=tmp_path,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert occupied.stdout.strip() == "busy"
    finally:
        lock.close()

    released = subprocess.run(
        [sys.executable, "-c", script, str(paths.lock_path)],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert released.stdout.strip() == "acquired"
