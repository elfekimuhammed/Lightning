from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

from lightning.runtime.paths import (
    choose_data_root,
    create_profile,
    discover_profiles,
    legacy_database_candidates,
    resolve_profile,
    user_data_root,
)


def test_documents_default_and_configurable_root_are_pure(tmp_path):
    documents = tmp_path / "OneDrive - Example" / "Documents"
    default_root = choose_data_root(
        platform="win32", documents_dir=documents, environ={}, home=tmp_path
    )
    custom = choose_data_root(custom_root=tmp_path / "custom Lightning")

    assert default_root == documents / "Lightning"
    assert custom == (tmp_path / "custom Lightning").resolve()
    assert not default_root.exists()
    assert not custom.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="uses the Windows known-folder API")
def test_windows_documents_known_folder_resolves_without_writing():
    from lightning.runtime.paths import _windows_documents_directory

    documents = _windows_documents_directory()
    assert documents.is_absolute()


def test_linux_documents_dir_safely_expands_only_home(tmp_path):
    home = tmp_path / "home"
    config = tmp_path / "config"
    config.mkdir()
    (config / "user-dirs.dirs").write_text(
        'XDG_DOCUMENTS_DIR="${HOME}/Cloud Documents"\n', encoding="utf-8"
    )
    root = user_data_root(
        platform="linux",
        environ={"HOME": str(home), "XDG_CONFIG_HOME": str(config), "XDG_DATA_HOME": "/ignore"},
    )
    assert root == (home / "Cloud Documents" / "Lightning").resolve()
    assert not home.exists()

    marker = tmp_path / "must-not-run"
    (config / "user-dirs.dirs").write_text(
        f'XDG_DOCUMENTS_DIR="$(touch {marker})"\n', encoding="utf-8"
    )
    fallback = choose_data_root(
        platform="linux", environ={"HOME": str(home), "XDG_CONFIG_HOME": str(config)}
    )
    assert fallback == (home / "Documents" / "Lightning").resolve()
    assert not marker.exists()


def test_profile_names_utc_sequences_sanitize_and_exclusive_prepare(tmp_path):
    instant = datetime(2026, 10, 1, 1, 30, tzinfo=timezone(timedelta(hours=3)))
    root = tmp_path / "Lightning"
    first = create_profile(
        "Personal",
        root=root,
        created_at=instant,
        id_factory=lambda: "a1b2c3d4",
    )
    assert first.data_dir.name == "Personal_2026-09-30_001_a1b2c3d4"
    assert first.db_path.name == first.data_dir.name + ".db"
    assert first.keys_path.parent == first.data_dir
    assert first.lock_path.parent == first.data_dir
    assert first.backups_dir == first.data_dir / "backups"
    first.prepare()
    first.db_path.write_bytes(b"opaque database bytes")
    (first.keys_path).write_text("secret", encoding="utf-8")

    second = create_profile(
        "personal",
        root=root,
        created_at=instant,
        id_factory=lambda: "b1b2c3d4",
    )
    assert second.data_dir.name == "personal_2026-09-30_002_b1b2c3d4"
    second.prepare()
    with pytest.raises(FileExistsError):
        second.prepare()

    reserved = create_profile(
        "CON",
        root=root,
        created_at=date(2026, 10, 1),
        id_factory=lambda: "c1b2c3d4",
    )
    assert reserved.data_dir.name.startswith("_CON_")
    reserved_with_extension = create_profile(
        "CON.txt",
        root=root,
        created_at=date(2026, 10, 1),
        id_factory=lambda: "e1b2c3d4",
    )
    assert reserved_with_extension.profile.name == "_CON.txt"
    unsafe = create_profile(
        "Bad:/Name. ",
        root=root,
        created_at=date(2026, 10, 1),
        id_factory=lambda: "d1b2c3d4",
    )
    assert unsafe.profile.name == "Bad__Name"
    long_name = create_profile(
        "é" * 80,
        root=root,
        created_at=date(2026, 10, 1),
        id_factory=lambda: "f1b2c3d4",
    )
    assert long_name.profile.name == "é" * 48


def test_unfinished_profile_directory_reserves_its_sequence(tmp_path):
    root = tmp_path / "Lightning"
    first = create_profile(
        "Pending", root=root, created_at=date(2026, 10, 1),
        id_factory=lambda: "a1b2c3d4"
    )
    first.prepare()  # Profile exists before its database file is initialized.
    second = create_profile(
        "Pending", root=root, created_at=date(2026, 10, 1),
        id_factory=lambda: "b1b2c3d4"
    )
    assert second.profile.sequence == 2


