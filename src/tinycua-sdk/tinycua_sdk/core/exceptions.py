"""Provider-specific exception classes for the TINYCUA SDK."""

from __future__ import annotations



class ProviderNotSupportedError(ValueError):
    """Raised when a requested provider is not registered in the registry.

    Attributes:
        provider_id: The provider identifier that was requested.
        supported_list: List of registered provider identifiers.
    """

    def __init__(
        self,
        provider_id: str,
        supported_list: list[str] | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.supported_list = supported_list or []
        if self.supported_list:
            msg = (
                f"Provider '{provider_id}' is not supported. "
                f"Supported providers: {', '.join(sorted(self.supported_list))}"
            )
        else:
            msg = f"Provider '{provider_id}' is not supported."
        super().__init__(msg)

    def __reduce__(self) -> tuple[type[ProviderNotSupportedError], tuple[str, list[str]]]:
        """Return pickling reduce for the exception."""
        return (self.__class__, (self.provider_id, self.supported_list))


class ProviderAuthError(Exception):
    """Raised when provider authentication fails.

    Attributes:
        message: Human-readable error description.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ProviderApiError(Exception):
    """Raised when a provider API call returns an error status.

    Attributes:
        status_code: HTTP status code from the provider API.
        message: Human-readable error description.
    """

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{status_code}] {message}")

    def __reduce__(self) -> tuple[type[ProviderApiError], tuple[int, str]]:
        """Return pickling reduce for the exception."""
        return (self.__class__, (self.status_code, self.message))


__all__ = [
    "ProviderNotSupportedError",
    "ProviderAuthError",
    "ProviderApiError",
]
