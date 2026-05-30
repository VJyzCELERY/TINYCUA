"""Serialization round-trip tests for state objects serialization and validation."""

import pytest

from tinycua.state import (
    AcceptedResult,
    AgentState,
    ContextEnhancedQuery,
    ContextUpdate,
    DigestedInformation,
    ExecutionLog,
    ExecutionLogEntry,
    ModeDecision,
    ReviewerDecision,
    Session,
    Task,
    TaskResult,
    WorkerConfig,
    WorkerResult,
)


class TestModeDecision:
    """ModeDecision serialization and validation."""

    def test_json_round_trip(self):
        """ModeDecision survives JSON round-trip without data loss."""
        decision = ModeDecision(
            mode="uncertain",
            score=0.72,
            confidence=0.41,
            reasons=["low context", "conflicting signals"],
            uncertain_next_action="ask_user",
        )
        serialized = decision.to_json()
        restored = ModeDecision.from_json(serialized)
        assert restored == decision

    def test_dict_round_trip(self):
        """ModeDecision survives dict round-trip without data loss."""
        decision = ModeDecision(
            mode="primary_agent",
            score=0.95,
            confidence=0.88,
            reasons=["direct answer sufficient"],
        )
        restored = ModeDecision.from_dict(decision.to_dict())
        assert restored == decision

    def test_invalid_mode_raises(self):
        """ModeDecision rejects invalid mode value."""
        with pytest.raises(ValueError, match="Invalid value 'invalid' for field 'mode'"):
            ModeDecision(
                mode="invalid",
                score=0.5,
                confidence=0.5,
                reasons=["test"],
            )

    def test_missing_uncertain_next_action_raises(self):
        """ModeDecision raises error when mode='uncertain' without uncertain_next_action."""
        with pytest.raises(ValueError, match="uncertain_next_action is required when mode is 'uncertain'"):
            ModeDecision(
                mode="uncertain",
                score=0.5,
                confidence=0.5,
                reasons=["uncertain"],
            )

    def test_uncertain_next_action_allowed_when_not_uncertain(self):
        """ModeDecision allows uncertain_next_action even when mode is not 'uncertain'."""
        decision = ModeDecision(
            mode="worker",
            score=0.8,
            confidence=0.7,
            reasons=["needs decomposition"],
            uncertain_next_action="explore",
        )
        # Should not raise - consumer should ignore uncertain_next_action when mode != uncertain
        assert decision.uncertain_next_action == "explore"


class TestTaskTree:
    """Task tree node serialization."""

    def test_nested_round_trip_dict(self):
        """Nested Task tree structures round-trip through dict serialization."""
        leaf = Task(
            task_id="t-2",
            task_name="leaf",
            task_description="leaf task",
            task_context="ctx",
            success_criteria=["done"],
            confidence=0.9,
        )
        parent = Task(
            task_id="t-1",
            task_name="parent",
            task_description="container task",
            task_context="ctx",
            success_criteria=["all children done"],
            confidence=0.8,
            child_tasks=[leaf],
        )
        restored = Task.from_dict(parent.to_dict())
        assert restored == parent
        assert restored.child_tasks[0].task_id == "t-2"

    def test_nested_round_trip_json(self):
        """Nested Task tree structures round-trip through JSON serialization."""
        leaf = Task(
            task_id="t-2",
            task_name="leaf",
            task_description="leaf task",
            task_context="ctx",
            success_criteria=["done"],
            confidence=0.9,
        )
        parent = Task(
            task_id="t-1",
            task_name="parent",
            task_description="container task",
            task_context="ctx",
            success_criteria=["all children done"],
            confidence=0.8,
            child_tasks=[leaf],
        )
        restored = Task.from_json(parent.to_json())
        assert restored == parent
        assert restored.child_tasks[0].task_id == "t-2"

    def test_tree_preserves_finished_flags(self):
        """Tree round-trip preserves finished flags."""
        leaf = Task(
            task_id="t-2", task_name="leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            finished=True,
        )
        parent = Task(
            task_id="t-1", task_name="parent", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[leaf],
        )
        restored = Task.from_dict(parent.to_dict())
        assert restored.child_tasks[0].finished is True
        assert restored.finished is False

    def test_tree_preserves_parent_task_id(self):
        """Tree round-trip preserves parent_task_id after auto-setting."""
        leaf = Task(
            task_id="t-2", task_name="leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        parent = Task(
            task_id="t-1", task_name="parent", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[leaf],
        )
        restored = Task.from_dict(parent.to_dict())
        assert restored.child_tasks[0].parent_task_id == "t-1"


