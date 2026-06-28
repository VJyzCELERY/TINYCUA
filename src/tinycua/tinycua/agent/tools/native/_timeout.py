"""Shared timeout-bounding helper for native tools.

Centralises the ``int(timeout)`` parse + clamp/reject pattern duplicated
between ``shell._bounded_timeout`` (clamps to [1, max]) and
``python_exec._bounded_timeout`` (returns None to signal rejection above
max). The two tools have different overflow policies; this helper
parameterises the policy so both call sites share the parse logic.
"""

from __future__ import annotations


def bounded_timeout(
    timeout: int,
    default: int,
    max_seconds: int,
    *,
    reject_overflow: bool = False,
) -> int | None:
    """Return a safe timeout, or None to signal rejection above the max.

    Args:
        timeout: The requested timeout (may be a string from LLM tool calls).
        default: Returned when ``timeout`` can't be parsed as an int.
        max_seconds: The upper bound. Values above this are either clamped
            (when ``reject_overflow=False``) or cause a None return (when
            ``reject_overflow=True``) so the caller can reject with an error.
        reject_overflow: When True, return None for requests above
            ``max_seconds``. When False, clamp to ``max_seconds``.

    Returns:
        The bounded timeout (>= 1), or None when ``reject_overflow`` is True
        and the requested timeout exceeds ``max_seconds``.
    """
    try:
        requested = int(timeout)
    except (TypeError, ValueError):
        return default
    if reject_overflow and requested > max_seconds:
        return None
    return min(max(requested, 1), max_seconds)
