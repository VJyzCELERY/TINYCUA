"""Compaction strategy package for TinyCUA."""

from tinycua.compaction.errors import CompactionError
from tinycua.compaction.simple import SimpleCompaction
from tinycua.compaction.strategy import CompactionStrategy

__all__ = [
    "CompactionError",
    "CompactionStrategy",
    "SimpleCompaction",
]
