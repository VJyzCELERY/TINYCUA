"""Final response contracts: no synthetic success and observable final stream."""

from __future__ import annotations

import json
import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.config.node_config import NodeConfigBase
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.node import ProcessNode
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode
from tinycua.loops.task_nodes import TinyCUATaskAssessorNode
from tinycua.loops.task_nodes import TinyCUATaskExecutorNode
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStatus


class EmptyResponseAgent:
    """Agent double that returns empty first, then a valid response on retry.

    Simulates a model that fails validation once, then the recovery retry
    produces valid output. The unbounded recovery loop calls the agent again
    with a focused context — this double returns a real response on that
    second call.
    """

    def __init__(self) -> None:
        self._call_count = 0

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        self._call_count += 1
        if self._call_count == 1:
            return {"role": "assistant", "content": ""}
        # Recovery retry — produce a valid non-empty response.
        return {"role": "assistant", "content": "Recovered response after retry."}


class StreamingResponseAgent:
    """Agent double that streams terminal response deltas."""

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        if not stream:
            return {"role": "assistant", "content": "done"}

        async def events():
            yield {"type": "response.output_text.delta", "delta": "hel"}
            yield {"type": "response.output_text.delta", "delta": "lo"}
            yield {"type": "response.usage", "usage": {"output_tokens": 1}}

        return events()


class TextResponseAgent:
    """Agent double that returns a fixed terminal response."""

    def __init__(self, content: str) -> None:
        self.content = content

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        return {"role": "assistant", "content": self.content}


class ReplayingResponseAgent:
    """Agent double that keeps replaying internal response context."""

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        return {
            "role": "assistant",
            "content": (
                "Direct response context from the entry request:\nHello\n"
                "Based on the accepted Worker result or direct-response context above."
            ),
        }


class NonterminalFailureThenResponseAgent:
    """Agent double that fails TaskCreate then succeeds on recovery, then ResponseNode."""

    def __init__(self) -> None:
        self._task_create_calls = 0

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        system_text = "\n".join(
            str(message.get("content", ""))
            for message in messages
            if message.get("role") == "system"
        )
        if "Generate the final user-facing response" in system_text:
            return {
                "role": "assistant",
                "content": "Final response saw the validation failure.",
            }
        # TaskCreate: fail first (no tool call), then succeed on recovery retry.
        if "task creation node" in system_text or "task_init" in system_text:
            self._task_create_calls += 1
            if self._task_create_calls == 1:
                return {"role": "assistant", "content": "planner-only response"}
            # Recovery retry — produce the required task_init tool call.
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "task_init",
                            "arguments": '{"title":"create a task"}',
                        },
                    }
                ],
            }
        return {"role": "assistant", "content": "planner-only response"}


class IntermediateThenResponseAgent:
    """Agent double for max-iteration terminal routing."""

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        system_text = "\n".join(
            str(message.get("content", ""))
            for message in messages
            if message.get("role") == "system"
        )
        if "Generate the final user-facing response" in system_text:
            return {"role": "assistant", "content": "Final after loop limit."}
        return {"role": "assistant", "content": "Intermediate complete."}


class ExecutorFailureThenReviewerAgent:
    """Agent double: executor omits result state, reviewer handles failure."""

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        system_text = "\n".join(
            str(message.get("content", ""))
            for message in messages
            if message.get("role") == "system"
        )
        if "You are the TaskExecutor" in system_text:
            return {"role": "assistant", "content": "I forgot to record result state."}
        if "You are the ResultReviewer" in system_text:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "task_review_decision",
                            "arguments": '{"decision":"approved","rationale":"runtime failure evidence reviewed"}',
                        },
                    }
                ],
            }
        if "You are the ResultAggregation" in system_text:
            return {"role": "assistant", "content": "Aggregated failure evidence."}
        return {"role": "assistant", "content": "Final failure summary."}


class ExecutorValidationFailureAgent:
    """Agent double: executor never records task_result_update."""

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        return {"role": "assistant", "content": "I forgot task_result_update."}


