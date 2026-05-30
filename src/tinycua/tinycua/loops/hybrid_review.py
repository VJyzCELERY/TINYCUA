"""HybridReviewLoop — hybrid deterministic + LLM review loop."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from tinycua_sdk.agent.loop import BaseLoop

from tinycua.state import ReviewerDecision, ReviewStatus

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

__all__ = ["CheckResult", "HybridReviewLoop", "HybridReviewConfig"]


@dataclass
class CheckResult:
    """Result of a single deterministic check in :class:`HybridReviewLoop`.

    Attributes:
        check_name: Name of the check that produced this result.
        passed: Whether the check passed.
        reason: Human-readable reason for the result.
        decision_override: If set and ``passed`` is False, the loop
            short-circuits to this decision without calling the LLM.
            One of ``ReviewStatus`` values (``accepted``, ``retry``,
            ``replan``, ``escalate_user``).
    """

    check_name: str
    passed: bool
    reason: str
    decision_override: ReviewStatus | None = None


@dataclass
class HybridReviewConfig:
    """Configuration for :class:`HybridReviewLoop`.

    Attributes:
        deterministic_checks: List of callable check functions.
        consecutive_failure_threshold: Max consecutive failures before
            escalating.
        llm_review_required: Whether LLM semantic review is required when
            all checks pass.
    """

    deterministic_checks: list[Callable] = field(default_factory=list)
    consecutive_failure_threshold: int = 3
    llm_review_required: bool = True


_REVIEW_SYSTEM_PROMPT = """\
You are a result reviewer. Your task is to review a task execution result \
and determine whether it should be accepted, retried, replanned, or \
escalated to a human.

Review the task, its result, and any execution log. Consider:
- Does the output satisfy the task requirements?
- Are there any quality or correctness issues?
- Would a retry likely produce a better result?
- Does the task need to be re-planned (reassigned differently)?
- Should a human be involved?

Respond with a JSON object containing:
- "status": one of "accepted", "retry", "replan", "escalate_user"
- "reason": detailed explanation for the decision
- "confidence": float between 0.0 and 1.0
- "task_id": the ID of the reviewed task
"""

CheckFunction = Callable[[dict, dict], CheckResult | None]
"""Type alias for a deterministic check function.

