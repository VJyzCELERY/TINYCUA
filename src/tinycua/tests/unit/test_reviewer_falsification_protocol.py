"""Root-review falsification protocol tests."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult, Tool
from tinycua.loops.node_contract import LifecyclePhase, phase_tool_names
from tinycua.loops.context_rendering import render_llm_content
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.reviewer_protocol import (
    advance_lifecycle_phase,
    reset_reviewer_attempt,
    review_action_directive,
    reviewer_assurance_errors,
)
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import (
    AggregatedResult,
    ReviewerDecision,
    TaskResult,
    TaskStateStore,
)
from tinycua.tools.task_tools import TaskReviewPlanTool
from tinycua_sdk import Agent, LanguageModel


def _checks() -> list[dict[str, str]]:
    return [
        {
            "criterion_id": "acceptance-1",
            "testability": "empirical",
            "falsifying_condition": "The command exits non-zero.",
            "procedure": "Run the requested command.",
            "expected_observation": "The command exits zero.",
        },
        {
            "criterion_id": "acceptance-2",
            "testability": "judgment",
            "falsifying_condition": "The explanation omits the requested trade-off.",
            "procedure": "Compare the explanation with the requested trade-off.",
            "expected_observation": "The trade-off is addressed explicitly.",
        },
    ]


def _tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"call-{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def test_failed_reviewer_action_remains_retryable() -> None:
    """A failed observation keeps Reviewer evidence tools available for retry."""
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    node.progress.lifecycle_phase = LifecyclePhase.ACTION
    failed = LLMResult(
        tool_calls=[_tool_call("run_shell", {"command": "check"})],
        metadata={
            "tool_results": [
                {
                    "name": "run_shell",
                    "output": {
                        "stdout": "",
                        "stderr": "temporary failure",
                        "exit_code": 1,
                        "error": None,
                    },
                }
            ]
        },
    )

    assert advance_lifecycle_phase(node, failed) is False
    assert node.progress.lifecycle_phase is LifecyclePhase.ACTION

    succeeded = LLMResult(
        tool_calls=[_tool_call("run_shell", {"command": "check"})],
        metadata={
            "tool_results": [
                {"name": "run_shell", "output": {"success": True, "content": "ok"}}
            ]
        },
    )
    assert advance_lifecycle_phase(node, succeeded) is True
    assert node.progress.lifecycle_phase is LifecyclePhase.COMMIT


class _SequenceLLM:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        messages: list[dict[str, Any]],
        tools: list[Tool],
        *,
        stream: bool = False,
    ) -> dict[str, Any]:
        del stream
        self.calls.append(
            {"messages": messages, "tool_names": [tool.name for tool in tools]}
        )
        return self.responses[len(self.calls) - 1]


class _ObserveTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="run_shell")

    def __call__(self, command: str = "") -> dict[str, Any]:
        return {"success": True, "command": command, "value": "observed"}


class _TaskStateTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="task_inspect")

    def __call__(self) -> dict[str, Any]:
        return {"success": True, "tasks": []}


class _FailedObserveTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="run_shell")

    def __call__(self) -> dict[str, Any]:
        return {"success": False, "error": "observation failed"}


def test_root_review_plan_requires_exact_acceptance_coverage() -> None:
    """A root plan covers each immutable acceptance clause exactly once."""
    store = TaskStateStore()
    root = store.create_task(
        "Root",
        acceptance_clauses=["Command exits zero", "Explain the trade-off"],
    )

    store.stage_review_plan(root.task_id, _checks())

    assert store.staged_review_plan(root.task_id) == _checks()


@pytest.mark.parametrize(
    "checks,error",
    [
        (_checks()[:1], "cover every root acceptance clause"),
        ([*_checks(), _checks()[0]], "exactly once"),
        (
            [
                {
                    **_checks()[0],
                    "criterion_id": "unknown",
                },
                _checks()[1],
            ],
            "unknown acceptance clause",
        ),
    ],
)
def test_root_review_plan_rejects_invalid_criterion_coverage(
    checks: list[dict[str, str]], error: str
) -> None:
    """Missing, repeated, and unknown criteria cannot enter review action."""
    store = TaskStateStore()
    root = store.create_task(
        "Root",
        acceptance_clauses=["Command exits zero", "Explain the trade-off"],
    )

    with pytest.raises(ValueError, match=error):
        store.stage_review_plan(root.task_id, checks)

    assert store.staged_review_plan(root.task_id) == []


def test_review_plan_is_root_only_and_immutable_during_attempt() -> None:
    """Leaf review stays unchanged and a committed root plan cannot drift."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    child = store.create_task("Child", parent_id=root.task_id)
    check = [{**_checks()[0], "criterion_id": "acceptance-1"}]

    with pytest.raises(ValueError, match="root task"):
        store.stage_review_plan(child.task_id, check)

    store.stage_review_plan(root.task_id, check)
    with pytest.raises(ValueError, match="already staged"):
        store.stage_review_plan(root.task_id, check)


