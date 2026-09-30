"""OS-backed, non-blocking single-instance locks for runtime profiles."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TextIO


class InstanceAlreadyRunning(RuntimeError):
    """Raised when another process already owns the profile lock."""


class InstanceLock:
    """Hold an advisory OS lock through an open descriptor until ``close``.

    The lock file is persistent and is never unlinked, avoiding inode replacement
    races. PID text is diagnostic metadata only; the OS lock is authoritative.
    Call ``ProfilePaths.prepare`` before acquisition when the profile is new.
    """

    def __init__(self, lock_path: str | Path) -> None:
        self.path = Path(lock_path)
        self._file: TextIO | None = None

    @property
    def acquired(self) -> bool:
        return self._file is not None

    def acquire(self) -> "InstanceLock":
        if self._file is not None:
            raise InstanceAlreadyRunning(f"this lock object already owns {self.path}")
        handle = self.path.open("a+", encoding="ascii")
        try:
            if os.name == "nt":
                self._acquire_windows(handle)
            else:
                self._acquire_posix(handle)
            handle.seek(0)
            handle.truncate()
            handle.write(f"pid={os.getpid()}\n")
            handle.flush()
        except (InstanceAlreadyRunning, BlockingIOError, OSError) as exc:
            handle.close()
            if isinstance(exc, InstanceAlreadyRunning):
                raise
            if isinstance(exc, BlockingIOError) or getattr(exc, "errno", None) in (11, 13, 36):
                raise InstanceAlreadyRunning(f"profile is already running ({self.path})") from exc
            raise
        self._file = handle
        return self

    @staticmethod
    def _acquire_posix(handle: TextIO) -> None:
        import fcntl

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise InstanceAlreadyRunning from exc

    @staticmethod
    def _acquire_windows(handle: TextIO) -> None:
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write("\0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise InstanceAlreadyRunning from exc

    def close(self) -> None:
        """Release the OS lock by closing its descriptor; safe to call repeatedly."""
        handle, self._file = self._file, None
        if handle is not None:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                handle.close()

    def __enter__(self) -> "InstanceLock":
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
