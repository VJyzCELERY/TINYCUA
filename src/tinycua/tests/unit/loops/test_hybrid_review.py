"""Unit tests for HybridReviewLoop."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua.loops import HybridReviewLoop, CheckResult


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM that returns predictable responses."""

    async def _call_llm(
        messages: list[dict], tools: list, **kwargs: object
    ) -> dict:
        return {
            "content": (
                '{\n'
                '  "status": "accepted",\n'
                '  "reason": "Task completed successfully with valid output.",\n'
                '  "confidence": 0.92\n'
                '}'
            ),
            "tool_calls": None,
        }

    return AsyncMock(side_effect=_call_llm)


@pytest.fixture
def mock_agent(mock_llm: AsyncMock) -> MagicMock:
    """Mock agent for hybrid review tests."""
    agent = MagicMock()
    agent.name = "test_reviewer"
    agent.instructions = "You are a result reviewer."
    agent.skills = []
    agent.is_cancelled = False
    agent.policy.max_tool_calls = 100
    agent._call_llm = mock_llm
    return agent


@pytest.fixture
def sample_task() -> dict:
    return {
        "task_id": "task-001",
        "description": "Analyze quarterly financial data",
        "status": "completed",
        "assigned_to": "worker",
    }


@pytest.fixture
def sample_passed_result() -> dict:
    return {
        "task_id": "task-001",
        "status": "completed",
        "output": "Analysis complete. Revenue growth of 15% QoQ.",
        "error": None,
    }


@pytest.fixture
def sample_failed_result() -> dict:
    return {
        "task_id": "task-001",
        "status": "failed",
        "output": "Missing required field: revenue_data",
        "error": "Schema validation failed",
    }


class TestHybridReviewLoop:
    """Test HybridReviewLoop construction and run()."""

    def test_default_construction(self) -> None:
        """HybridReviewLoop can be constructed with default params."""
        loop = HybridReviewLoop()
        assert loop.max_iterations == 3
        assert loop.deterministic_checks == []
        assert loop.consecutive_failure_threshold == 3

    def test_custom_construction(self) -> None:
        """HybridReviewLoop accepts custom params."""
        checks = [lambda t, r: CheckResult("test", True, "ok")]
        loop = HybridReviewLoop(
            max_iterations=5,
            deterministic_checks=checks,
            consecutive_failure_threshold=2,
        )
        assert loop.max_iterations == 5
        assert len(loop.deterministic_checks) == 1
        assert loop.consecutive_failure_threshold == 2

    @pytest.mark.asyncio
    async def test_deterministic_short_circuit(
        self,
        mock_agent: MagicMock,
        sample_task: dict,
        sample_failed_result: dict,
        mock_llm: AsyncMock,
    ) -> None:
        """Deterministic check failure short-circuits without LLM call."""
        def failing_check(task: dict, task_result: dict) -> CheckResult:
            return CheckResult(
                check_name="schema_validity",
                passed=False,
                reason="Missing required field",
                decision_override="retry",
            )

        loop = HybridReviewLoop(deterministic_checks=[failing_check])
        decision = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            task=sample_task,
            task_result=sample_failed_result,
        )
        assert decision.status == "retry"
        assert decision.reason
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_checks_pass(
        self,
        mock_agent: MagicMock,
        sample_task: dict,
        sample_passed_result: dict,
    ) -> None:
        """When all deterministic checks pass, LLM review is performed."""
        def passing_check(task: dict, task_result: dict) -> CheckResult:
            return CheckResult(
                check_name="schema_validity",
                passed=True,
                reason="All fields present",
            )

        loop = HybridReviewLoop(deterministic_checks=[passing_check])
        decision = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            task=sample_task,
            task_result=sample_passed_result,
            execution_log=None,
        )
        assert decision.status in ("accepted", "retry", "replan", "escalate_user")
        assert decision.reason

    @pytest.mark.asyncio
    async def test_escalate_on_failure(
        self,
        mock_agent: MagicMock,
        sample_task: dict,
        sample_failed_result: dict,
    ) -> None:
        """Check with escalate_user override results in escalate decision."""
        def escalate_check(task: dict, task_result: dict) -> CheckResult:
            return CheckResult(
                check_name="critical_error",
                passed=False,
                reason="Critical system error detected",
                decision_override="escalate_user",
            )

        loop = HybridReviewLoop(deterministic_checks=[escalate_check])
        decision = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            task=sample_task,
            task_result=sample_failed_result,
        )
        assert decision.status == "escalate_user"
        assert "Critical" in decision.reason

    @pytest.mark.asyncio
    async def test_replan_on_failure(
        self,
        mock_agent: MagicMock,
        sample_task: dict,
        sample_failed_result: dict,
    ) -> None:
        """Check with replan override results in replan decision."""
        def replan_check(task: dict, task_result: dict) -> CheckResult:
            return CheckResult(
                check_name="scope_change",
                passed=False,
                reason="Requirements changed mid-execution",
                decision_override="replan",
            )

        loop = HybridReviewLoop(deterministic_checks=[replan_check])
        decision = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            task=sample_task,
            task_result=sample_failed_result,
        )
        assert decision.status == "replan"
        assert "Requirements" in decision.reason

    @pytest.mark.asyncio
    async def test_multiple_checks_first_failure_wins(
        self,
        mock_agent: MagicMock,
        sample_task: dict,
        sample_failed_result: dict,
    ) -> None:
        """First failing check should cause immediate short-circuit."""
        check1_called = False
        check2_called = False

        def check1(task: dict, task_result: dict) -> CheckResult:
            nonlocal check1_called
            check1_called = True
            return CheckResult("check1", True, "ok")

        def check2(task: dict, task_result: dict) -> CheckResult:
            nonlocal check2_called
            check2_called = True
            return CheckResult("check2", False, "failed", "retry")

        def check3(task: dict, task_result: dict) -> CheckResult:
            pytest.fail("check3 should not be called")

        loop = HybridReviewLoop(deterministic_checks=[check1, check2, check3])
        decision = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            task=sample_task,
            task_result=sample_failed_result,
        )
        assert decision.status == "retry"
        assert check1_called
        assert check2_called

    @pytest.mark.asyncio
    async def test_check_returns_none_skips(
        self,
        mock_agent: MagicMock,
        sample_task: dict,
        sample_passed_result: dict,
    ) -> None:
        """Check returning None is skipped (not a failure)."""
        calls: list[str] = []

        def check_skip(task: dict, task_result: dict) -> None:
            calls.append("skip")
            return None

        def check_pass(task: dict, task_result: dict) -> CheckResult:
            calls.append("pass")
            return CheckResult("pass", True, "ok")

        loop = HybridReviewLoop(deterministic_checks=[check_skip, check_pass])
        decision = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            task=sample_task,
            task_result=sample_passed_result,
        )
        assert decision.status in ("accepted", "retry", "replan", "escalate_user")
        assert calls == ["skip", "pass"]

    @pytest.mark.asyncio
    async def test_stream_mode(
        self,
        mock_agent: MagicMock,
        sample_task: dict,
        sample_passed_result: dict,
    ) -> None:
        """HybridReviewLoop supports stream=True."""
        loop = HybridReviewLoop()
        stream = loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            stream=True,
            task=sample_task,
            task_result=sample_passed_result,
            execution_log=None,
        )
        events = [event async for event in stream]
        assert len(events) > 0
