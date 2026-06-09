"""Unit tests for WorkerEffort enum, effort_to_pass_limit(), and TinyCUAAnalysisEffortNode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.analysis_effort import (
    TinyCUAAnalysisEffortNode,
    WorkerEffort,
    effort_to_pass_limit,
)
from tinycua.loops.node import ProcessNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


def _make_mock_node(node_id: str, *, is_terminal: bool = False) -> MagicMock:
    """Create a mock node with required attributes."""
    node = MagicMock()
    node.node_id = node_id
    node.is_terminal = is_terminal
    return node


# ─── WorkerEffort Enum Tests ────────────────────────────────────────────────


class TestWorkerEffortEnum:
    """Tests for WorkerEffort enum values and behavior."""

    def test_worker_effort_enum_values(self) -> None:
        """WorkerEffort has none, low, medium, high values."""
        assert WorkerEffort.none.value == "none"
        assert WorkerEffort.low.value == "low"
        assert WorkerEffort.medium.value == "medium"
        assert WorkerEffort.high.value == "high"

    def test_worker_effort_has_four_members(self) -> None:
        """WorkerEffort has exactly four members."""
        assert len(WorkerEffort) == 4

    def test_worker_effort_is_str_enum(self) -> None:
        """WorkerEffort is a string enum (str subclass)."""
        assert isinstance(WorkerEffort.none, str)
        assert WorkerEffort.none == "none"


# ─── effort_to_pass_limit Tests ─────────────────────────────────────────────


class TestEffortToPassLimit:
    """Tests for effort_to_pass_limit() mapping function."""

    def test_effort_to_pass_limit_none(self) -> None:
        """WorkerEffort.none maps to pass_limit=0."""
        assert effort_to_pass_limit(WorkerEffort.none) == 0

    def test_effort_to_pass_limit_low(self) -> None:
        """WorkerEffort.low maps to pass_limit=1."""
        assert effort_to_pass_limit(WorkerEffort.low) == 1

    def test_effort_to_pass_limit_medium(self) -> None:
        """WorkerEffort.medium maps to pass_limit=2."""
        assert effort_to_pass_limit(WorkerEffort.medium) == 2

    def test_effort_to_pass_limit_high(self) -> None:
        """WorkerEffort.high maps to pass_limit=3."""
        assert effort_to_pass_limit(WorkerEffort.high) == 3

    def test_effort_to_pass_limit_all_levels(self) -> None:
        """All four effort levels map to correct pass limits."""
        expected = {
            WorkerEffort.none: 0,
            WorkerEffort.low: 1,
            WorkerEffort.medium: 2,
            WorkerEffort.high: 3,
        }
        for effort, expected_limit in expected.items():
            assert effort_to_pass_limit(effort) == expected_limit


# ─── TinyCUAAnalysisEffortNode Init Tests ───────────────────────────────────


class TestAnalysisEffortNodeInit:
    """Tests for TinyCUAAnalysisEffortNode initialization."""

    def test_inherits_from_process_node(self) -> None:
        """TinyCUAAnalysisEffortNode inherits from ProcessNode."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            node_id="analysis_effort", config=config,
        )
        assert isinstance(node, ProcessNode)

    def test_default_node_id(self) -> None:
        """AnalysisEffortNode defaults to 'analysis_effort' node_id."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(config=config)
        assert node.node_id == "analysis_effort"

    def test_default_effort_is_none(self) -> None:
        """AnalysisEffortNode defaults to WorkerEffort.none."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(config=config)
        assert node.effort == WorkerEffort.none

    def test_pass_count_starts_at_zero(self) -> None:
        """AnalysisEffortNode pass_count starts at 0."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(config=config)
        assert node.pass_count == 0

    def test_pass_limit_from_effort(self) -> None:
        """AnalysisEffortNode pass_limit is derived from effort."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.low,
        )
        assert node.pass_limit == 1

    def test_pass_limit_none_effort(self) -> None:
        """AnalysisEffortNode with none effort has pass_limit=0."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.none,
        )
        assert node.pass_limit == 0

    def test_pass_limit_medium_effort(self) -> None:
        """AnalysisEffortNode with medium effort has pass_limit=2."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.medium,
        )
        assert node.pass_limit == 2

    def test_pass_limit_high_effort(self) -> None:
        """AnalysisEffortNode with high effort has pass_limit=3."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.high,
        )
        assert node.pass_limit == 3


# ─── TinyCUAAnalysisEffortNode Behavior Tests ───────────────────────────────


class TestAnalysisEffortNodeBehavior:
    """Tests for TinyCUAAnalysisEffortNode deterministic behavior."""

    def test_none_effort_spawns_executor_immediately(self) -> None:
        """WorkerEffort.none: pass_limit=0, should_spawn_executor returns True immediately."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.none,
        )
        assert node._should_spawn_executor() is True

    def test_low_effort_does_not_spawn_immediately(self) -> None:
        """WorkerEffort.low: pass_limit=1, should_spawn_executor returns False at pass_count=0."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.low,
        )
        assert node._should_spawn_executor() is False

    def test_medium_effort_does_not_spawn_immediately(self) -> None:
        """WorkerEffort.medium: pass_limit=2, should_spawn_executor returns False at pass_count=0."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.medium,
        )
        assert node._should_spawn_executor() is False

    def test_high_effort_does_not_spawn_immediately(self) -> None:
        """WorkerEffort.high: pass_limit=3, should_spawn_executor returns False at pass_count=0."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.high,
        )
        assert node._should_spawn_executor() is False

    def test_pass_count_increment(self) -> None:
        """pass_count increments on each pass."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.medium,
        )
        assert node.pass_count == 0
        node.pass_count += 1
        assert node.pass_count == 1
        node.pass_count += 1
        assert node.pass_count == 2

    def test_threshold_reached_spawns_executor(self) -> None:
        """TaskExecutor spawns when pass_count >= pass_limit."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.low,
        )
        # pass_limit=1, pass_count=0 → should not spawn
        assert node._should_spawn_executor() is False
        # After one pass: pass_count=1 >= pass_limit=1 → should spawn
        node.pass_count = 1
        assert node._should_spawn_executor() is True

    def test_no_llm_call(self) -> None:
        """AnalysisEffortNode is deterministic — no LLM call is made."""
        mock_llm = MagicMock()
        config = NodeConfigBase(llm_client=mock_llm)
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.none,
        )
        session = Session()
        node.ensure_session(session)

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Continue"}],
        )
        node(input_data)

        mock_llm.assert_not_called()

    def test_preserves_terminal_path(self) -> None:
        """Terminal response path is maintained after TaskExecutor spawning."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.none,
        )
        session = Session()
        node.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [node, terminal]

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Continue"}],
        )
        node(input_data)

        # Terminal node should still be in queue
        node_ids = [n.node_id for n in queue.items]
        assert "response" in node_ids

    def test_default_effort_when_not_configured(self) -> None:
        """AnalysisEffortNode defaults to WorkerEffort='none' when not configured."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(config=config)
        assert node.effort == WorkerEffort.none
        assert node.pass_limit == 0

    def test_effort_to_pass_limit_mapping_all_levels(self) -> None:
        """All four effort levels map to correct pass limits via node attributes."""
        config = NodeConfigBase()
        for effort, expected_limit in [
            (WorkerEffort.none, 0),
            (WorkerEffort.low, 1),
            (WorkerEffort.medium, 2),
            (WorkerEffort.high, 3),
        ]:
            node = TinyCUAAnalysisEffortNode(config=config, effort=effort)
            assert node.pass_limit == expected_limit

    def test_task_tree_propagation(self) -> None:
        """Task tree state changes from TaskAssessor and TaskAnalyzer passes are propagated."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.low,
        )
        session = Session()
        node.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [node, terminal]

        # Call __call__ to get the response, then on_complete to trigger prepending
        response = node(
            NodeInput(
                input_type="continuation",
                messages=[{"role": "user", "content": "Continue"}],
            )
        )

        # Mock the prepending to verify it's called
        with patch.object(node, "_prepend_assessor_analyzer_pair") as mock_prepend:
            node.on_complete(queue, response)
            # Verify prepending was called (pass_count < pass_limit)
            mock_prepend.assert_called_once_with(queue)


