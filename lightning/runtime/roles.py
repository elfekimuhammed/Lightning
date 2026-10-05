"""Session roles for multiple devices: whether the open profile may commit new work.

Multiple devices plan, section 5. The role is chosen when a profile opens and fixes how its database
connection is made, so a reader never holds a writable handle: SQLite's own read-only mode is the
barrier, and the request gate only turns a refused write into a readable answer.
"""
from __future__ import annotations

from enum import StrEnum


class SessionRole(StrEnum):
    HOME = "home"          # the device that holds the profile (every standalone profile today)
    BORROWER = "borrower"  # writes under a granted permit (task 07); returning or sealed copies open as readers
    READER = "reader"      # a saved copy: read-only connection, no backup, migration or seed

    @property
    def writable(self) -> bool:
        return self is not SessionRole.READER


READ_ONLY_REFUSAL = "This is a read-only copy. Nothing can be changed here."