Receives ``(task: dict, task_result: dict)`` and returns either a
``CheckResult`` or ``None`` (to skip the check).
"""


class HybridReviewLoop(BaseLoop):
    """Hybrid deterministic + LLM review loop for the Result Reviewer.

    Executes injected deterministic check callables first; short-circuits
    on failure with a ``ReviewerDecision``. If all checks pass, performs
    LLM semantic review to produce the final decision.

    Args:
        max_iterations: Maximum iterations (default 3).
        deterministic_checks: List of callable check functions, each
            receiving ``(task: dict, task_result: dict)`` and returning
            ``CheckResult | None``.
        consecutive_failure_threshold: Max consecutive failures before
            escalating (reserved for future use).
    """

    def __init__(
        self,
        max_iterations: int = 3,
        deterministic_checks: list[CheckFunction] | None = None,
        consecutive_failure_threshold: int = 3,
    ) -> None:
        super().__init__(max_iterations=max_iterations)
        self.deterministic_checks: list[CheckFunction] = deterministic_checks or []
        self.consecutive_failure_threshold = consecutive_failure_threshold

    def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        stream: bool = False,
        *,
        task: dict,
        task_result: dict,
        execution_log: dict | None = None,
    ) -> ReviewerDecision | AsyncIterator[dict[str, Any]]:
        """Run the hybrid review loop.

        When ``stream=False`` (default), returns a coroutine that resolves
        to ``ReviewerDecision`` — call with ``await``.

        When ``stream=True``, returns an async iterator of SSE event dicts
        — use ``async for`` to consume.

        Args:
            agent: The agent executing the loop.
            messages: Existing conversation messages.
            tools: Available tools (typically empty for review).
            stream: When True, yields SSE events.
            task: The task dict with at least ``task_id``.
            task_result: The task result dict with ``task_id`` and
                ``status``.
            execution_log: Optional execution log dict.

        Returns:
            A coroutine resolving to ``ReviewerDecision`` when
            ``stream=False``, or an async iterator of stream events.
        """
        # Step 1: Run deterministic checks (always synchronous)
        check_decision = self._run_deterministic_checks(task, task_result)
        if check_decision is not None:
            return self._wrap_immediate(check_decision)

        # Step 2: LLM semantic review
        if stream:
            return self._run_stream_review(agent, tools, task, task_result, execution_log)

        return self._llm_review(agent, task, task_result, execution_log)

    def _run_deterministic_checks(
        self,
        task: dict,
        task_result: dict,
    ) -> ReviewerDecision | None:
        """Execute all deterministic checks in order.

        Returns:
            A ``ReviewerDecision`` if a check fails with an override,
            or ``None`` if all checks pass (or return ``None``).
        """
        for check_fn in self.deterministic_checks:
            result = check_fn(task, task_result)
            if result is None:
                continue
            if not result.passed and result.decision_override is not None:
                return ReviewerDecision(
                    task_id=task.get("task_id", "unknown"),
                    status=result.decision_override,
                    reason=result.reason,
                    confidence=1.0,  # Deterministic — full confidence
                )
            if not result.passed:
                return ReviewerDecision(
                    task_id=task.get("task_id", "unknown"),
                    status=ReviewStatus.RETRY,
                    reason=result.reason,
                    confidence=1.0,
                )
        return None

    async def _llm_review(
        self,
        agent: Agent,
        task: dict,
        task_result: dict,
        execution_log: dict | None = None,
    ) -> ReviewerDecision:
        """Perform LLM-based semantic review."""
        log_text = ""
        if execution_log:
            log_text = f"\nExecution Log:\n{json.dumps(execution_log, indent=2)}\n"

        working: list[dict] = [
            {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Task:\n{json.dumps(task, indent=2)}\n\n"
                    f"Task Result:\n{json.dumps(task_result, indent=2)}\n"
                    f"{log_text}"
                    f"\nProvide your review as a JSON object."
                ),
            },
        ]

        llm_response: dict = await agent._call_llm(working, [])  # type: ignore[arg-type]
        return self._parse_review_response(llm_response, task.get("task_id", "unknown"))

    def _parse_review_response(
        self,
        response: dict,
        default_task_id: str,
    ) -> ReviewerDecision:
        """Parse the LLM response into ``ReviewerDecision``."""
        content = response.get("content", "{}")
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {}

        status_str = data.get("status", "retry")
        valid_statuses = {"accepted", "retry", "replan", "escalate_user"}
        if status_str not in valid_statuses:
            status_str = "retry"

        return ReviewerDecision(
            task_id=data.get("task_id", default_task_id),
            status=status_str,  # type: ignore[arg-type]
            reason=data.get("reason", "Review completed — no specific reason provided."),
            confidence=float(data.get("confidence", 0.5)),
        )

    @staticmethod
    async def _wrap_immediate(decision: ReviewerDecision) -> ReviewerDecision:
        """Wrap an immediate decision in a coroutine for API consistency."""
        return decision

    async def _run_stream_review(
        self,
        agent: Agent,
        tools: list[Tool],
        task: dict,
        task_result: dict,
        execution_log: dict | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream review events."""
        yield {"type": "response.created"}

        log_text = ""
        if execution_log:
            log_text = f"\nExecution Log:\n{json.dumps(execution_log, indent=2)}\n"

        working: list[dict] = [
            {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Task:\n{json.dumps(task, indent=2)}\n\n"
                    f"Task Result:\n{json.dumps(task_result, indent=2)}\n"
                    f"{log_text}"
                    f"\nProvide your review as a JSON object."
                ),
            },
        ]

        try:
            llm_stream = await agent._call_llm(working, tools, stream=True)  # type: ignore[arg-type]
            async for event in llm_stream:
                yield event
        except Exception as e:
            yield {"type": "response.failed", "error": {"message": str(e)}}
            yield {"type": "error", "error": {"message": str(e)}}
            return

        yield {"type": "response.completed", "finish_reason": "completed"}