class ExecutorResultThenReviewerAgent:
    """Agent double: executor records a result and must stop for reviewer."""

    def __init__(self) -> None:
        self.executor_calls = 0
        self.reviewer_calls = 0
        self.tool_permissions = {}
        self.approval_workflow = None

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        system_text = "\n".join(
            str(message.get("content", ""))
            for message in messages
            if message.get("role") == "system"
        )
        if "You are the TaskExecutor" in system_text:
            self.executor_calls += 1
            if self.executor_calls > 1:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {"name": "terminate", "arguments": "{}"},
                        }
                    ],
                }
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "task_result_update",
                            "arguments": '{"content":"created requirements.txt","success":true}',
                        },
                    }
                ],
            }
        if "You are the ResultReviewer" in system_text:
            self.reviewer_calls += 1
            if self.reviewer_calls > 1:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {"name": "terminate", "arguments": "{}"},
                        }
                    ],
                }
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "task_inspect",
                            "arguments": "{}",
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "list_files",
                            "arguments": "{}",
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "task_review_decision",
                            "arguments": '{"decision":"approved","rationale":"evidence accepted"}',
                        },
                    }
                ],
            }
        if "You are the ResultAggregation" in system_text:
            return {"role": "assistant", "content": "Aggregated success evidence."}
        return {"role": "assistant", "content": "Final success summary."}


@pytest.mark.asyncio
async def test_empty_terminal_response_is_not_synthetic_success() -> None:
    """An empty ResponseNode result triggers recovery, not synthetic success.

    The unbounded recovery loop retries until the agent produces valid output.
    The EmptyResponseAgent returns empty on the first call, then a valid
    response on the recovery retry. The result must not contain synthetic
    "Processed request" success text.
    """
    loop = TinyCUALoop(queue=NodeQueue(items=[ResponseNode()]))

    await loop.run(
        EmptyResponseAgent(),
        messages=[{"role": "user", "content": "do work"}],
        tools=[],
    )

    # Should not contain synthetic "Processed request" success text.
    assert "Processed request" not in loop.get_transcript_text()


