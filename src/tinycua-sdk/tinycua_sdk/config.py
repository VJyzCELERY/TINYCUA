"""Compatibility shim - deprecated.

This module is deprecated. Use tinycua_sdk.core.config.SDKConfig instead.
See migration guide at docs/guides/migration.md
"""


def __getattr__(name):
    """Compatibility shim that raises ImportError with helpful migration message."""
    raise ImportError(
        f"tinycua_sdk.config is deprecated. "
        f"Import '{name}' from 'tinycua_sdk.core.config' instead. "
        f"See migration guide at docs/guides/migration.md"
    )


def __dir__():
    """Return empty list to prevent attribute access."""
    return []
