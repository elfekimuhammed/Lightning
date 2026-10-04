from __future__ import annotations

import errno
import os
import stat

import pytest

from lightning.database import promotion
from lightning.database.promotion import PosixPromotionFileOps


pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX adapter tests")


def write(path, content):
    path.write_bytes(content)
    path.chmod(0o600)


def test_exclusive_copy_hash_and_file_directory_flushes(tmp_path, monkeypatch):
    write(tmp_path / "live.db", b"old ledger")
    adapter = PosixPromotionFileOps(tmp_path)
    calls = []
    original_fsync = os.fsync

    def record_fsync(fd):
        calls.append(stat.S_ISDIR(os.fstat(fd).st_mode))
        return original_fsync(fd)

    monkeypatch.setattr(promotion.os, "fsync", record_fsync)
    try:
        adapter.copy_exclusive("live.db", "prior.db")
        assert adapter.sha256("live.db") == adapter.sha256("prior.db")
        assert (tmp_path / "prior.db").read_bytes() == b"old ledger"
        assert calls == [False, True]
    finally:
        adapter.close()


def test_exclusive_copy_never_overwrites_an_existing_file(tmp_path):
    write(tmp_path / "live.db", b"source")
    write(tmp_path / "prior.db", b"keep me")
    with PosixPromotionFileOps(tmp_path) as adapter:
        with pytest.raises(FileExistsError):
            adapter.copy_exclusive("live.db", "prior.db")
    assert (tmp_path / "prior.db").read_bytes() == b"keep me"


def test_symlinks_hardlinks_and_unsafe_names_are_rejected(tmp_path):
    write(tmp_path / "live.db", b"old")
    (tmp_path / "linked.db").symlink_to(tmp_path / "live.db")
    os.link(tmp_path / "live.db", tmp_path / "hardlinked.db")
    with PosixPromotionFileOps(tmp_path) as adapter:
        with pytest.raises(OSError):
            adapter.sha256("linked.db")
        with pytest.raises(ValueError, match="Hard-linked"):
            adapter.sha256("hardlinked.db")
        with pytest.raises(ValueError, match="safe file names"):
            adapter.sha256("../outside.db")
        with pytest.raises(ValueError, match="safe file names"):
            adapter.copy_exclusive("live.db", "subdir/out.db")


def test_symlink_and_hardlink_destination_are_not_replaced(tmp_path):
    write(tmp_path / "candidate.db", b"new")
    write(tmp_path / "live.db", b"old")
    (tmp_path / "sym-live.db").symlink_to(tmp_path / "live.db")
    os.link(tmp_path / "live.db", tmp_path / "hard-live.db")
    with PosixPromotionFileOps(tmp_path) as adapter:
        with pytest.raises(OSError):
            adapter.atomic_replace("candidate.db", "sym-live.db")
        with pytest.raises(ValueError, match="Hard-linked"):
            adapter.atomic_replace("candidate.db", "hard-live.db")
    assert (tmp_path / "candidate.db").read_bytes() == b"new"
    assert (tmp_path / "live.db").read_bytes() == b"old"


def test_root_symlink_is_rejected(tmp_path):
    root = tmp_path / "real"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic links"):
        PosixPromotionFileOps(alias)


def test_replaced_root_path_fails_closed(tmp_path):
    root = tmp_path / "profile-data"
    root.mkdir()
    write(root / "live.db", b"old")
    adapter = PosixPromotionFileOps(root)
    moved = tmp_path / "renamed-profile-data"
    root.rename(moved)
    root.mkdir()
    write(root / "live.db", b"different profile")
    try:
        with pytest.raises(OSError, match="directory path changed"):
            adapter.sha256("live.db")
        assert (moved / "live.db").read_bytes() == b"old"
        assert (root / "live.db").read_bytes() == b"different profile"
    finally:
        adapter.close()


def test_atomic_replace_is_same_directory_and_preserves_named_previous(tmp_path, monkeypatch):
    write(tmp_path / "live.db", b"old live")
    write(tmp_path / "candidate.db", b"new live")
    write(tmp_path / "previous.db", b"old live")
    adapter = PosixPromotionFileOps(tmp_path)
    calls = []
    original_fsync = os.fsync

    def record_fsync(fd):
        calls.append(stat.S_ISDIR(os.fstat(fd).st_mode))
        return original_fsync(fd)

    monkeypatch.setattr(promotion.os, "fsync", record_fsync)
    try:
        adapter.atomic_replace("candidate.db", "live.db")
        assert (tmp_path / "live.db").read_bytes() == b"new live"
        assert (tmp_path / "previous.db").read_bytes() == b"old live"
        assert not (tmp_path / "candidate.db").exists()
        assert calls == [False, True]
    finally:
        adapter.close()


def test_copy_flush_failure_removes_partial_and_keeps_existing_ledger(tmp_path, monkeypatch):
    write(tmp_path / "live.db", b"old live")
    write(tmp_path / "previous.db", b"old live")
    adapter = PosixPromotionFileOps(tmp_path)
    original_fsync = os.fsync

    def fail_file_fsync(fd):
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(errno.EIO, "injected file flush failure")
        return original_fsync(fd)

    monkeypatch.setattr(promotion.os, "fsync", fail_file_fsync)
    try:
        with pytest.raises(OSError, match="injected file flush failure"):
            adapter.copy_exclusive("live.db", "candidate.db")
        assert not (tmp_path / "candidate.db").exists()
        assert (tmp_path / "live.db").read_bytes() == b"old live"
        assert (tmp_path / "previous.db").read_bytes() == b"old live"
    finally:
        adapter.close()


def test_rename_failure_leaves_candidate_live_and_previous_untouched(tmp_path, monkeypatch):
    write(tmp_path / "live.db", b"old live")
    write(tmp_path / "candidate.db", b"new live")
    write(tmp_path / "previous.db", b"old live")
    adapter = PosixPromotionFileOps(tmp_path)

    def fail_replace(*args, **kwargs):
        raise OSError(errno.EIO, "injected rename failure")

    monkeypatch.setattr(promotion.os, "replace", fail_replace)
    try:
        with pytest.raises(OSError, match="injected rename failure"):
            adapter.atomic_replace("candidate.db", "live.db")
        assert (tmp_path / "live.db").read_bytes() == b"old live"
        assert (tmp_path / "candidate.db").read_bytes() == b"new live"
        assert (tmp_path / "previous.db").read_bytes() == b"old live"
    finally:
        adapter.close()


def test_directory_flush_failure_after_replace_keeps_old_checkpoint(tmp_path, monkeypatch):
    write(tmp_path / "live.db", b"old live")
    write(tmp_path / "candidate.db", b"new live")
    write(tmp_path / "previous.db", b"old live")
    adapter = PosixPromotionFileOps(tmp_path)
    original_fsync = os.fsync

    def fail_directory_fsync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(errno.EIO, "injected directory flush failure")
        return original_fsync(fd)

    monkeypatch.setattr(promotion.os, "fsync", fail_directory_fsync)
    try:
        with pytest.raises(OSError, match="injected directory flush failure"):
            adapter.atomic_replace("candidate.db", "live.db")
        # Rename may have happened, but authority must remain blocked and the
        # pre-P4 journal's named old checkpoint remains recoverable.
        assert (tmp_path / "live.db").read_bytes() == b"new live"
        assert (tmp_path / "previous.db").read_bytes() == b"old live"
    finally:
        adapter.close()
