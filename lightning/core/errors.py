"""Errors raised by the financial core.

Every error carries a plain-language message that is safe to show in the UI.
"""


class LightningError(Exception):
    """Base class for all expected (user-facing) errors."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


class ValidationError(LightningError):
    """Input breaks a business rule (bad amount, wrong category, ...)."""


class NotFoundError(LightningError):
    """A referenced record does not exist."""


class ConflictError(LightningError):
    """The action conflicts with existing data (duplicate code, non-zero balance, ...)."""
