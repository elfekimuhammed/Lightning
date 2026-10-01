"""Document-rooted profile paths and read-only profile discovery."""

from __future__ import annotations

import os
import re
import secrets
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

_PROFILE_STEM = re.compile(
    r"(?P<name>.+)_(?P<day>\d{4}-\d{2}-\d{2})_(?P<sequence>\d{3,})_(?P<identity>[0-9a-fA-F]{8})\Z"
)
_MAX_PROFILE_NAME_LENGTH = 48
_INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WINDOWS_NAME = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", re.IGNORECASE)


@dataclass(frozen=True)
class ProfileInfo:
    """Non-secret metadata discovered from a Lightning profile directory."""

    name: str
    path: Path
    db_path: Path
    created: date
    sequence: int
    profile_id: str


@dataclass(frozen=True)
class ProfilePaths:
    """Database and companion paths for one explicitly selected profile."""

    profile: ProfileInfo | None
    data_dir: Path
    db_path: Path
    keys_path: Path
    backups_dir: Path
    lock_path: Path
    is_new: bool = False

    def prepare(self) -> None:
        """Create required directories without replacing any profile or data file.

        New named profiles are created with exclusive ``mkdir``. Existing named
        profiles must already exist. Explicit-database sidecars may be created as
        directories beside the selected database.
        """
        if self.is_new:
            self.data_dir.parent.mkdir(parents=True, exist_ok=True)
            self.data_dir.mkdir(exist_ok=False)
        elif self.profile is not None:
            if not self.data_dir.is_dir():
                raise FileNotFoundError(f"profile directory does not exist: {self.data_dir}")
        else:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(exist_ok=True)


def _windows_documents_directory() -> Path:
    """Ask Windows for the current user's Documents known folder (including redirects)."""
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    folder_id = GUID(
        0xFDD39AD0,
        0x238F,
        0x46AF,
        (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
    )
    result_path = ctypes.POINTER(ctypes.c_wchar)()
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)  # type: ignore[attr-defined]
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)  # type: ignore[attr-defined]
    get_known_folder_path = shell32.SHGetKnownFolderPath
    get_known_folder_path.argtypes = [
        ctypes.POINTER(GUID),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_wchar)),
    ]
    get_known_folder_path.restype = ctypes.c_long
    free_task_memory = ole32.CoTaskMemFree
    free_task_memory.argtypes = [ctypes.c_void_p]
    free_task_memory.restype = None

    result = get_known_folder_path(ctypes.byref(folder_id), 0, None, ctypes.byref(result_path))
    if result:
        raise OSError(result, "Could not resolve the Windows Documents folder")
    if not result_path:
        raise OSError("SHGetKnownFolderPath returned a null Documents path")
    try:
        return Path(ctypes.wstring_at(result_path))
    finally:
        free_task_memory(ctypes.cast(result_path, ctypes.c_void_p))


def _linux_documents_directory(home: Path, environ: Mapping[str, str]) -> Path:
    config_home = environ.get("XDG_CONFIG_HOME", "")
    config_dir = Path(config_home) if config_home and Path(config_home).is_absolute() else home / ".config"
    config_file = config_dir / "user-dirs.dirs"
    try:
        lines = config_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return home / "Documents"

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"XDG_DOCUMENTS_DIR\s*=\s*(.*)", line)
        if not match:
            continue
        value = _parse_user_dir_value(match.group(1))
        if value is None:
            break
        value = value.replace("${HOME}", str(home)).replace("$HOME", str(home))
        if "$" in value or "`" in value or not Path(value).is_absolute():
            break
        return Path(value)
    return home / "Documents"


def _parse_user_dir_value(raw: str) -> str | None:
    """Parse a plain quoted/unquoted value without shell expansion or evaluation."""
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        quote = raw[0]
        raw = raw[1:-1]
        if quote == '"':
            raw = re.sub(r"\\([\\\"])", r"\1", raw)
    elif any(char.isspace() for char in raw) or "#" in raw:
        return None
    if "\n" in raw or "\r" in raw or "\x00" in raw:
        return None
    return raw


