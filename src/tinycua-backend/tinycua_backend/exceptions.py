"""Custom exceptions for TinyCUA backend."""

from typing import Any

from pydantic import BaseModel


class TinyCUAException(Exception):
    """Base exception for TinyCUA."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class NotFoundException(TinyCUAException):
    """Resource not found."""

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            message=f"{resource} '{resource_id}' not found",
            code="NOT_FOUND",
        )
        self.resource = resource
        self.resource_id = resource_id


class UnauthorizedException(TinyCUAException):
    """Unauthorized access."""

    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message=message, code="UNAUTHORIZED")


class ValidationException(TinyCUAException):
    """Validation error."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR")
        self.field = field


class ConflictException(TinyCUAException):
    """Resource conflict."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CONFLICT")


class ForbiddenException(TinyCUAException):
    """Forbidden access."""

    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message=message, code="FORBIDDEN")


class ServiceException(TinyCUAException):
    """Service unavailable."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="SERVICE_UNAVAILABLE")


class ErrorResponse(BaseModel):
    """Error response schema."""

    code: str
    message: str
    details: dict[str, Any] | None = None
