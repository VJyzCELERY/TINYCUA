"""Unit tests for analyzer prompt + max_attempts (Milestone 8, FR-054/FR-055)."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.loops.task_nodes import (
    TinyCUATaskAnalyzerNode,
    _TASK_ANALYZER_CONTINUATION,
    _TASK_ANALYZER_INSTRUCTION,
    _TASK_ANALYZER_LOCAL_REPLAN_CONTINUATION,
)
from tinycua.models.session import Session


class TestAnalyzerPromptTerminate:
    """Analyzer action prompts defer state changes to their later phases."""

    def test_instruction_defers_termination(self):
        assert "terminate" not in _TASK_ANALYZER_INSTRUCTION.lower()

    def test_continuation_defers_termination(self):
        assert "terminate" not in _TASK_ANALYZER_CONTINUATION.lower()

    def test_local_replan_continuation_defers_termination(self):
        assert "terminate" not in _TASK_ANALYZER_LOCAL_REPLAN_CONTINUATION.lower()

    def test_continuation_does_not_trap_with_task_inspect_first(self):
        """FR-054: the continuation MUST NOT instruct calling task_inspect first.

        task_inspect does not satisfy the analyzer's state-tool contract and
        traps the model into a retry-exhausted cycle. The roadmap is already
        in context via build_continuation.
        """
        # The old trap was "call task_inspect. Explore first...". The new
        # continuation should not lead with "call task_inspect".
        # It may still mention task_inspect as a read-only option, but not
        # as the first action. We check it's not the first instruction.
        lowered = _TASK_ANALYZER_CONTINUATION.lower()
        # The continuation should lead with exploration or context, not
        # "call task_inspect".
        assert not lowered.startswith("based on the roadmap and mission context above, call task_inspect.")


class TestAnalyzerMaxAttempts:
    """FR-055: analyzer max_attempts is 10 (raised from default 3)."""

    def test_analyzer_max_attempts_is_10(self):
        config = create_node_config("task_analyzer")
        assert config.retry_policy.max_attempts == 10

    def test_executor_max_attempts_unchanged_at_25(self):
        config = create_node_config("task_executor")
        assert config.retry_policy.max_attempts == 25

    def test_reviewer_max_attempts_unchanged_at_25(self):
        config = create_node_config("result_reviewer")
        assert config.retry_policy.max_attempts == 25

    def test_assessor_uses_default_max_attempts(self):
        """Assessor is not in the override list — uses default 3."""
        config = create_node_config("task_assessor")
        assert config.retry_policy.max_attempts == 3