def choose_data_root(
    custom_root: str | Path | None = None,
    *,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    documents_dir: str | Path | None = None,
) -> Path:
    """Choose the Lightning profile container, without creating directories.

    ``custom_root`` selects a caller-configured container. Otherwise Windows uses
    its Documents known folder and Linux follows ``XDG_DOCUMENTS_DIR``; both append
    ``Lightning``. ``documents_dir`` injects an already-resolved Documents folder.
    """
    if custom_root is not None:
        return Path(custom_root).expanduser().resolve()
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    home_path = Path(home or environ.get("HOME") or Path.home()).expanduser()
    if documents_dir is not None:
        documents = Path(documents_dir).expanduser()
    elif platform == "win32" or platform.startswith("win"):
        documents = _windows_documents_directory()
    else:
        documents = _linux_documents_directory(home_path, environ)
    return (documents / "Lightning").resolve()


def user_data_root(
    *,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    custom_root: str | Path | None = None,
    documents_dir: str | Path | None = None,
) -> Path:
    """Compatibility name for :func:`choose_data_root`. No path is created."""
    return choose_data_root(
        custom_root,
        platform=platform,
        environ=environ,
        home=home,
        documents_dir=documents_dir,
    )


def _sanitize_profile_name(name: str) -> str:
    cleaned = _INVALID_NAME_CHARS.sub("_", name.strip()).rstrip(" .")
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned[:_MAX_PROFILE_NAME_LENGTH].rstrip(" .")
    if not cleaned or cleaned in (".", ".."):
        raise ValueError("profile name must contain at least one usable character")
    if _RESERVED_WINDOWS_NAME.fullmatch(cleaned.split(".", 1)[0]):
        cleaned = f"_{cleaned}"
    return cleaned


def _profile_info(path: Path) -> ProfileInfo | None:
    match = _PROFILE_STEM.fullmatch(path.name)
    if match is None:
        return None
    try:
        created = date.fromisoformat(match.group("day"))
    except ValueError:
        return None
    stem = path.name
    database = path / f"{stem}.db"
    if database.is_symlink() or not database.is_file():
        return None
    return ProfileInfo(
        name=match.group("name"),
        path=path.resolve(),
        db_path=database.resolve(),
        created=created,
        sequence=int(match.group("sequence")),
        profile_id=match.group("identity").lower(),
    )


def _reject_hardlinked_database(database: Path) -> None:
    try:
        if database.stat().st_nlink > 1:
            raise ValueError(f"database hard links are unsupported: {database}")
    except FileNotFoundError:
        pass


def discover_profiles(
    root: str | Path | None = None,
    *,
    custom_dir: str | Path | None = None,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    documents_dir: str | Path | None = None,
) -> tuple[ProfileInfo, ...]:
    """List direct Lightning profile subdirectories without opening profile data.

    Set ``custom_dir`` to scan an explicitly selected alternate container. The scan
    is never recursive; backup folders and unrelated Documents content are ignored.
    This discovers database profiles only, not backup files. Returned metadata
    contains names and paths only, never key or database contents.
    """
    if root is not None and custom_dir is not None:
        raise ValueError("pass root or custom_dir, not both")
    container = Path(custom_dir or root).expanduser().resolve() if (custom_dir or root) else choose_data_root(
        platform=platform, environ=environ, home=home, documents_dir=documents_dir
    )
    canonical_root = container.resolve()
    try:
        children = tuple(container.iterdir())
    except OSError:
        return ()
    profiles: list[ProfileInfo] = []
    seen: set[Path] = set()
    for child in children:
        try:
            if not child.is_dir():
                continue
            canonical = child.resolve()
            try:
                canonical.relative_to(canonical_root)
            except ValueError:
                continue
            if canonical in seen:
                continue
            info = _profile_info(canonical)
            if info is not None:
                profiles.append(info)
                seen.add(canonical)
        except OSError:
            continue
    return tuple(sorted(profiles, key=lambda item: (item.name.casefold(), item.created, item.sequence, item.profile_id)))