class TestSession:
    """Session serialization and validation."""

    def test_json_round_trip(self):
        """Session survives JSON round-trip."""
        session = Session(
            session_id="sess-1",
            owner_type="primary",
            owner_name="user",
            chat_history=[{"type": "user", "message": "hello"}],
            context="# Context\nSome context",
        )
        restored = Session.from_json(session.to_json())
        assert restored == session

    def test_dict_round_trip_with_execution_log(self):
        """Session with execution_log round-trips through dict."""
        log = ExecutionLog(entries=[
            ExecutionLogEntry(action="run_task", outcome="success"),
        ])
        session = Session(
            session_id="sess-2",
            owner_type="child",
            owner_name="worker",
            chat_history=[],
            context="",
            execution_log=log,
        )
        restored = Session.from_dict(session.to_dict())
        assert restored == session
        assert restored.execution_log is not None
        assert len(restored.execution_log.entries) == 1

    def test_invalid_owner_type_raises(self):
        """Session rejects invalid owner_type."""
        with pytest.raises(ValueError, match="owner_type"):
            Session(
                session_id="sess-3",
                owner_type="invalid",
                owner_name="test",
                chat_history=[],
                context="",
            )


class TestDigestedInformation:
    """DigestedInformation serialization."""

    def test_round_trip_with_all_fields(self):
        """DigestedInformation round-trips with all optional fields."""
        info = DigestedInformation(
            context_summary="Summary",
            key_points=["point 1", "point 2"],
            advisory_instructions="Do X",
            constraints=["constraint 1"],
            known_gaps=["gap 1"],
        )
        restored = DigestedInformation.from_dict(info.to_dict())
        assert restored == info

    def test_round_trip_with_optional_fields_omitted(self):
        """DigestedInformation round-trips with optional fields omitted."""
        info = DigestedInformation(
            context_summary="Summary",
            key_points=["point 1"],
        )
        assert info.advisory_instructions is None
        assert info.constraints is None
        assert info.known_gaps is None
        restored = DigestedInformation.from_dict(info.to_dict())
        assert restored == info


class TestWorkerConfig:
    """WorkerConfig validation and serialization."""

    def test_round_trip(self):
        """WorkerConfig round-trips through dict."""
        config = WorkerConfig(effort="high")
        restored = WorkerConfig.from_dict(config.to_dict())
        assert restored == config

    def test_invalid_effort_raises(self):
        """WorkerConfig rejects invalid effort value."""
        with pytest.raises(ValueError, match="effort"):
            WorkerConfig(effort="medium")


class TestTaskResult:
    """TaskResult validation and serialization."""

    def test_round_trip(self):
        """TaskResult round-trips through dict."""
        result = TaskResult(
            task_id="t-1",
            status="completed",
            result="Done",
            discovered_sequence_issues=["issue 1"],
            uncertainty_notes=["note 1"],
        )
        restored = TaskResult.from_dict(result.to_dict())
        assert restored == result

    def test_round_trip_minimal(self):
        """TaskResult round-trips with only required fields."""
        result = TaskResult(
            task_id="t-1",
            status="failed",
            result="Error",
        )
        restored = TaskResult.from_dict(result.to_dict())
        assert restored == result

    def test_invalid_status_raises(self):
        """TaskResult rejects invalid status."""
        with pytest.raises(ValueError, match="status"):
            TaskResult(task_id="t-1", status="invalid", result="x")