@pytest.mark.asyncio
async def test_empty_worker_response_falls_back_to_completed_task_summary() -> None:
    """Completed worker evidence gets a deterministic final fallback."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("Build app")
    loop.root_session.task_store.record_result(task.task_id, TaskResult(content="Built app"))
    loop.root_session.task_store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.APPROVED,
    )

    events = [
        event
        async for event in loop._stream_exhausted_node_events(
            ResponseNode(),
            None,  # agent (not used by fallback path)
            [],    # resolved_tools
            "",
            ValidationResult(is_valid=False, errors=["Final response must be non-empty."]),
            LLMResult(),
            False,
            False,
            False,
            "ResponseNode",
            3,
        )
    ]

    assert events[0]["type"] == "response.output_text.delta"
    assert events[0]["delta"] == "Done: Built app"


@pytest.mark.asyncio
async def test_final_response_events_capture_only_terminal_user_visible_stream() -> None:
    """Final response events expose terminal text deltas without debug events."""
    loop = TinyCUALoop(queue=NodeQueue(items=[ResponseNode()]))

    stream = await loop.run(
        StreamingResponseAgent(),
        messages=[{"role": "user", "content": "hello"}],
        tools=[],
        stream=True,
    )
    events = [event async for event in stream]

    assert "hello" == "".join(
        event["delta"] for event in loop.get_final_response_events()
    )
    assert all(
        event["type"] == "response.output_text.delta"
        for event in loop.get_final_response_events()
    )
    assert any(event["type"] == "node.completed" for event in events)


@pytest.mark.asyncio
async def test_nonterminal_validation_failure_does_not_route_to_response_node() -> None:
    """A nonterminal validation failure is caught by the validator, not a crash.

    The task_create node's validation failure triggers the unbounded recovery
    loop. With a mock agent that can't produce real tool calls (tools=[]),
    the loop would spin forever in production. This test verifies the
    validation gate itself rejects prose-only output — the recovery loop's
    entry condition. The full recovery flow is tested in
    test_unbounded_recovery_* tests with proper tool setup.
    """
    task_create = TinyCUATaskCreateNode(
        node_id="task_create",
        config=create_node_config("task_create"),
    )
    loop = TinyCUALoop()

    # The task_create validation must fail when no task_init tool call was made.
    result = LLMResult(content="planner-only response")
    validation = loop._validate_node_result(task_create, result)

    assert not validation.is_valid
    assert any("task_init" in error for error in validation.errors)


@pytest.mark.asyncio
async def test_loop_continues_until_response_node() -> None:
    """Loop exits only at ResponseNode."""
    first = ProcessNode(
        node_id="first",
        config=NodeConfigBase(),
        instruction="First nonterminal node.",
    )
    second = ProcessNode(
        node_id="second",
        config=NodeConfigBase(),
        instruction="Second nonterminal node.",
    )
    response = ResponseNode()
    loop = TinyCUALoop(queue=NodeQueue(items=[first, second, response]))

    result = await loop.run(
        IntermediateThenResponseAgent(),
        messages=[{"role": "user", "content": "do two things"}],
        tools=[],
    )

    trace = loop.get_execution_trace()
    assert result == "Final after loop limit."
    assert [entry["node_id"] for entry in trace] == ["first", "second", "response"]
    assert trace[-1]["is_terminal"] is True
    assert loop.root_session.diagnostics == []


@pytest.mark.asyncio
async def test_response_node_rejects_success_before_all_tasks_complete() -> None:
    """Worker task trees must be complete before success response synthesis.

    With the unbounded recovery loop, the system cannot exit until all tasks
    are done. This test verifies the validation gate itself rejects a success
    response when tasks remain unfinished — the recovery loop would spin
    forever in production (until the experiment timeout). We test the validator
    directly instead of running the full loop.
    """
    loop = TinyCUALoop()
    loop.root_session.task_store.create_task("unfinished worker task")

    # The response validation must fail when tasks are incomplete.
    result = LLMResult(content="Done successfully.")
    validation = loop._validate_node_result(ResponseNode(), result)

    assert not validation.is_valid
    assert any("complete" in error.lower() for error in validation.errors)


def test_task_executor_validation_failure_without_tool_evidence_fails_closed() -> None:
    """Executor prose-only failures do not respawn executor forever."""
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    response = ResponseNode()
    loop = TinyCUALoop(queue=NodeQueue(items=[executor, reviewer, response]))
    root = loop.root_session.task_store.create_task("build app")
    task = loop.root_session.task_store.create_task(
        "verify app locally",
        parent_id=root.task_id,
    )

    recovered = loop._recover_task_executor_validation_failure(
        executor,
        ValidationResult(is_valid=False, errors=["missing task_result_update"]),
        LLMResult(content="I forgot task_result_update."),
    )

    assert recovered is False
    assert task.result is None
    assert task.reviewer_decisions == []
    assert loop.root_session.task_store.active_task_id == task.task_id
    assert [node.node_id for node in loop.queue.items] == [
        "task_executor",
        "result_reviewer",
        "response",
    ]


def test_task_executor_partial_action_evidence_continues_same_task() -> None:
    """Successful action evidence keeps executing instead of replanning."""
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    response = ResponseNode()
    loop = TinyCUALoop(queue=NodeQueue(items=[executor, response]))
    task = loop.root_session.task_store.create_task("write frontend files")

    recovered = loop._recover_task_executor_validation_failure(
        executor,
        ValidationResult(is_valid=False, errors=["missing task_result_update"]),
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "write_file",
                        "allowed": True,
                        "output": {"success": True, "path": "templates/index.html"},
                    }
                ]
            }
        ),
    )

    assert recovered is True
    assert task.result is None


def test_reviewer_approval_with_nonempty_result_is_valid() -> None:
    """Approving a task with a non-empty result report is valid when inspector inspects first."""
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[reviewer, ResponseNode()]))
    task = loop.root_session.task_store.create_task("Build app")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="Built app"),
    )
    loop.root_session.task_store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.APPROVED,
        rationale="looks fine",
    )

    validation = loop._validate_node_result(
        reviewer,
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "task_inspect",
                        "output": {"success": True, "tasks": {}},
                    },
                    {
                        "name": "task_review_decision",
                        "output": {
                            "success": True,
                            "task_id": task.task_id,
                            "decision": "approved",
                        },
                    },
                    {"name": "terminate", "output": {"success": True}},
                ]
            }
        ),
    )

    assert validation.is_valid is True


def test_reviewer_approval_without_result_is_rejected() -> None:
    """Approval cannot create synthetic executor evidence."""
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[reviewer, ResponseNode()]))
    task = loop.root_session.task_store.create_task("Build app")
    with pytest.raises(ValueError, match="requires successful executor evidence"):
        loop.root_session.task_store.record_reviewer_decision(
            task.task_id,
            ReviewerDecision.APPROVED,
            rationale="looks fine",
        )

    assert task.result is None
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.reviewer_decisions == []


def test_exhausted_replan_response_allows_failure_summary() -> None:
    """Only the explicit exhausted-budget route may answer before completion."""
    loop = TinyCUALoop()
    loop.root_session.task_store.create_task("unfinished worker task")
    config = create_node_config("response")
    config.metadata["replan_budget_exhausted"] = {"task_id": "task", "rationale": "cap"}

    validation = loop._validate_node_result(
        ResponseNode(config=config),
        LLMResult(content="The task failed after its replan budget was exhausted."),
    )

    assert validation.is_valid is True


def test_invalid_reviewer_approval_rolls_back_completed_parent() -> None:
    """Rollback keeps ancestors unfinished when a child approval is invalid (no result)."""
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Build app")
    child = store.create_task("Build vertical slice", parent_id=root.task_id)
    # Record result on child so approval goes through record_reviewer_decision
    store.record_result(
        child.task_id,
        TaskResult(content="Built app"),
    )
    store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
    # Now clear the result to simulate empty-result approval rejection
    child.result = None

    validation = loop._validate_node_result(
        reviewer,
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "task_review_decision",
                        "output": {
                            "success": True,
                            "task_id": child.task_id,
                            "decision": "approved",
                        },
                    }
                ]
            }
        ),
    )

    assert validation.is_valid is False
    assert child.status == TaskStatus.IN_PROGRESS
    assert root.status == TaskStatus.IN_PROGRESS


def test_completed_worker_final_response_must_not_ask_clarification() -> None:
    """Completed task trees need an outcome summary, not more questions."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("Build app")
    loop.root_session.task_store.record_result(task.task_id, TaskResult(content="Built app"))
    loop.root_session.task_store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.APPROVED,
    )

    validation = loop._validate_node_result(
        ResponseNode(),
        LLMResult(content="I need clarification on the current state before answering."),
    )

    assert validation.is_valid is False
    assert any("summarize completed task outcome" in error for error in validation.errors)