def create_profile(
    name: str,
    *,
    root: str | Path | None = None,
    custom_dir: str | Path | None = None,
    created_at: datetime | date | None = None,
    id_factory: Callable[[], str] = lambda: secrets.token_hex(4),
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    documents_dir: str | Path | None = None,
) -> ProfilePaths:
    """Reserve a unique profile name and return paths; creation is deferred to prepare.

    Sequence numbers are allocated per sanitized name and UTC date. Directory
    creation remains exclusive in ``prepare`` to catch races without overwriting.
    """
    if root is not None and custom_dir is not None:
        raise ValueError("pass root or custom_dir, not both")
    container = Path(custom_dir or root).expanduser().resolve() if (custom_dir or root) else choose_data_root(
        platform=platform, environ=environ, home=home, documents_dir=documents_dir
    )
    safe_name = _sanitize_profile_name(name)
    if created_at is None:
        day = datetime.now(timezone.utc).date()
    elif isinstance(created_at, datetime):
        moment = created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at
        day = moment.astimezone(timezone.utc).date()
    else:
        day = created_at
    entries = tuple(container.iterdir()) if container.is_dir() else ()
    occupied_names = {child.name.casefold() for child in entries}
    matching: list[int] = []
    for child in entries:
        match = _PROFILE_STEM.fullmatch(child.name)
        if match is None or match.group("name").casefold() != safe_name.casefold():
            continue
        try:
            if date.fromisoformat(match.group("day")) == day:
                matching.append(int(match.group("sequence")))
        except ValueError:
            continue
    sequence = max(matching, default=0) + 1
    identity = id_factory().lower()
    if re.fullmatch(r"[0-9a-f]{8}", identity) is None:
        raise ValueError("id_factory must return exactly eight hexadecimal characters")
    while True:
        stem = f"{safe_name}_{day.isoformat()}_{sequence:03d}_{identity}"
        if stem.casefold() not in occupied_names:
            break
        sequence += 1
    profile_dir = container / stem
    info = ProfileInfo(
        name=safe_name,
        path=profile_dir,
        db_path=profile_dir / f"{stem}.db",
        created=day,
        sequence=sequence,
        profile_id=identity,
    )
    return ProfilePaths(
        profile=info,
        data_dir=profile_dir,
        db_path=info.db_path,
        keys_path=profile_dir / "keys.json",
        backups_dir=profile_dir / "backups",
        lock_path=profile_dir / "instance.lock",
        is_new=True,
    )


def resolve_profile(
    profile_path: str | Path | None = None,
    *,
    db_path: str | Path | None = None,
) -> ProfilePaths:
    """Resolve an explicitly selected named profile or database path.

    Omitting both selectors is an error: discovery never chooses a profile for the
    user. Explicit database sidecars are derived from its canonical path and remain
    beside that database, preserving its filename and location.
    """
    if (profile_path is None) == (db_path is None):
        raise ValueError("select exactly one of profile_path or db_path")
    if profile_path is not None:
        directory = Path(profile_path).expanduser().resolve()
        info = _profile_info(directory)
        if info is None:
            raise ValueError(f"not a Lightning profile directory: {directory}")
        _reject_hardlinked_database(info.db_path)
        return ProfilePaths(
            profile=info,
            data_dir=directory,
            db_path=info.db_path,
            keys_path=directory / "keys.json",
            backups_dir=directory / "backups",
            lock_path=directory / "instance.lock",
        )

    database = Path(db_path).expanduser().resolve()
    _reject_hardlinked_database(database)
    named_profile = _profile_info(database.parent)
    if named_profile is not None and named_profile.db_path == database:
        directory = named_profile.path
        return ProfilePaths(
            profile=named_profile,
            data_dir=directory,
            db_path=named_profile.db_path,
            keys_path=directory / "keys.json",
            backups_dir=directory / "backups",
            lock_path=directory / "instance.lock",
        )
    sidecar = database.parent / f".{database.name}.lightning"
    return ProfilePaths(
        profile=None,
        data_dir=sidecar,
        db_path=database,
        keys_path=sidecar / "keys.json",
        backups_dir=sidecar / "backups",
        lock_path=sidecar / "instance.lock",
    )


def legacy_database_candidates(
    *, project_root: str | Path, cwd: str | Path | None = None
) -> tuple[Path, ...]:
    """Report existing legacy ``data/lightning.db`` files without opening them."""
    roots = [Path(project_root)]
    if cwd is not None:
        roots.append(Path(cwd))
    found: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        candidate = (root / "data" / "lightning.db").resolve()
        if candidate not in seen and candidate.is_file():
            found.append(candidate)
            seen.add(candidate)
    return tuple(found)
