"""Tests for runtime context in TinyCUA node system prompts."""

from datetime import UTC, datetime

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.system_prompt import build_runtime_context
from tinycua.loops.node import ProcessNode
from tinycua.models.session import Session


def test_build_runtime_context_formats_time_and_timezone() -> None:
    """Runtime context exposes date/time and timezone without extra dependencies."""
    context = build_runtime_context(datetime(2026, 6, 19, 5, 0, tzinfo=UTC))

    assert "## Runtime Context" in context
    assert "Current date/time: 2026-06-19 05:00:00 +0000" in context
    assert "Timezone: UTC (+0000)" in context


def test_node_system_message_includes_runtime_context() -> None:
    """Every node system prompt gets the runtime context fragment."""
    node = ProcessNode("x", NodeConfigBase(), instruction="Do the task.")

    messages = node.build_messages(Session(), {})

    system = messages[0]
    assert system["role"] == "system"
    assert "Do the task." in system["content"]
    assert "## Runtime Context" in system["content"]
    assert "Current date/time:" in system["content"]
    assert "Timezone:" in system["content"]
