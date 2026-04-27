"""Custom exceptions for TinyCUA."""

from __future__ import annotations


class TinyCUAError(Exception):
    """Base exception for TinyCUA errors."""

    pass


class StorageError(TinyCUAError):
    """Raised when a storage operation fails."""

    pass


class NetworkError(TinyCUAError):
    """Raised when a network operation fails."""

    pass


class AuthError(TinyCUAError):
    """Raised when an authentication operation fails."""

    pass


class ConfigError(TinyCUAError):
    """Raised when a configuration operation fails."""

    pass


class SyncError(TinyCUAError):
    """Raised when a sync operation fails."""

    pass