def test_invalid_reviewer_replacement_clears_old_staged_approval() -> None:
    """A rejected correction cannot leave an earlier approval committable."""
    store = TaskStateStore()
    task = store.create_task("Review me")
    store.record_result(task.task_id, TaskResult(content="done"))
    store.stage_reviewer_decision(
        task.task_id,
        ReviewerDecision.APPROVED,
        rationale="Initially acceptable.",
    )

    with pytest.raises(ValueError, match="future task"):
        store.stage_reviewer_decision(
            task.task_id,
            ReviewerDecision.APPROVED,
            rationale="Invalid replacement.",
            metadata={
                "context_updates": [{"task_id": "missing", "context": "invalid target"}]
            },
        )

    with pytest.raises(ValueError, match="No provisional reviewer decision"):
        store.commit_staged_reviewer_decision(task.task_id)


def test_review_plan_tool_stages_only_the_active_root() -> None:
    """The planning tool cannot plan a leaf or a non-active root."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    child = store.create_task("Child", parent_id=root.task_id)
    check = [{**_checks()[0], "criterion_id": "acceptance-1"}]
    tool = TaskReviewPlanTool()
    tool.bind_task_store(store)
    tool.bind_source_node("result_reviewer")

    store.active_task_id = child.task_id
    rejected = tool(checks=check)
    store.active_task_id = root.task_id
    staged = tool(checks=check)

    assert rejected["success"] is False
    assert "root task" in rejected["error"]
    assert staged == {
        "success": True,
        "task_id": root.task_id,
        "check_count": 1,
        "staged": True,
    }
    assert store.staged_review_plan(root.task_id) == check


def test_review_plan_tool_schema_is_bounded() -> None:
    """The model-facing plan schema accepts only the five plan fields."""
    parameters = TaskReviewPlanTool().parameters
    item = parameters["properties"]["checks"]["items"]

    assert parameters["required"] == ["checks"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == {
        "criterion_id",
        "testability",
        "falsifying_condition",
        "procedure",
        "expected_observation",
    }


def test_review_plan_phase_exposes_only_plan_tool() -> None:
    """Root planning cannot inspect the outcome or commit a verdict early."""
    tools = {
        "task_review_plan",
        "task_review_decision",
        "task_inspect",
        "run_shell",
        "terminate",
    }

    assert phase_tool_names("result_reviewer", tools, LifecyclePhase.PLAN) == {
        "task_review_plan"
    }
    assert phase_tool_names("result_reviewer", tools, LifecyclePhase.ACTION) == {
        "task_inspect",
        "run_shell",
    }
    assert phase_tool_names("result_reviewer", tools, LifecyclePhase.COMMIT) == {
        "task_review_decision"
    }


def test_root_reviewer_starts_blind_plan_before_executor_claims() -> None:
    """Root planning sees criteria but not the Executor's success narrative."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="SECRET EXECUTOR CLAIM"))
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )

    node.ensure_session(loop.root_session)
    continuation = node.build_continuation(loop.root_session)

    assert node.progress.lifecycle_phase is LifecyclePhase.PLAN
    assert "acceptance-1" in continuation
    assert "Outcome works" in continuation
    assert "SECRET EXECUTOR CLAIM" not in continuation


