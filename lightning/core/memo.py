"""Request-scoped memo for pure read functions.

A page often asks for the same figure many times (the Overview's position at several dates, the same
month's spending for every budget line). Inside ``request_cache(db)`` a function decorated with
``@request_cached`` computes each distinct call once; outside it, nothing is cached and every call
reads the database as before.

The memo can never serve a figure older than the database it was read from:
- it lives for one request only;
- any write on the connection (SQLite ``total_changes``) empties it;
- nothing is cached or served while a transaction is open, so a rolled-back write leaves nothing behind.

Callers get a copy of a cached list, dict or tuple (``deep=True`` copies all the way down), so a caller
that edits its result cannot change what the next caller reads.
"""

from __future__ import annotations

import copy
import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


class _Scope:
    __slots__ = ("db", "stamp", "values")

    def __init__(self, db: Any):
        self.db = db
        self.stamp: int | None = None
        self.values: dict = {}

    def usable(self) -> int | None:
        """The connection's change count when the memo may be used now, else None."""
        conn = self.db.conn
        if conn.in_transaction:
            return None
        changes = conn.total_changes
        if changes != self.stamp:
            self.values.clear()
            self.stamp = changes
        return changes


_SCOPE: ContextVar[_Scope | None] = ContextVar("lightning_request_cache", default=None)


@contextmanager
def request_cache(db: Any) -> Iterator[None]:
    """Memoize decorated reads against ``db`` until the block ends."""
    token = _SCOPE.set(_Scope(db))
    try:
        yield
    finally:
        _SCOPE.reset(token)


def in_request() -> bool:
    """True while decorated reads are being memoized (a request, outside any transaction)."""
    scope = _SCOPE.get()
    return scope is not None and scope.usable() is not None


def _shallow(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, tuple) and type(value) is tuple:
        return tuple(_shallow(item) for item in value)
    return value


def request_cached(func: Callable | None = None, *, deep: bool = False) -> Callable:
    """Decorate a pure read (method or function) whose arguments are hashable."""
    def decorate(fn: Callable) -> Callable:
        name = f"{fn.__module__}.{fn.__qualname__}"
        give = copy.deepcopy if deep else _shallow

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            scope = _SCOPE.get()
            if scope is None:
                return fn(*args, **kwargs)
            try:
                key = (name, args, tuple(sorted(kwargs.items())))
                hash(key)
            except TypeError:
                return fn(*args, **kwargs)
            stamp = scope.usable()
            if stamp is None:
                return fn(*args, **kwargs)
            if key in scope.values:
                return give(scope.values[key])
            value = fn(*args, **kwargs)
            if scope.usable() == stamp:  # nothing was written while it was computed
                scope.values[key] = value
                return give(value)
            return value

        return wrapper

    return decorate(func) if func is not None else decorate
