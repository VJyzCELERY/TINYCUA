"""Unified storage layer for sessions and messages.

.. deprecated::
    Import SessionStore from tinycua_sdk.storage.store instead.
    This module will be removed in a future version.
"""

import warnings
import traceback

# Only warn if directly imported from user code (not from submodules)
# The logic: warn if the import is from user code AND NOT from storage.store
# We check if storage.store is in the stack - if it is, this is a valid import
_stack = traceback.extract_stack()
_has_store_submodule = any("storage.store" in frame.filename for frame in _stack)
# Check for direct import from <string> or from test files (pytest runs tests from files)
_is_direct_import = any(
    "<string>" in frame.filename or frame.filename.endswith(".py") for frame in _stack
)

# Warn only if it's a direct import AND not from storage.store
if _is_direct_import and not _has_store_submodule:
    warnings.warn(
        "Importing SessionStore from tinycua_sdk.storage is deprecated. "
        "Use tinycua_sdk.storage.store.SessionStore instead. "
        "This module will be removed in a future version.",
        DeprecationWarning,
        stacklevel=2,
    )

from tinycua_sdk.storage.store import SessionStore, get_session_store  # noqa: E402
from tinycua_sdk.storage.snapshot import MemorySnapshot, SnapshotManager, SnapshotError  # noqa: E402

__all__ = [
    "SessionStore",
    "get_session_store",
    "MemorySnapshot",
    "SnapshotManager",
    "SnapshotError",
]
