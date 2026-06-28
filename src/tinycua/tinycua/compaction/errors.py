"""Compaction error types."""

from __future__ import annotations


class CompactionError(Exception):
    """Raised when compaction fails.

    This exception is raised when the compaction Agent is unreachable,
    returns an invalid response, or encounters any internal failure during
    the compaction process.
    """
