"""Root conftest for tinycua test suite.

Sets a per-process memory limit to catch memory bloat early.
Unit tests should never need more than 256 MB; if they do,
the limit can be raised after investigating the cause.
"""

from __future__ import annotations

import os
import resource

import pytest

# 2 GB virtual-memory cap per test process.
# Catches infinite-loop / unbounded-growth bugs before they hang CI.
_MEMORY_LIMIT_MB = 2048
_MEMORY_LIMIT_BYTES = _MEMORY_LIMIT_MB * 1024 * 1024


def _apply_memory_limit() -> None:
    """Set RLIMIT_AS (virtual memory) if not already constrained tighter."""
    if os.name != "posix":
        return  # resource module is POSIX-only

    current_soft, current_hard = resource.getrlimit(resource.RLIMIT_AS)

    # Only tighten — never widen an existing limit.
    if current_soft != resource.RLIM_INFINITY and current_soft <= _MEMORY_LIMIT_BYTES:
        return

    new_hard = min(current_hard, _MEMORY_LIMIT_BYTES)
    resource.setrlimit(resource.RLIMIT_AS, (_MEMORY_LIMIT_BYTES, new_hard))


_apply_memory_limit()


@pytest.fixture(autouse=True)
def _enforce_memory_limit() -> None:  # noqa: PT004
    """Re-apply the memory limit before every test (safety net).

    Some tests or fixtures might call setrlimit themselves; this
    ensures the cap is always in place.
    """
    _apply_memory_limit()
