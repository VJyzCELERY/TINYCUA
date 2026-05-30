"""Unit tests for each tinycua.state object type and validation rule."""

from __future__ import annotations

import json

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
    TaskList,
    TaskResult,
    WorkerConfig,
    WorkerResult,
)


# =========================================================================
# Session
# =========================================================================


class TestSessionUnit:
    """Unit tests for Session."""

    def test_minimal_construction(self):
        """Session can be constructed with required fields only."""
        session = Session(
            session_id="s-1",
            owner_type="primary",
            owner_name="user",
            chat_history=[],
            context="",
        )
        assert session.session_id == "s-1"
        assert session.owner_type == "primary"
        assert session.owner_name == "user"
        assert session.chat_history == []
        assert session.context == ""
        assert session.execution_log is None

    def test_with_execution_log(self):
        """Session with execution_log is constructed correctly."""
        log = ExecutionLog(entries=[])
        session = Session(
            session_id="s-2",
            owner_type="child",
            owner_name="worker",
            chat_history=[{"role": "user", "content": "hi"}],
            context="ctx",
            execution_log=log,
        )
        assert session.execution_log is not None
        assert session.execution_log.entries == []

    def test_invalid_owner_type(self):
        """Session rejects invalid owner_type."""
        with pytest.raises(ValueError, match="owner_type"):
            Session(
                session_id="s-3",
                owner_type="invalid",
                owner_name="test",
                chat_history=[],
                context="",
            )

    def test_to_dict_basic(self):
        """Session.to_dict returns expected structure."""
        session = Session(
            session_id="s-4",
            owner_type="primary",
            owner_name="user",
            chat_history=[{"role": "user", "content": "hello"}],
            context="## Context",
        )
        d = session.to_dict()
        assert d["session_id"] == "s-4"
        assert d["owner_type"] == "primary"
        assert d["execution_log"] is None

    def test_to_json_is_valid_json(self):
        """Session.to_json produces valid JSON."""
        session = Session(
            session_id="s-5",
            owner_type="primary",
            owner_name="user",
            chat_history=[],
            context="",
        )
        parsed = json.loads(session.to_json())
        assert parsed["session_id"] == "s-5"

    def test_from_dict_missing_required(self):
        """Session.from_dict raises error for missing required field."""
        with pytest.raises(ValueError, match="session_id"):
            Session.from_dict({
                "owner_type": "primary",
                "owner_name": "user",
                "chat_history": [],
                "context": "",
            })


# =========================================================================
# ContextEnhancedQuery
# =========================================================================


class TestContextEnhancedQueryUnit:
    """Unit tests for ContextEnhancedQuery."""

    def test_construction(self):
        """ContextEnhancedQuery can be constructed."""
        q = ContextEnhancedQuery(enhanced_query="What is AI?")
        assert q.enhanced_query == "What is AI?"

    def test_round_trip(self):
        """ContextEnhancedQuery round-trips through dict."""
        q = ContextEnhancedQuery(enhanced_query="Query")
        assert ContextEnhancedQuery.from_dict(q.to_dict()) == q


# =========================================================================
# ModeDecision
# =========================================================================


class TestModeDecisionUnit:
    """Unit tests for ModeDecision."""

    def test_all_modes(self):
        """All valid mode values are accepted."""
        for mode in ("primary_agent", "worker", "uncertain"):
            kwargs = {
                "mode": mode,
                "score": 0.5,
                "confidence": 0.5,
                "reasons": ["test"],
            }
            if mode == "uncertain":
                kwargs["uncertain_next_action"] = "ask_user"
            decision = ModeDecision(**kwargs)
            assert decision.mode == mode

    def test_mode_case_sensitive(self):
        """Mode validation is case-sensitive."""
        with pytest.raises(ValueError, match="mode"):
            ModeDecision(
                mode="Primary_Agent",
                score=0.5,
                confidence=0.5,
                reasons=["test"],
            )

    def test_uncertain_next_action_validation(self):
        """Uncertain next action is validated when provided."""
        with pytest.raises(ValueError, match="uncertain_next_action"):
            ModeDecision(
                mode="worker",
                score=0.5,
                confidence=0.5,
                reasons=["test"],
                uncertain_next_action="bad_action",
            )

    def test_to_dict_with_uncertain(self):
        """ModeDecision.to_dict with uncertain mode includes uncertain_next_action."""
        decision = ModeDecision(
            mode="uncertain",
            score=0.6,
            confidence=0.4,
            reasons=["unsure"],
            uncertain_next_action="ask_user",
        )
        d = decision.to_dict()
        assert d["uncertain_next_action"] == "ask_user"

    def test_from_dict_missing_uncertain_next_action(self):
        """from_dict raises for uncertain mode without next_action."""
        with pytest.raises(ValueError, match="uncertain_next_action is required"):
            ModeDecision.from_dict({
                "mode": "uncertain",
                "score": 0.5,
                "confidence": 0.5,
                "reasons": ["unsure"],
            })