def test_root_reviewer_receives_finding_ledger_only_after_plan() -> None:
    """Blind planning hides findings that become visible for ACTION cross-checking."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="failed", success=False))
    store.record_reviewer_decision(
        root.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="The prior attempt failed.",
        metadata={"new_findings": ["ROOT_OPEN_FINDING"]},
    )
    store.record_result(root.task_id, TaskResult(content="retry", success=True))
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    node.ensure_session(loop.root_session)

    plan_context = node.build_continuation(loop.root_session)
    node.progress.lifecycle_phase = LifecyclePhase.ACTION
    action_context = review_action_directive(node)

    assert "ROOT_OPEN_FINDING" not in plan_context
    assert "ROOT_OPEN_FINDING" in action_context


def test_leaf_reviewer_keeps_existing_action_context() -> None:
    """The initial rollout leaves task-local review behavior unchanged."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    child = store.create_task("Child", parent_id=root.task_id)
    store.record_result(child.task_id, TaskResult(content="VISIBLE CHILD CLAIM"))
    store.active_task_id = child.task_id
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )

    node.ensure_session(loop.root_session)
    continuation = node.build_continuation(loop.root_session)

    assert node.progress.lifecycle_phase is LifecyclePhase.ACTION
    assert "VISIBLE CHILD CLAIM" in continuation


@pytest.mark.asyncio
async def test_root_reviewer_plan_unlocks_action_and_decision() -> None:
    """A successful plan is followed by normal review tools and one verdict."""
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[node]))
    store = loop.root_session.task_store
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="Executor says it works."))
    check = [{**_checks()[0], "criterion_id": "acceptance-1"}]
    review_summary = "Comprehensive evidence-backed review. " * 40
    llm = _SequenceLLM(
        [
            {
                "content": "",
                "tool_calls": [_tool_call("task_review_plan", {"checks": check})],
            },
            {
                "content": "Observed the final behavior.",
                "tool_calls": [_tool_call("run_shell", {"command": "check outcome"})],
            },
            {
                "content": "approved",
                "tool_calls": [
                    _tool_call(
                        "task_review_decision",
                        {
                            "decision": "approved",
                            "rationale": "Observed outcome.",
                            "review_summary": review_summary,
                            "criterion_assessments": [
                                {
                                    "criterion_id": "acceptance-1",
                                    "result": "supported",
                                    "evidence_ids": ["call-run_shell"],
                                    "inference": "The check observed the outcome.",
                                    "limitations": "One check was executed.",
                                }
                            ],
                        },
                    )
                ],
            },
        ]
    )
    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = llm  # type: ignore[method-assign]

    await loop._execute_node(node, agent, [_ObserveTool()])

    assert llm.calls[0]["tool_names"] == ["task_review_plan"]
    assert "Executor says it works." not in json.dumps(llm.calls[0]["messages"])
    assert "task_review_plan" not in llm.calls[1]["tool_names"]
    assert "Executor says it works." in json.dumps(llm.calls[1]["messages"])
    assert set(llm.calls[1]["tool_names"]) == {
        "task_inspect",
        "run_shell",
    }
    assert set(llm.calls[2]["tool_names"]) == {
        "task_review_decision",
        "json_draft_create",
        "json_draft_read",
        "json_draft_replace",
        "json_draft_commit",
    }
    assert root.reviewer_decisions[-1]["decision"] == "approved"
    assert root.reviewer_decisions[-1]["review_summary"] == review_summary.strip()


@pytest.mark.asyncio
async def test_reviewer_observation_has_runtime_provenance_without_provider_id() -> (
    None
):
    """Actual ACTION outcomes receive stable provenance even without a call ID."""
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="done"))
    node.ensure_session(loop.root_session)
    node.progress.lifecycle_phase = LifecyclePhase.ACTION
    node.progress.attempt_count = 2

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [
            {
                "id": "",
                "type": "function",
                "function": {
                    "name": "run_shell",
                    "arguments": '{"command":"observe"}',
                },
            }
        ],
        [_ObserveTool()],
        node,
    )

    outcome = results[0]["outcome"]
    assert outcome["evidence_id"]
    assert outcome["call_id"] == outcome["evidence_id"]
    assert outcome["node_id"] == "result_reviewer"
    assert outcome["task_id"] == root.task_id
    assert outcome["review_attempt"] == 2
    assert outcome["lifecycle_phase"] == "action"
    assert isinstance(outcome["task_version"], int)