def test_discovery_is_shallow_metadata_only_and_symlink_aliases_dedupe(tmp_path):
    root = tmp_path / "container"
    root.mkdir()
    profile = create_profile(
        "Personal",
        root=root,
        created_at=date(2026, 10, 1),
        id_factory=lambda: "a1b2c3d4",
    )
    profile.prepare()
    profile.db_path.write_bytes(b"database contents are not read")
    profile.keys_path.write_text("do not disclose", encoding="utf-8")
    alias = root / "friendly-alias"
    try:
        alias.symlink_to(profile.data_dir, target_is_directory=True)
    except PermissionError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    unrelated = root / "not-a-profile"
    unrelated.mkdir()
    (unrelated / "nested").mkdir()
    backup_like = profile.backups_dir / "Other_2026-10-01_001_12345678"
    backup_like.mkdir()
    (backup_like / f"{backup_like.name}.db").write_bytes(b"backup")

    found = discover_profiles(root=root)
    assert len(found) == 1
    assert found[0].name == "Personal"
    assert found[0].path == profile.data_dir.resolve()
    assert found[0].db_path == profile.db_path.resolve()
    assert not hasattr(found[0], "keys")
    selected = resolve_profile(profile_path=alias)
    assert selected.data_dir == profile.data_dir.resolve()
    assert selected.lock_path == profile.lock_path
    selected_from_db = resolve_profile(db_path=alias / profile.db_path.name)
    assert selected_from_db.data_dir == selected.data_dir
    assert selected_from_db.keys_path == selected.keys_path
    assert selected_from_db.backups_dir == selected.backups_dir
    assert selected_from_db.lock_path == selected.lock_path
    with pytest.raises(ValueError):
        resolve_profile()


def test_named_profile_rejects_database_symlink_to_external_file(tmp_path):
    profile = create_profile(
        "LinkedDb",
        root=tmp_path / "Lightning",
        created_at=date(2026, 10, 1),
        id_factory=lambda: "a1b2c3d4",
    )
    profile.prepare()
    external_database = tmp_path / "external.db"
    external_database.write_bytes(b"not a profile database")
    try:
        profile.db_path.symlink_to(external_database)
    except PermissionError as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")

    assert discover_profiles(root=profile.data_dir.parent) == ()
    with pytest.raises(ValueError, match="not a Lightning profile"):
        resolve_profile(profile_path=profile.data_dir)
    # An explicit file selection follows its symlink to the canonical database.
    assert resolve_profile(db_path=profile.db_path).db_path == external_database.resolve()


def test_explicit_database_preserves_location_and_canonical_alias_sidecars(tmp_path):
    original = tmp_path / "財務" / "ledger.data.db"
    original.parent.mkdir()
    original.touch()
    alias = tmp_path / "alias.db"
    try:
        alias.symlink_to(original)
    except PermissionError as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")

    direct = resolve_profile(db_path=original)
    via_alias = resolve_profile(db_path=alias)
    other = resolve_profile(db_path=tmp_path / "財務" / "other.db")
    assert via_alias.db_path == direct.db_path == original.resolve()
    assert via_alias.keys_path == direct.keys_path
    assert via_alias.backups_dir == direct.backups_dir
    assert via_alias.lock_path == direct.lock_path
    assert direct.db_path == original.resolve()
    assert other.keys_path != direct.keys_path
    assert other.backups_dir != direct.backups_dir
    assert other.lock_path != direct.lock_path


def test_explicit_database_hardlinks_are_rejected(tmp_path):
    database = tmp_path / "ledger.db"
    database.write_bytes(b"opaque")
    linked_name = tmp_path / "linked-ledger.db"
    try:
        linked_name.hardlink_to(database)
    except OSError as exc:
        pytest.skip(f"filesystem does not support hard links: {exc}")

    with pytest.raises(ValueError, match="hard links are unsupported"):
        resolve_profile(db_path=database)
    with pytest.raises(ValueError, match="hard links are unsupported"):
        resolve_profile(db_path=linked_name)

    profile = create_profile(
        "Linked", root=tmp_path / "Lightning", created_at=date(2026, 10, 1),
        id_factory=lambda: "e1b2c3d4"
    )
    profile.prepare()
    profile.db_path.hardlink_to(database)
    with pytest.raises(ValueError, match="hard links are unsupported"):
        resolve_profile(profile_path=profile.data_dir)


def test_prepare_and_legacy_detection_are_read_only_except_for_requested_directories(tmp_path):
    profile = create_profile(
        "Fresh", root=tmp_path / "Lightning", created_at=date(2026, 10, 1),
        id_factory=lambda: "a1b2c3d4"
    )
    profile.prepare()
    assert profile.data_dir.is_dir()
    assert profile.backups_dir.is_dir()
    assert not profile.db_path.exists()
    assert not profile.keys_path.exists()

    legacy = tmp_path / "old-app" / "data" / "lightning.db"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"keep me")
    before = legacy.read_bytes()
    candidates = legacy_database_candidates(project_root=legacy.parents[1], cwd=tmp_path)
    assert candidates == (legacy.resolve(),)
    assert legacy.read_bytes() == before