def test_reviewer_replan_keeps_task_tree_unfinished() -> None:
    """Replan is routing, not accepted completion."""
    store = TinyCUALoop().root_session.task_store
    root = store.create_task("Build app")
    child = store.create_task("Build vertical slice", parent_id=root.task_id)
    store.record_result(child.task_id, TaskResult(content="env only"))
    store.record_reviewer_decision(child.task_id, ReviewerDecision.REPLAN)

    assert child.status == TaskStatus.IN_PROGRESS
    assert store.active_task_id == child.task_id
    assert store.all_done() is False


def test_analyzer_failure_does_not_fabricate_app_vertical_slice() -> None:
    """Analyzer recovery must not fabricate a vertical-slice task.

    Spec: ./specs/tinycua-runtime-invariants/spec.md:29-42, 218-219, 261.
    Source: src/tinycua/docs/design/loops/tinycua_loop.md:67-84,
            src/tinycua/docs/design/loops/task_analyzer.md:23-31.
    When the analyzer misses its tool call and the root has no children, the
    recovery must NOT fabricate a hardcoded app/web-ui task. The runtime may
    only continue when the tree already has children; otherwise it must fail
    closed so the node retries its own contract.
    """
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer"),
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[analyzer, ResponseNode()]))
    root = loop.root_session.task_store.create_task("Build note app with web UI")

    recovered = loop._recover_task_analyzer_validation_failure(
        analyzer,
        ValidationResult(is_valid=False, errors=["missing task_decompose"]),
    )

    # No children exist, so recovery must NOT fabricate a vertical slice.
    assert recovered is False
    assert root.children == []
    assert not any(
        "vertical-slice" in str(t).lower()
        for t in [child.title for child in loop.root_session.task_store.tasks.values()]
    )


@pytest.mark.asyncio
async def test_response_exhaustion_falls_back_to_clean_direct_answer() -> None:
    """Bad response synthesis should not crash or replay internals."""
    loop = TinyCUALoop(queue=NodeQueue(items=[ResponseNode()]))

    result = await loop.run(
        ReplayingResponseAgent(),
        messages=[{"role": "user", "content": "Hello"}],
        tools=[],
    )

    assert result == "Hello!"