@pytest.mark.asyncio
async def test_root_reviewer_retries_unknown_observation_reference() -> None:
    """A verdict cannot launder an invented evidence ID into empirical support."""
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[node]))
    store = loop.root_session.task_store
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="done"))
    check = [{**_checks()[0], "criterion_id": "acceptance-1"}]

    def decision(evidence_id: str) -> dict[str, Any]:
        return {
            "decision": "approved",
            "rationale": "Observed outcome.",
            "criterion_assessments": [
                {
                    "criterion_id": "acceptance-1",
                    "result": "supported",
                    "evidence_ids": [evidence_id],
                    "inference": "The check observed the outcome.",
                    "limitations": "One check was executed.",
                }
            ],
        }

    llm = _SequenceLLM(
        [
            {
                "content": "",
                "tool_calls": [_tool_call("task_review_plan", {"checks": check})],
            },
            {
                "content": "",
                "tool_calls": [_tool_call("run_shell", {"command": "check"})],
            },
            {
                "content": "approved",
                "tool_calls": [
                    _tool_call("task_review_decision", decision("invented"))
                ],
            },
            {
                "content": "approved",
                "tool_calls": [
                    _tool_call("task_review_decision", decision("call-run_shell"))
                ],
            },
        ]
    )
    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = llm  # type: ignore[method-assign]

    await loop._execute_node(node, agent, [_ObserveTool()])

    assert len(llm.calls) == 4
    assert set(llm.calls[-1]["tool_names"]) == {
        "task_review_decision",
        "json_draft_create",
        "json_draft_read",
        "json_draft_replace",
        "json_draft_commit",
    }
    assert root.reviewer_decisions[-1]["metadata"]["assurance_status"] == "observed"


def test_root_approval_requires_assessment_for_every_criterion() -> None:
    """A complete plan cannot be approved through rationale alone."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="done"))
    store.stage_review_plan(
        root.task_id, [{**_checks()[0], "criterion_id": "acceptance-1"}]
    )

    with pytest.raises(ValueError, match="criterion assessment"):
        store.stage_reviewer_decision(
            root.task_id,
            ReviewerDecision.APPROVED,
            rationale="Looks good.",
        )


def test_empirical_approval_requires_observation_reference() -> None:
    """Empirical support cannot be committed as an uncited assertion."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="done"))
    store.stage_review_plan(
        root.task_id, [{**_checks()[0], "criterion_id": "acceptance-1"}]
    )

    with pytest.raises(ValueError, match="(?i)empirical support requires evidence"):
        store.stage_reviewer_decision(
            root.task_id,
            ReviewerDecision.APPROVED,
            rationale="Looks good.",
            metadata={
                "criterion_assessments": [
                    {
                        "criterion_id": "acceptance-1",
                        "result": "supported",
                        "evidence_ids": [],
                        "inference": "The outcome works.",
                        "limitations": "One observation.",
                    }
                ]
            },
        )


def test_judgment_only_root_can_complete_without_fake_evidence() -> None:
    """Subjective work exits honestly without inventing a tool observation."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["Explanation is clear"])
    store.record_result(root.task_id, TaskResult(content="done"))
    check = [{**_checks()[1], "criterion_id": "acceptance-1"}]
    assessments = [
        {
            "criterion_id": "acceptance-1",
            "result": "judgment_only",
            "evidence_ids": [],
            "inference": "The requested trade-off is stated directly.",
            "limitations": "Clarity remains subjective.",
        }
    ]
    store.stage_review_plan(root.task_id, check)
    store.stage_reviewer_decision(
        root.task_id,
        ReviewerDecision.APPROVED,
        rationale="The explanation addresses the request.",
        metadata={"criterion_assessments": assessments},
    )

    store.commit_staged_reviewer_decision(root.task_id)

    assert root.status.value == "completed"
    assert root.metadata["assurance_status"] == "judgment_only"
    event = root.reviewer_decisions[-1]
    assert event["metadata"]["review_plan"] == check
    assert event["metadata"]["criterion_assessments"] == assessments


def test_contradicted_empirical_criterion_blocks_approval() -> None:
    """Approval is invalid when the planned falsifier contradicts the outcome."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="done"))
    store.stage_review_plan(
        root.task_id, [{**_checks()[0], "criterion_id": "acceptance-1"}]
    )

    with pytest.raises(ValueError, match="cannot approve"):
        store.stage_reviewer_decision(
            root.task_id,
            ReviewerDecision.APPROVED,
            rationale="The observation contradicted the claim.",
            metadata={
                "criterion_assessments": [
                    {
                        "criterion_id": "acceptance-1",
                        "result": "contradicted",
                        "evidence_ids": ["ev-1"],
                        "inference": "The observed outcome failed.",
                        "limitations": "None.",
                    }
                ]
            },
        )


