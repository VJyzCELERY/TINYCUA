"""Shared constants for TinyCUA loop mixins.

Extracted from ``tinycua_loop.py`` so mixin modules can import them without
importing the main loop module (avoids a circular core<->mixin import).
"""

from __future__ import annotations

# Maximum sequential tool-call continuations within one node attempt before the
# loop treats the tool loop as a runaway and stops.
_MAX_TOOL_CONTINUATIONS = 6

# Sentinel used when retry_policy.max_attempts is None (unbounded): a number
# large enough that in practice it never trips, while keeping max_attempts an int.
_UNBOUNDED_RETRY_ATTEMPTS = 1_000_000_000