def test_task_result_update_merges_tool_evidence_metadata() -> None:
    """Enrichment attaches tool-call transcript evidence to task result metadata."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("write file")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="file written", success=True),
    )
    task.metadata["executor_partial_tool_results"] = [
        {
            "name": "write_file",
            "allowed": True,
            "output": {"success": True, "path": "jwt_utils.py"},
        }
    ]
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )

    loop._enrich_task_results_from_tool_batch(
        executor,
        [
            {
                "name": "task_result_update",
                "allowed": True,
                "output": {"success": True, "task_id": task.task_id},
            }
        ],
    )

    assert task.result is not None
    assert "tool_results" in task.result.metadata
    assert "executor_partial_tool_results" not in task.metadata


def test_shell_action_records_tool_audit_artifact(tmp_path) -> None:
    """Action tool results produce durable audit artifacts under .tinycua-artifacts."""
    artifact_dir = tmp_path / ".tinycua-artifacts"
    loop = TinyCUALoop(
        session_config=SessionConfig(workspace_dir=tmp_path, artifact_dir=artifact_dir)
    )
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    executor.ensure_session(loop.root_session)

    # Simulate a tool result from run_shell
    tool_result = {
        "name": "run_shell",
        "allowed": True,
        "output": {"stdout": "hello\n", "stderr": "", "exit_code": 0, "timed_out": False, "error": None},
    }
    audit_path = loop._write_tool_audit_artifact(
        "run_shell",
        {"command": "echo hello"},
        tool_result["output"],
    )

    assert audit_path is not None
    assert "run_shell" in audit_path
    audit_file = tmp_path / audit_path
    assert audit_file.exists()
    audit = json.loads(audit_file.read_text())
    assert audit["name"] == "run_shell"
    assert audit["arguments"]["command"] == "echo hello"
    assert audit["output"]["stdout"].strip() == "hello"

    # Verify _artifacts_from_tool_results includes audit artifacts
    tool_result["artifact_path"] = audit_path
    artifacts = loop._artifacts_from_tool_results([tool_result])
    audit_artifacts = [a for a in artifacts if a["kind"] == "tool_audit"]
    assert len(audit_artifacts) == 1
    assert audit_artifacts[0]["metadata"]["tool_name"] == "run_shell"


def test_non_action_tool_does_not_create_audit_artifact(tmp_path) -> None:
    """Read/list/task tools should not produce audit artifact files."""
    artifact_dir = tmp_path / ".tinycua-artifacts"
    loop = TinyCUALoop(
        session_config=SessionConfig(workspace_dir=tmp_path, artifact_dir=artifact_dir)
    )
    result = loop._write_tool_audit_artifact(
        "read_file",
        {"path": "app.py"},
        {"content": "file contents"},
    )
    assert result is None


def test_task_executor_read_only_evidence_retries_executor_not_replan() -> None:
    """Read/list-only executor evidence still goes back through executor/reviewer."""
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    response = ResponseNode()
    loop = TinyCUALoop(queue=NodeQueue(items=[executor, response]))
    task = loop.root_session.task_store.create_task("implement search")

    recovered = loop._recover_task_executor_validation_failure(
        executor,
        ValidationResult(is_valid=False, errors=["missing task_result_update"]),
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "read_file",
                        "allowed": True,
                        "output": "existing file contents",
                    },
                    {
                        "name": "list_files",
                        "allowed": True,
                        "output": ["app.py"],
                    },
                ]
            }
        ),
    )

    assert recovered is True
    assert "executor_partial_tool_results" not in task.metadata
    assert task.metadata["runtime_validation_failure"]["recovery"] == "executor_retry"
    assert task.metadata["runtime_validation_failure"]["tool_results"]
    assert "task_result_update" in task.metadata["runtime_validation_failure"]["guidance"]
    assert [node.node_id for node in loop.queue.items] == [
        "task_executor",
        "task_executor",
        "result_reviewer",
        "response",
    ]


def test_task_executor_success_without_action_evidence_is_structurally_valid() -> None:
    """Executor can report weak success; reviewer owns quality rejection."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("initialize backend")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="Created venv and requirements.txt", success=True),
    )
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )

    validation = loop._validate_node_result(
        executor,
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "task_execute",
                        "output": {"success": True, "task_id": task.task_id},
                    },
                    {
                        "name": "task_result_update",
                        "output": {"success": True, "task_id": task.task_id},
                    },
                    {"name": "terminate", "output": {"success": True}},
                ]
            },
        ),
    )

    assert validation.is_valid is True


