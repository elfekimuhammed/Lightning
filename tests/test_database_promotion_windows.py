from __future__ import annotations

import os

import pytest

from lightning.database.promotion_windows import WindowsPromotionFileOps


def test_windows_adapter_import_and_name_validation_are_portable():
    assert WindowsPromotionFileOps.validate_name("profile_01.db") == "profile_01.db"
    for name in ("../outside.db", "subdir\\outside.db", "C:stream", "bad?.db", "NUL.txt", "trailing."):
        with pytest.raises(ValueError):
            WindowsPromotionFileOps.validate_name(name)
    if os.name != "nt":
        with pytest.raises(OSError, match="only on Windows"):
            WindowsPromotionFileOps(".")


windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows file-operation adapter tests")


def put(path, value):
    path.write_bytes(value)


@windows_only
def test_copy_exclusive_flushes_and_verifies_bytes(tmp_path):
    put(tmp_path / "live.db", b"old database bytes")
    with WindowsPromotionFileOps(tmp_path) as adapter:
        adapter.copy_exclusive("live.db", "previous.db")
        assert adapter.sha256("previous.db") == adapter.sha256("live.db")
        with pytest.raises(OSError):
            adapter.copy_exclusive("live.db", "previous.db")
    assert (tmp_path / "previous.db").read_bytes() == b"old database bytes"


@windows_only
def test_replace_uses_same_directory_and_retains_previous_checkpoint(tmp_path):
    put(tmp_path / "live.db", b"old")
    put(tmp_path / "candidate.db", b"new")
    with WindowsPromotionFileOps(tmp_path) as adapter:
        adapter.copy_exclusive("live.db", "previous.db")
        expected_hash = adapter.sha256("candidate.db")
        adapter.atomic_replace("candidate.db", "live.db")
        assert adapter.sha256("live.db") == expected_hash
        assert (tmp_path / "live.db").read_bytes() == b"new"
        assert (tmp_path / "previous.db").read_bytes() == b"old"
        assert not (tmp_path / "candidate.db").exists()


@windows_only
def test_copy_flush_failure_keeps_source_and_removes_partial(tmp_path, monkeypatch):
    put(tmp_path / "live.db", b"old")
    with WindowsPromotionFileOps(tmp_path) as adapter:
        def fail_flush(handle):
            raise OSError("injected FlushFileBuffers failure")

        monkeypatch.setattr(adapter, "_flush_file", fail_flush)
        with pytest.raises(OSError, match="FlushFileBuffers"):
            adapter.copy_exclusive("live.db", "previous.db")
        assert (tmp_path / "live.db").read_bytes() == b"old"
        assert not (tmp_path / "previous.db").exists()
        assert list(tmp_path.glob(".lp-*.partial")) == []


@windows_only
def test_move_failure_preserves_live_candidate_and_previous(tmp_path, monkeypatch):
    put(tmp_path / "live.db", b"old")
    put(tmp_path / "candidate.db", b"new")
    put(tmp_path / "previous.db", b"old")
    with WindowsPromotionFileOps(tmp_path) as adapter:
        def fail_move(source, destination, flags):
            raise OSError("injected MoveFileExW failure")

        monkeypatch.setattr(adapter, "_move_file", fail_move)
        with pytest.raises(OSError, match="MoveFileExW"):
            adapter.atomic_replace("candidate.db", "live.db")
    assert (tmp_path / "live.db").read_bytes() == b"old"
    assert (tmp_path / "candidate.db").read_bytes() == b"new"
    assert (tmp_path / "previous.db").read_bytes() == b"old"


@windows_only
def test_post_replace_flush_failure_keeps_previous_for_blocked_recovery(tmp_path, monkeypatch):
    put(tmp_path / "live.db", b"old")
    put(tmp_path / "candidate.db", b"new")
    put(tmp_path / "previous.db", b"old")
    with WindowsPromotionFileOps(tmp_path) as adapter:
        original_flush = adapter._flush_file
        calls = 0

        def fail_second_flush(handle):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected published-file flush failure")
            original_flush(handle)

        monkeypatch.setattr(adapter, "_flush_file", fail_second_flush)
        with pytest.raises(OSError, match="published-file flush"):
            adapter.atomic_replace("candidate.db", "live.db")
    # Namespace replacement happened; caller must leave authority blocked and
    # recover from hashes. This adapter does not claim POSIX directory fsync.
    assert (tmp_path / "live.db").read_bytes() == b"new"
    assert (tmp_path / "previous.db").read_bytes() == b"old"


@windows_only
def test_hardlinks_and_reparse_points_are_rejected(tmp_path):
    put(tmp_path / "live.db", b"old")
    os.link(tmp_path / "live.db", tmp_path / "hard.db")
    with WindowsPromotionFileOps(tmp_path) as adapter:
        with pytest.raises(ValueError, match="Hard-linked"):
            adapter.sha256("hard.db")
        try:
            (tmp_path / "link.db").symlink_to(tmp_path / "live.db")
        except (OSError, NotImplementedError):
            pytest.skip("Windows symlink creation is unavailable in this environment")
        with pytest.raises(ValueError, match="Reparse-point"):
            adapter.sha256("link.db")


@windows_only
def test_reparse_root_is_rejected(tmp_path):
    root = tmp_path / "real-root"
    root.mkdir()
    alias = tmp_path / "root-alias"
    try:
        alias.symlink_to(root, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Windows symlink creation is unavailable in this environment")
    with pytest.raises(ValueError, match="reparse points"):
        WindowsPromotionFileOps(alias)
