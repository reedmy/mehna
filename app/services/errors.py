"""Domain errors — routes translate these into HTTP responses.

Keeping them separate from HTTP means services stay framework-agnostic.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for expected, user-facing failures."""

    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    status_code = 422


class PermissionDenied(DomainError):
    status_code = 403
    default = "لا تملك صلاحية لهذا الإجراء."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.default)


class NotFound(DomainError):
    status_code = 404

    def __init__(self, message: str = "العنصر غير موجود."):
        super().__init__(message)


class LimitReached(DomainError):
    status_code = 402
