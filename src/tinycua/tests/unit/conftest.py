"""Shared fixtures for unit tests.

Provides a unified MockLLM and resource-limiting fixtures to prevent
test memory/CPU bloat.
"""

from __future__ import annotations

import os
import resource
from pathlib import Path
from typing import Any

import pytest

from tinycua.config.node_config import NodeConfigBase
from tinycua.agent.tools.native.context import bind_workspace
from tinycua.models.session import Session

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Unified MockLLM — supports all test patterns
# ---------------------------------------------------------------------------
class MockLLM:
    """Unified mock LLM client for all unit tests.

    Supports three usage patterns:

    1. **Single response** (simple ProcessNode tests):
       ``MockLLM(response="result")``

    2. **Sequential responses** (DecisionNode tests):
       ``MockLLM(responses=["analysis", "worker"])``

    3. **Per-node-id responses** (pipeline integration tests):
       ``MockLLM(node_responses={"qa": {...}, "digester": {...}})``

    Tracks call counts only — does NOT store message lists to avoid
    memory bloat across many test invocations.
    """

    def __init__(
        self,
        response: str | None = None,
        responses: list[str] | None = None,
        node_responses: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize MockLLM.

        Args:
            response: Single response returned for every call.
            responses: List of responses returned in sequence (cycles).
            node_responses: Per-node-id response dicts (detected via
                system message content).
        """
        if response is not None:
            self._responses: list[str] = [response]
        elif responses is not None:
            self._responses = responses
        else:
            self._responses = ["mock response"]

        self._node_responses = node_responses or {}
        self.call_count = 0
        self.last_messages: list[dict] | None = None
        self.all_messages: list[list[dict]] = []

    def __call__(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> dict[str, Any]:  # noqa: ARG002
        """Return the next configured response.

        If ``node_responses`` was provided, detect node from system
        message and return that node's response. Otherwise, cycle
        through the ``_responses`` list.
        """
        self.call_count += 1
        self.last_messages = messages
        self.all_messages.append(messages)

        if self._node_responses:
            node_id = self._detect_node(messages)
            if node_id in self._node_responses:
                return self._node_responses[node_id]

        idx = min(self.call_count - 1, len(self._responses) - 1)
        content = self._responses[idx]
        return {"role": "assistant", "content": content}

    def get_call_count(self, node_id: str) -> int:
        """Return call count for a specific node (per-node mode only)."""
        if not self._node_responses:
            return self.call_count
        count = 0
        for msgs in self.all_messages:
            if self._detect_node(msgs) == node_id:
                count += 1
        return count

    def _detect_node(self, messages: list[dict[str, str]]) -> str:
        """Detect which node the call belongs to from system message."""
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "").lower()
                if "query analyst" in content:
                    return "qa"
                if (
                    "information digester" in content
                    or "informationdigester" in content
                ):
                    return "digester"
                if "worker node" in content:
                    return "worker"
                if "task creation" in content:
                    return "task_create"
        return "unknown"


# ---------------------------------------------------------------------------
# Resource-limiting helpers
# ---------------------------------------------------------------------------
_DEFAULT_MEMORY_LIMIT_MB = int(os.environ.get("TEST_MEMORY_LIMIT_MB", "2048"))


def _get_rss_mb() -> float:
    """Get current RSS (Resident Set Size) in MB on Linux."""
    try:
        with open("/proc/self/statm") as f:
            parts = f.read().split()
        rss_pages = int(parts[1])
        page_size = resource.getpagesize()
        return (rss_pages * page_size) / (1024 * 1024)
    except (OSError, IndexError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def config() -> NodeConfigBase:
    """Create a NodeConfigBase with sensible defaults for tests."""
    cfg = NodeConfigBase()
    cfg.retry_policy.max_attempts = 1
    cfg.retry_policy.on_retry_exhausted = "record_failure"
    cfg.message_policy.include_session_context = True
    cfg.message_policy.include_chat_history = False
    cfg.custom_instruction_append = ""
    cfg.custom_retry_append = ""
    return cfg


@pytest.fixture()
def mock_llm() -> MockLLM:
    """Create a fresh single-response MockLLM."""
    return MockLLM()


@pytest.fixture()
def root_session() -> Session:
    """Create a fresh root session."""
    return Session()


@pytest.fixture()
def workspace_tmp(tmp_path: Path) -> Path:
    """Create a temp dir and bind it as the workspace for native tools.

    Milestone 5: native tools raise WorkspaceNotBoundError when the workspace
    is not bound. Tests that use file/shell tools MUST use this fixture.
    """
    bind_workspace(tmp_path)
    yield tmp_path
    bind_workspace(None)


@pytest.fixture(autouse=True)
def _resource_limits(request: pytest.FixtureRequest) -> Any:
    """Auto-applied fixture that monitors RSS after every test.

    Fails the test if RSS exceeds the configured limit.

    Configure via environment variables:
      - TEST_MEMORY_LIMIT_MB: RSS limit in MB (default: 2048)
    """
    bind_workspace(None)
    original_cwd = Path.cwd()
    mem_limit_mb = _DEFAULT_MEMORY_LIMIT_MB
    rss_before = _get_rss_mb()

    yield

    bind_workspace(None)
    os.chdir(original_cwd)

    rss_after = _get_rss_mb()
    rss_delta = rss_after - rss_before

    if rss_delta > mem_limit_mb * 0.5:
        import warnings

        warnings.warn(
            f"Test {request.node.name} RSS grew by {rss_delta:.1f}MB "
            f"(before={rss_before:.1f}MB, after={rss_after:.1f}MB). "
            f"Limit is {mem_limit_mb}MB.",
            stacklevel=1,
        )

    if rss_after > mem_limit_mb:
        pytest.fail(
            f"Test {request.node.name} exceeded memory limit: "
            f"RSS={rss_after:.1f}MB > {mem_limit_mb}MB"
        )