def test_stale_observation_from_previous_attempt_is_rejected() -> None:
    """A retry cannot approve with an observation from an earlier attempt."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="done"))
    store.stage_review_plan(
        root.task_id, [{**_checks()[0], "criterion_id": "acceptance-1"}]
    )
    observation_version = store.version
    store.stage_reviewer_decision(
        root.task_id,
        ReviewerDecision.APPROVED,
        rationale="Observed outcome.",
        metadata={
            "criterion_assessments": [
                {
                    "criterion_id": "acceptance-1",
                    "result": "supported",
                    "evidence_ids": ["old-observation"],
                    "inference": "The outcome works.",
                    "limitations": "One observation.",
                }
            ]
        },
    )
    node = SimpleNamespace(
        progress=SimpleNamespace(
            attempt_count=2,
            correlated_outcomes=[
                {
                    "success": True,
                    "node_id": "result_reviewer",
                    "task_id": root.task_id,
                    "lifecycle_phase": "action",
                    "evidence_id": "old-observation",
                    "tool_name": "run_shell",
                    "review_attempt": 1,
                    "task_version": observation_version,
                }
            ],
        )
    )

    assert reviewer_assurance_errors(node, store)


def test_invalid_non_supported_observation_reference_is_rejected() -> None:
    """Contradicted and inconclusive assessments cannot cite invented evidence."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="failed"))
    store.stage_review_plan(
        root.task_id, [{**_checks()[0], "criterion_id": "acceptance-1"}]
    )
    store.stage_reviewer_decision(
        root.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="The check failed.",
        metadata={
            "new_findings": ["The acceptance check failed."],
            "criterion_assessments": [
                {
                    "criterion_id": "acceptance-1",
                    "result": "contradicted",
                    "evidence_ids": ["invented"],
                    "inference": "The outcome failed.",
                    "limitations": "One observation.",
                }
            ],
        },
    )
    node = SimpleNamespace(
        progress=SimpleNamespace(attempt_count=1, correlated_outcomes=[])
    )

    assert reviewer_assurance_errors(node, store)


def test_aggregated_result_renders_assurance_for_final_response() -> None:
    """Final response context keeps assurance separate from completion."""
    rendered = render_llm_content(
        AggregatedResult(
            root_task_id="root",
            metadata={"assurance_status": "judgment_only"},
        )
    )

    assert "Assurance:" in rendered
    assert "judgment_only" in rendered


def test_reviewer_retry_resets_plan_and_observations() -> None:
    """A new root Reviewer attempt starts blind with no prior evidence."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    node.ensure_session(loop.root_session)
    store.stage_review_plan(
        root.task_id, [{**_checks()[0], "criterion_id": "acceptance-1"}]
    )
    node.progress.lifecycle_phase = LifecyclePhase.ACTION
    node.progress.mark_tool_called("task_review_plan")
    node.progress.correlated_outcomes.append({"evidence_id": "stale"})

    assert reset_reviewer_attempt(node) is True
    assert store.staged_review_plan(root.task_id) == []
    assert node.progress.lifecycle_phase is LifecyclePhase.PLAN
    assert node.progress.visited_tools == set()
    assert node.progress.satisfied_requirements == set()
    assert node.progress.correlated_outcomes == []


def test_reviewer_recovery_reentry_resets_plan_and_observations() -> None:
    """Recovery re-entry starts a fresh blind root review attempt."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    node.ensure_session(loop.root_session)
    store.stage_review_plan(
        root.task_id, [{**_checks()[0], "criterion_id": "acceptance-1"}]
    )
    node.progress.lifecycle_phase = LifecyclePhase.ACTION
    node.progress.correlated_outcomes.append({"evidence_id": "stale"})
    loop._recovery_reentry = True

    loop._reset_progress_for_retry(node)

    assert store.staged_review_plan(root.task_id) == []
    assert node.progress.lifecycle_phase is LifecyclePhase.PLAN
    assert node.progress.correlated_outcomes == []