# =========================================================================
# DigestedInformation
# =========================================================================


class TestDigestedInformationUnit:
    """Unit tests for DigestedInformation."""

    def test_required_only(self):
        """DigestedInformation with only required fields."""
        info = DigestedInformation(
            context_summary="Summary",
            key_points=["p1"],
        )
        assert info.context_summary == "Summary"
        assert info.key_points == ["p1"]
        assert info.advisory_instructions is None
        assert info.constraints is None
        assert info.known_gaps is None

    def test_all_fields(self):
        """DigestedInformation with all fields populated."""
        info = DigestedInformation(
            context_summary="Summary",
            key_points=["p1", "p2"],
            advisory_instructions="Do X",
            constraints=["c1"],
            known_gaps=["g1"],
        )
        assert info.advisory_instructions == "Do X"
        assert info.constraints == ["c1"]
        assert info.known_gaps == ["g1"]

    def test_empty_key_points(self):
        """DigestedInformation allows empty key_points."""
        info = DigestedInformation(
            context_summary="Summary",
            key_points=[],
        )
        assert info.key_points == []


# =========================================================================
# WorkerConfig
# =========================================================================


class TestWorkerConfigUnit:
    """Unit tests for WorkerConfig."""

    @pytest.mark.parametrize("effort", ["none", "high"])
    def test_valid_effort(self, effort):
        """Valid effort values are accepted."""
        config = WorkerConfig(effort=effort)
        assert config.effort == effort

    def test_invalid_effort(self):
        """WorkerConfig rejects invalid effort value."""
        with pytest.raises(ValueError, match="effort"):
            WorkerConfig(effort="medium")


# =========================================================================
# Task
# =========================================================================


class TestTaskUnit:
    """Unit tests for Task."""

    def test_leaf_task(self):
        """A leaf task has no nested tasks."""
        task = Task(
            task_id="t-1",
            name="Test",
            description="A test task",
            context="ctx",
            success_criteria=["done"],
            confidence=0.9,
        )
        assert task.tasks is None
        assert task.task_id == "t-1"

    def test_container_task(self):
        """A container task has nested sub-tasks."""
        child = Task(
            task_id="t-1.1",
            name="Child",
            description="Child task",
            context="ctx",
            success_criteria=["done"],
            confidence=0.8,
        )
        parent = Task(
            task_id="t-1",
            name="Parent",
            description="Parent task",
            context="ctx",
            success_criteria=["all done"],
            confidence=0.7,
            tasks=[child],
        )
        assert parent.tasks is not None
        assert len(parent.tasks) == 1
        assert parent.tasks[0].task_id == "t-1.1"

    def test_deeply_nested(self):
        """Task supports deep nesting."""
        level3 = Task(
            task_id="l3", name="L3", description="d", context="c",
            success_criteria=["x"], confidence=0.9,
        )
        level2 = Task(
            task_id="l2", name="L2", description="d", context="c",
            success_criteria=["x"], confidence=0.9,
            tasks=[level3],
        )
        level1 = Task(
            task_id="l1", name="L1", description="d", context="c",
            success_criteria=["x"], confidence=0.9,
            tasks=[level2],
        )
        assert level1.tasks[0].tasks[0].task_id == "l3"


# =========================================================================
# TaskList
# =========================================================================


class TestTaskListUnit:
    """Unit tests for TaskList."""

    def test_no_current_task(self):
        """TaskList can have no current_task_id."""
        task = Task(
            task_id="t-1", name="T1", description="d", context="c",
            success_criteria=["x"], confidence=0.9,
        )
        tl = TaskList(tasks=[task])
        assert tl.current_task_id is None

    def test_with_current_task(self):
        """TaskList tracks current_task_id."""
        task = Task(
            task_id="t-1", name="T1", description="d", context="c",
            success_criteria=["x"], confidence=0.9,
        )
        tl = TaskList(tasks=[task], current_task_id="t-1")
        assert tl.current_task_id == "t-1"


