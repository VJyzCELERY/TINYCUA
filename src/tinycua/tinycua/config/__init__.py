"""Configuration dataclasses for TinyCUA."""

from tinycua.compaction.errors import CompactionError
from tinycua.compaction.simple import SimpleCompaction
from tinycua.compaction.strategy import CompactionStrategy
from tinycua.config.local_model import LocalModelConfig
from tinycua.config.node_config import (
    NodeConfigBase,
    NodeMessagePolicy,
    NodeRetryPolicy,
    NodeStreamPolicy,
    NodeToolPolicy,
)
from tinycua.config.session_config import SessionConfig
from tinycua.config.system_prompt import SystemPrompt, SystemPromptBuilder
from tinycua.config.types import StateObject, Tool

__all__ = [
    "SessionConfig",
    "CompactionStrategy",
    "SimpleCompaction",
    "CompactionError",
    "Tool",
    "StateObject",
    "NodeConfigBase",
    "NodeMessagePolicy",
    "NodeToolPolicy",
    "NodeStreamPolicy",
    "NodeRetryPolicy",
    "SystemPrompt",
    "SystemPromptBuilder",
    "LocalModelConfig",
]
