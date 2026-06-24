"""Shared constants for TinyCUA loop mixins.

Extracted from ``tinycua_loop.py`` so mixin modules can import them without
importing the main loop module (avoids a circular core<->mixin import).
"""

from __future__ import annotations

# Maximum sequential tool-call continuations within one node attempt before the
# loop treats the tool loop as a runaway and stops.
_MAX_TOOL_CONTINUATIONS = 6

# FR-086: maximum catch-and-retry attempts when the LLM provider raises an
# error (context overflow, 500, network blip). After this many retries within
# one attempt, the exception re-raises and the app crashes (same as today,
# but only after recovery attempts). Each retry forces a compaction to shrink
# the prompt before retrying.
_MAX_PROVIDER_RETRIES = 3

# Sentinel used when retry_policy.max_attempts is None (unbounded): a number
# large enough that in practice it never trips, while keeping max_attempts an int.
_UNBOUNDED_RETRY_ATTEMPTS = 1_000_000_000