# =========================================================================
# TaskResult
# =========================================================================


class TestTaskResultUnit:
    """Unit tests for TaskResult."""

    @pytest.mark.parametrize("status", ["completed", "failed", "blocked"])
    def test_valid_status(self, status):
        """Valid status values are accepted."""
        result = TaskResult(task_id="t-1", status=status, result="ok")
        assert result.status == status

    def test_invalid_status(self):
        """TaskResult rejects invalid status."""
        with pytest.raises(ValueError, match="status"):
            TaskResult(task_id="t-1", status="invalid", result="x")

    def test_optional_fields(self):
        """TaskResult with all optional fields."""
        result = TaskResult(
            task_id="t-1",
            status="completed",
            result="Done",
            discovered_sequence_issues=["ordering"],
            uncertainty_notes=["unclear"],
        )
        assert result.discovered_sequence_issues == ["ordering"]
        assert result.uncertainty_notes == ["unclear"]


# =========================================================================
# ContextUpdate
# =========================================================================


class TestContextUpdateUnit:
    """Unit tests for ContextUpdate."""

    def test_construction(self):
        """ContextUpdate can be constructed with required fields."""
        cu = ContextUpdate(target_task_id="t-1", update="New context")
        assert cu.target_task_id == "t-1"
        assert cu.update == "New context"


# =========================================================================
# ReviewerDecision
# =========================================================================


class TestReviewerDecisionUnit:
    """Unit tests for ReviewerDecision."""

    @pytest.mark.parametrize("status", ["accepted", "retry", "replan", "escalate_user"])
    def test_valid_status(self, status):
        """Valid status values are accepted."""
        decision = ReviewerDecision(
            task_id="t-1", status=status, reason="ok", confidence=0.8,
        )
        assert decision.status == status

    def test_invalid_status(self):
        """ReviewerDecision rejects invalid status."""
        with pytest.raises(ValueError, match="status"):
            ReviewerDecision(
                task_id="t-1", status="invalid", reason="x", confidence=0.5,
            )

    def test_with_context_updates(self):
        """ReviewerDecision with context updates."""
        updates = [
            ContextUpdate(target_task_id="t-2", update="Update 1"),
        ]
        decision = ReviewerDecision(
            task_id="t-1",
            status="retry",
            reason="Needs more info",
            confidence=0.6,
            context_updates=updates,
            retry_instructions="Check sources",
        )
        assert len(decision.context_updates) == 1
        assert decision.retry_instructions == "Check sources"


# =========================================================================
# WorkerResult / AcceptedResult
# =========================================================================


class TestWorkerResultUnit:
    """Unit tests for WorkerResult and AcceptedResult."""

    def test_empty_accepted_results(self):
        """WorkerResult can have empty accepted_results."""
        wr = WorkerResult(accepted_results=[])
        assert wr.accepted_results == []

    def test_with_results(self):
        """WorkerResult with accepted results."""
        ar = AcceptedResult(task_id="t-1", name="Task 1", result="Output")
        wr = WorkerResult(accepted_results=[ar])
        assert len(wr.accepted_results) == 1
        assert wr.accepted_results[0].task_id == "t-1"


# =========================================================================
# AgentState
# =========================================================================


class TestAgentStateUnit:
    """Unit tests for AgentState."""

    def test_default_values(self):
        """AgentState uses default values correctly."""
        state = AgentState(active_agent="analyst")
        assert state.status == "idle"
        assert state.consecutive_failures == 0
        assert state.active_task_id is None
        assert state.resume_target is None

    def test_all_fields(self):
        """AgentState with all fields populated."""
        state = AgentState(
            active_agent="analyst",
            active_task_id="t-1",
            status="running",
            resume_target="continue",
            consecutive_failures=3,
        )
        assert state.active_agent == "analyst"
        assert state.active_task_id == "t-1"
        assert state.status == "running"
        assert state.consecutive_failures == 3

    def test_zero_failures(self):
        """AgentState allows zero consecutive_failures."""
        state = AgentState(active_agent="test", consecutive_failures=0)
        assert state.consecutive_failures == 0

    def test_negative_failures_rejected(self):
        """AgentState rejects negative consecutive_failures."""
        with pytest.raises(ValueError, match="consecutive_failures must be non-negative"):
            AgentState(active_agent="test", consecutive_failures=-1)

    @pytest.mark.parametrize(
        "status", ["idle", "running", "blocked", "terminated"],
    )
    def test_valid_statuses(self, status):
        """All valid AgentState statuses are accepted."""
        state = AgentState(active_agent="test", status=status)
        assert state.status == status

    def test_invalid_status(self):
        """AgentState rejects invalid status."""
        with pytest.raises(ValueError, match="status"):
            AgentState(active_agent="test", status="unknown")