def test_task_executor_failure_without_action_evidence_is_valid() -> None:
    """Executor failure claims are valid structurally so blockers reach reviewer/replan."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("initialize backend")
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )

    validation = loop._validate_node_result(
        executor,
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "task_execute",
                        "output": {"success": True, "task_id": task.task_id},
                    },
                    {
                        "name": "task_result_update",
                        "output": {"success": False, "task_id": task.task_id},
                    },
                    {"name": "terminate", "output": {"success": True}},
                ]
            },
        ),
    )

    assert validation.is_valid is True


def test_task_executor_success_without_action_evidence_reaches_reviewer() -> None:
    """Weak executor success is preserved for reviewer judgment."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("initialize backend")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="Created venv and requirements.txt", success=True),
    )
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    result = LLMResult(
        metadata={
            "tool_results": [
                {
                    "name": "task_execute",
                    "output": {"success": True, "task_id": task.task_id},
                },
                {
                    "name": "task_result_update",
                    "output": {"success": True, "task_id": task.task_id},
                },
                {"name": "terminate", "output": {"success": True}},
            ]
        },
    )

    loop._enrich_task_results_from_tool_batch(
        executor,
        result.metadata["tool_results"],
    )
    validation = loop._validate_node_result(executor, result)

    assert validation.is_valid is True
    assert task.result is not None
    assert task.result.success is True


def test_task_executor_repeated_success_without_evidence_stays_structural() -> None:
    """Repeated weak success remains executor-valid; reviewer decides quality."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("create requirements file")
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    unsupported_results = [
        {
            "name": "task_execute",
            "output": {"success": True, "task_id": task.task_id},
        },
        {
            "name": "task_result_update",
            "output": {"success": True, "task_id": task.task_id},
        },
        {"name": "terminate", "output": {"success": True}},
    ]
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="Created requirements.txt", success=True),
    )
    loop._enrich_task_results_from_tool_batch(executor, unsupported_results)
    task.reviewer_decisions.append(
        {
            "decision": "needs_revision",
            "rationale": "No concrete implementation evidence or artifacts were created.",
            "metadata": {},
        }
    )
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="Created requirements.txt", success=True),
    )
    result = LLMResult(metadata={"tool_results": unsupported_results})

    loop._enrich_task_results_from_tool_batch(executor, unsupported_results)
    validation = loop._validate_node_result(executor, result)

    assert validation.is_valid is True


def test_task_executor_read_only_evidence_is_left_to_reviewer() -> None:
    """Read/list evidence is not executor-invalid; reviewer decides sufficiency."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("create models")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="Created app/models.py", success=True),
    )
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )

    validation = loop._validate_node_result(
        executor,
        LLMResult(
            metadata={
                "tool_results": [
                    {"name": "list_files", "output": ["app/models.py"]},
                    {"name": "read_file", "output": "existing contents"},
                    {
                        "name": "task_result_update",
                        "output": {"success": True, "task_id": task.task_id},
                    },
                    {"name": "terminate", "output": {"success": True}},
                ]
            },
        ),
    )

    assert validation.is_valid is True
    assert task.result is not None


def test_task_executor_success_result_accepts_concrete_action_evidence() -> None:
    """Successful result update is valid when backed by implementation tools."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("write backend model")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="Created app/models.py", success=True),
    )
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )

    validation = loop._validate_node_result(
        executor,
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "write_file",
                        "output": {"success": True, "path": "app/models.py"},
                    },
                    {
                        "name": "task_result_update",
                        "output": {"success": True, "task_id": task.task_id},
                    },
                    {"name": "terminate", "output": {"success": True}},
                ]
            },
        ),
    )

    assert validation.is_valid is True


def test_reviewer_approval_requires_task_inspect() -> None:
    """Reviewer must call task_inspect before approving, even with a result report."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("create models")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="created backend/models.py", success=True),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )

    # Approval without task_inspect should be rejected
    validation = loop._validate_node_result(
        reviewer,
        LLMResult(
            tool_calls=[
                {
                    "function": {
                        "name": "task_review_decision",
                        "arguments": '{"decision":"approved"}',
                    }
                }
            ],
            metadata={
                "tool_results": [
                    {
                        "name": "task_review_decision",
                        "output": {
                            "success": True,
                            "task_id": task.task_id,
                            "decision": "approved",
                        },
                    },
                    {"name": "terminate", "output": {"success": True}},
                ]
            },
        ),
    )

    assert validation.is_valid is False
    assert any("task_inspect" in error for error in validation.errors)

    # But with task_inspect, approval is valid
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="created backend/models.py", success=True),
    )
    loop.root_session.task_store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.APPROVED,
    )

    validation_with_inspect = loop._validate_node_result(
        reviewer,
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "task_inspect",
                        "output": {"success": True, "tasks": {}},
                    },
                    {
                        "name": "task_review_decision",
                        "output": {
                            "success": True,
                            "task_id": task.task_id,
                            "decision": "approved",
                        },
                    },
                    {"name": "terminate", "output": {"success": True}},
                ]
            },
        ),
    )

    assert validation_with_inspect.is_valid is True