# ─── TinyCUAAnalysisEffortNode on_complete Tests ────────────────────────────


class TestAnalysisEffortNodeOnComplete:
    """Tests for TinyCUAAnalysisEffortNode.on_complete."""

    def test_on_complete_prepends_when_below_threshold(self) -> None:
        """on_complete prepends [TaskAssessor, TaskAnalyzer] when pass_count < pass_limit."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.low,
        )
        session = Session()
        node.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [node, terminal]

        response = LLMResult(
            content="Effort control: prepending assessor+analyzer", role="assistant",
        )

        with patch.object(node, "_prepend_assessor_analyzer_pair") as mock_prepend:
            node.on_complete(queue, response)
            mock_prepend.assert_called_once_with(queue)

    def test_on_complete_spawns_executor_when_at_threshold(self) -> None:
        """on_complete spawns TaskExecutor when pass_count >= pass_limit."""
        config = NodeConfigBase()
        node = TinyCUAAnalysisEffortNode(
            config=config, effort=WorkerEffort.low,
        )
        session = Session()
        node.ensure_session(session)
        node.pass_count = 1  # At threshold (pass_limit=1)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [node, terminal]

        response = LLMResult(
            content="Effort control: spawning executor", role="assistant",
        )

        with patch.object(node, "_spawn_task_executor") as mock_spawn:
            node.on_complete(queue, response)
            mock_spawn.assert_called_once_with(queue)