class TestReviewerDecision:
    """ReviewerDecision validation and serialization."""

    def test_round_trip(self):
        """ReviewerDecision round-trips through dict."""
        decision = ReviewerDecision(
            task_id="t-1",
            status="accepted",
            reason="Good work",
            confidence=0.9,
            context_updates=[
                ContextUpdate(target_task_id="t-2", update="Update context"),
            ],
            retry_instructions="None needed",
        )
        restored = ReviewerDecision.from_dict(decision.to_dict())
        assert restored == decision

    def test_rejects_invalid_status(self):
        """ReviewerDecision validation rejects unsupported status values."""
        with pytest.raises(ValueError, match="status"):
            ReviewerDecision(
                task_id="t-1",
                status="invalid_value",
                reason="bad status",
                confidence=0.2,
            )


class TestWorkerResult:
    """WorkerResult serialization."""

    def test_round_trip(self):
        """WorkerResult round-trips through dict."""
        result = WorkerResult(
            accepted_results=[
                AcceptedResult(task_id="t-1", name="Task 1", result="Output 1"),
            ],
        )
        restored = WorkerResult.from_dict(result.to_dict())
        assert restored == result


class TestAgentState:
    """AgentState validation and serialization."""

    def test_round_trip(self):
        """AgentState round-trips through dict."""
        state = AgentState(
            active_agent="analyst",
            active_task_id="t-1",
            status="running",
            resume_target="continue",
            consecutive_failures=0,
        )
        restored = AgentState.from_dict(state.to_dict())
        assert restored == state

    def test_round_trip_defaults(self):
        """AgentState round-trips with default values."""
        state = AgentState(active_agent="analyst")
        assert state.status == "idle"
        assert state.consecutive_failures == 0
        restored = AgentState.from_dict(state.to_dict())
        assert restored == state

    def test_rejects_negative_consecutive_failures(self):
        """AgentState rejects negative consecutive_failures."""
        with pytest.raises(ValueError, match="consecutive_failures must be non-negative"):
            AgentState(
                active_agent="test",
                consecutive_failures=-1,
            )

    def test_invalid_status_raises(self):
        """AgentState rejects invalid status."""
        with pytest.raises(ValueError, match="status"):
            AgentState(
                active_agent="test",
                status="invalid_status",
            )


class TestExecutionLog:
    """ExecutionLog serialization."""

    def test_round_trip(self):
        """ExecutionLog round-trips through dict."""
        log = ExecutionLog(
            entries=[
                ExecutionLogEntry(action="query", outcome="success", decision="chose path A"),
                ExecutionLogEntry(action="process", outcome="failure"),
            ],
        )
        restored = ExecutionLog.from_dict(log.to_dict())
        assert restored == log


class TestContextEnhancedQuery:
    """ContextEnhancedQuery serialization."""

    def test_round_trip(self):
        """ContextEnhancedQuery round-trips through dict."""
        query = ContextEnhancedQuery(enhanced_query="What is the capital of France?")
        restored = ContextEnhancedQuery.from_dict(query.to_dict())
        assert restored == query


class TestCrossObjectRoundTrips:
    """Cross-object serialization scenarios."""

    def test_session_with_full_state(self):
        """End-to-end test: Session with nested state objects round-trips."""
        execution_log = ExecutionLog(
            entries=[
                ExecutionLogEntry(action="execute", outcome="complete"),
            ],
        )
        session = Session(
            session_id="full-sess",
            owner_type="primary",
            owner_name="user",
            chat_history=[{"role": "user", "content": "research X"}],
            context="## Context\nResearch context",
            execution_log=execution_log,
        )
        restored = Session.from_json(session.to_json())
        assert restored == session