@pytest.mark.asyncio
async def test_duplicate_provider_call_ids_get_distinct_observation_ids() -> None:
    """Provider call-ID collisions cannot alias two Reviewer observations."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    node.ensure_session(loop.root_session)
    node.progress.lifecycle_phase = LifecyclePhase.ACTION
    calls = [
        {
            "id": "duplicate",
            "type": "function",
            "function": {"name": "run_shell", "arguments": '{"command":"check"}'},
        },
        {
            "id": "duplicate",
            "type": "function",
            "function": {"name": "run_shell", "arguments": '{"command":"check"}'},
        },
    ]

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()), calls, [_ObserveTool()], node
    )

    assert root.task_id
    evidence_ids = [item["outcome"]["evidence_id"] for item in results]
    assert len(set(evidence_ids)) == 2
    assert [json.loads(item["prompt_content"])["evidence_id"] for item in results] == (
        evidence_ids
    )


@pytest.mark.asyncio
async def test_task_state_tools_do_not_advertise_evidence_ids() -> None:
    """Uncitable task-state operations expose call provenance but not evidence IDs."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    store.create_task("Root", acceptance_clauses=["Outcome works"])
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    node.ensure_session(loop.root_session)
    node.progress.lifecycle_phase = LifecyclePhase.ACTION

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [_tool_call("task_inspect", {})],
        [_TaskStateTool()],
        node,
    )

    result = results[0]
    assert result["call_id"]
    assert "evidence_id" not in result
    assert "evidence_id" not in result["outcome"]
    assert "evidence_id" not in json.loads(result["prompt_content"])


@pytest.mark.asyncio
async def test_failed_action_observation_has_call_id_only() -> None:
    """Failed Reviewer observations cannot advertise uncitable evidence IDs."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    store.create_task("Root", acceptance_clauses=["Outcome works"])
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    node.ensure_session(loop.root_session)
    node.progress.lifecycle_phase = LifecyclePhase.ACTION

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [_tool_call("run_shell", {"command": "check"})],
        [_FailedObserveTool()],
        node,
    )

    result = results[0]
    assert result["call_id"]
    assert "evidence_id" not in result
    assert "evidence_id" not in result["outcome"]
    assert "evidence_id" not in json.loads(result["prompt_content"])


@pytest.mark.asyncio
async def test_recovery_reentry_rebuilds_blind_plan_context() -> None:
    """Recovery resets review state before constructing the first new prompt."""
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[node]))
    store = loop.root_session.task_store
    root = store.create_task("Root", acceptance_clauses=["Outcome works"])
    store.record_result(root.task_id, TaskResult(content="SECRET EXECUTOR CLAIM"))
    check = [{**_checks()[0], "criterion_id": "acceptance-1"}]
    store.stage_review_plan(root.task_id, check)
    node.ensure_session(loop.root_session)
    node.progress.lifecycle_phase = LifecyclePhase.ACTION
    loop._recovery_reentry = True
    llm = _SequenceLLM(
        [
            {
                "content": "",
                "tool_calls": [_tool_call("task_review_plan", {"checks": check})],
            },
            {
                "content": "",
                "tool_calls": [_tool_call("run_shell", {"command": "check"})],
            },
            {
                "content": "approved",
                "tool_calls": [
                    _tool_call(
                        "task_review_decision",
                        {
                            "decision": "approved",
                            "rationale": "Observed outcome.",
                            "criterion_assessments": [
                                {
                                    "criterion_id": "acceptance-1",
                                    "result": "supported",
                                    "evidence_ids": ["call-run_shell"],
                                    "inference": "The outcome works.",
                                    "limitations": "One observation.",
                                }
                            ],
                        },
                    )
                ],
            },
        ]
    )
    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = llm  # type: ignore[method-assign]

    await loop._execute_node(node, agent, [_ObserveTool()])

    assert "SECRET EXECUTOR CLAIM" not in json.dumps(llm.calls[0]["messages"])