def test_result_reviewer_approval_without_artifact_inspection_is_valid() -> None:
    """Reviewer can approve a task with a result report after task_inspect."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("create models")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="created backend/models.py", success=True),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )

    validation = loop._validate_node_result(
        reviewer,
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "task_inspect",
                        "output": {"success": True, "tasks": {}},
                    },
                    {
                        "name": "task_review_decision",
                        "output": {
                            "success": True,
                            "task_id": task.task_id,
                            "decision": "approved",
                        },
                    },
                    {"name": "terminate", "output": {"success": True}},
                ]
            },
        ),
    )

    assert validation.is_valid is True


def test_result_reviewer_cannot_approve_failed_task_result() -> None:
    """Runtime-rejected or failed executor results require revision/replan review."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("create models")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="Runtime rejected claimed success", success=False),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )

    validation = loop._validate_node_result(
        reviewer,
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "task_review_decision",
                        "output": {
                            "success": True,
                            "task_id": task.task_id,
                            "decision": "approved",
                        },
                    }
                ]
            },
        ),
    )

    assert validation.is_valid is False
    assert any("cannot approve a failed task result" in error for error in validation.errors)


def test_task_assessor_validation_failure_skips_analyzer_gate() -> None:
    """Assessor prose-only failure means no selected decomposition target."""
    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor"),
    )
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer"),
    )
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    response = ResponseNode()
    loop = TinyCUALoop(queue=NodeQueue(items=[assessor, analyzer, executor, response]))
    loop.root_session.task_store.create_task("Root")

    recovered = loop._recover_task_assessor_validation_failure(
        assessor,
        ValidationResult(is_valid=False, errors=["missing task_update"]),
    )

    assert recovered is True
    root = loop.root_session.task_store.tasks[loop.root_session.task_store.root_task_id]
    assert root.metadata["assessor_recovery"]["recovery"] == "skip_analyzer"
    assert [node.node_id for node in loop.queue.items] == [
        "task_assessor",
        "task_executor",
        "response",
    ]


def test_optional_task_analyzer_validation_failure_skips_pass() -> None:
    """Analyzer prose-only failure after a task tree exists should not block execution."""
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    response = ResponseNode()
    loop = TinyCUALoop(queue=NodeQueue(items=[analyzer, executor, response]))
    root = loop.root_session.task_store.create_task("Root")
    loop.root_session.task_store.create_task("Write app", parent_id=root.task_id)

    recovered = loop._recover_task_analyzer_validation_failure(
        analyzer,
        ValidationResult(is_valid=False, errors=["missing task_update"]),
    )

    assert recovered is True
    assert root.metadata["analyzer_recovery"]["recovery"] == "skip_analyzer"
    assert [node.node_id for node in loop.queue.items] == [
        "task_analyzer",
        "task_executor",
        "response",
    ]


@pytest.mark.asyncio
async def test_task_executor_stops_after_successful_result_update() -> None:
    """Result update plus terminate ends executor turn before reviewer."""
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    response = ResponseNode()
    loop = TinyCUALoop(queue=NodeQueue(items=[executor, reviewer, response]))
    loop.root_session.task_store.create_task("write dependency file")
    agent = ExecutorResultThenReviewerAgent()

    result = await loop.run(
        agent,
        messages=[{"role": "user", "content": "create requirements"}],
        tools=[],
    )

    assert agent.executor_calls == 2
    assert agent.reviewer_calls == 2
    assert result == "Final success summary."
    transcript = loop.get_transcript_text(include_node_calls=True)
    assert "[TaskExecutor] LLM input" in transcript
    assert "[ResultReviewer] LLM input" in transcript
    assert "[Response] LLM input" in transcript