# =========================================================================
# ExecutionLog / ExecutionLogEntry
# =========================================================================


class TestExecutionLogUnit:
    """Unit tests for ExecutionLog and ExecutionLogEntry."""

    def test_empty_log(self):
        """ExecutionLog can be empty."""
        log = ExecutionLog(entries=[])
        assert log.entries == []

    def test_with_entries(self):
        """ExecutionLog with entries."""
        entry = ExecutionLogEntry(
            action="run_task",
            outcome="success",
            decision="chose path A",
        )
        log = ExecutionLog(entries=[entry])
        assert log.entries[0].action == "run_task"
        assert log.entries[0].decision == "chose path A"

    def test_entry_without_decision(self):
        """ExecutionLogEntry can omit decision."""
        entry = ExecutionLogEntry(action="query", outcome="failure")
        assert entry.decision is None


# =========================================================================
# Serialization Edge Cases
# =========================================================================


class TestSerializationEdgeCases:
    """Edge case tests for serialization."""

    def test_empty_string_fields(self):
        """Empty string fields are preserved in round-trip."""
        task = Task(
            task_id="", name="", description="", context="",
            success_criteria=[], confidence=0.0,
        )
        restored = Task.from_dict(task.to_dict())
        assert restored == task

    def test_special_characters_in_strings(self):
        """Special characters in string fields survive JSON round-trip."""
        info = DigestedInformation(
            context_summary="Line1\nLine2\nTab\there",
            key_points=["Quote: \"hello\"", "Unicode: ñoño"],
        )
        restored = DigestedInformation.from_json(info.to_json())
        assert restored == info

    def test_very_nested_task_list(self):
        """Very deeply nested TaskList survives round-trip."""
        # Build 5 levels of nesting
        current = Task(
            task_id="l5", name="deep", description="d", context="c",
            success_criteria=["x"], confidence=0.5,
        )
        for i in range(4, 0, -1):
            current = Task(
                task_id=f"l{i}", name=f"L{i}", description="d", context="c",
                success_criteria=["x"], confidence=0.5,
                tasks=[current],
            )
        task_list = TaskList(tasks=[current], current_task_id="l1")
        restored = TaskList.from_json(task_list.to_json())
        assert restored == task_list

    def test_boolean_in_chat_history(self):
        """Booleans in chat_history dicts survive round-trip."""
        session = Session(
            session_id="s-1",
            owner_type="primary",
            owner_name="user",
            chat_history=[
                {"role": "user", "content": "hello", "is_final": True},
            ],
            context="",
        )
        restored = Session.from_json(session.to_json())
        assert restored == session
        assert restored.chat_history[0]["is_final"] is True

    def test_numeric_values_precision(self):
        """Float precision is maintained through JSON round-trip."""
        decision = ModeDecision(
            mode="worker",
            score=0.123456789,
            confidence=0.987654321,
            reasons=["test"],
        )
        restored = ModeDecision.from_json(decision.to_json())
        assert abs(restored.score - 0.123456789) < 1e-9

    def test_empty_list_fields(self):
        """Empty lists in various fields survive round-trip."""
        result = TaskResult(
            task_id="t-1",
            status="failed",
            result="Error",
            discovered_sequence_issues=[],
            uncertainty_notes=[],
        )
        restored = TaskResult.from_dict(result.to_dict())
        assert restored == result

    def test_none_vs_empty_list_optional_fields(self):
        """Optional list fields: None vs empty list are distinguished."""
        info_with_none = DigestedInformation(
            context_summary="S", key_points=["p"],
            constraints=None,
        )
        info_with_empty = DigestedInformation(
            context_summary="S", key_points=["p"],
            constraints=[],
        )
        assert info_with_none.constraints is None
        assert info_with_empty.constraints == []

        restored_none = DigestedInformation.from_dict(info_with_none.to_dict())
        restored_empty = DigestedInformation.from_dict(info_with_empty.to_dict())
        assert restored_none.constraints is None
        assert restored_empty.constraints == []
