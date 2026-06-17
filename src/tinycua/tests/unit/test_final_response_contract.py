"""Final response contracts: no synthetic success and observable final stream."""

from __future__ import annotations

import json
import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.config.node_config import NodeConfigBase
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.node import NodeExecutionError, ProcessNode
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode
from tinycua.loops.task_nodes import TinyCUATaskAssessorNode
from tinycua.loops.task_nodes import TinyCUATaskExecutorNode
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import TaskResult


class EmptyResponseAgent:
    """Agent double that returns an empty terminal response."""

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        if not stream:
            return {"role": "assistant", "content": ""}

        async def events():
            if False:
                yield {}

        return events()


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


class NonterminalFailureThenResponseAgent:
    """Agent double that fails TaskCreate then answers at ResponseNode."""

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
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
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
    """An empty ResponseNode result raises instead of synthetic success."""
    loop = TinyCUALoop(queue=NodeQueue(items=[ResponseNode()]))

    with pytest.raises(NodeExecutionError, match="Final response must be non-empty"):
        await loop.run(
            EmptyResponseAgent(),
            messages=[{"role": "user", "content": "do work"}],
            tools=[],
        )

    assert "Processed request" not in loop.get_transcript_text()


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
    """A nonterminal validation failure must not synthesize Response output."""
    task_create = TinyCUATaskCreateNode(
        node_id="task_create",
        config=create_node_config("task_create"),
    )
    response = ResponseNode()
    loop = TinyCUALoop(queue=NodeQueue(items=[task_create, response]))

    with pytest.raises(NodeExecutionError, match="task_create failed runtime validation"):
        await loop.run(
            NonterminalFailureThenResponseAgent(),
            messages=[{"role": "user", "content": "create a task"}],
            tools=[],
        )

    trace = loop.get_execution_trace()
    assert [entry["node_id"] for entry in trace] == [
        "task_create",
        "task_create",
        "task_create",
    ]
    assert all(entry["validation_errors"] for entry in trace)
    assert "response" not in [entry["node_id"] for entry in trace]


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
    """Worker task trees must be complete before success response synthesis."""
    loop = TinyCUALoop(queue=NodeQueue(items=[ResponseNode()]))
    loop.root_session.task_store.create_task("unfinished worker task")

    with pytest.raises(NodeExecutionError, match="actually completed"):
        await loop.run(
            TextResponseAgent("Done successfully."),
            messages=[{"role": "user", "content": "finish the task"}],
            tools=[],
        )


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
    assert task.metadata["executor_partial_tool_results"]
    assert [node.node_id for node in loop.queue.items] == [
        "task_executor",
        "task_executor",
        "result_reviewer",
        "response",
    ]


def test_task_result_update_merges_prior_partial_artifacts() -> None:
    """Reviewer evidence includes files written before result update."""
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
    assert task.result.artifacts == [
        {"path": "jwt_utils.py", "kind": "file", "metadata": {"tool_name": "write_file"}}
    ]
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


def test_task_executor_success_without_action_evidence_is_invalid() -> None:
    """Executor success claims without successful action/research tools are structurally invalid."""
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
                ]
            },
        ),
    )

    assert validation.is_valid is False
    assert any("action" in e.lower() for e in validation.errors)


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
                ]
            },
        ),
    )

    assert validation.is_valid is True


def test_task_executor_success_without_action_evidence_fails_validation() -> None:
    """Runtime validates structural evidence; result is preserved for reviewer to inspect."""
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
            ]
        },
    )

    loop._enrich_task_results_from_tool_batch(
        executor,
        result.metadata["tool_results"],
    )
    validation = loop._validate_node_result(executor, result)

    assert validation.is_valid is False
    # Result is preserved for reviewer despite structural validation failure
    assert task.result is not None
    assert task.result.success is True


def test_task_executor_repeated_success_without_evidence_fails_validation() -> None:
    """Repeated success claims without action evidence still fail structural validation."""
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

    assert validation.is_valid is False


def test_task_executor_read_only_evidence_fails_action_gate() -> None:
    """Read/list evidence is not action evidence; success claim fails structural validation."""
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
                ]
            },
        ),
    )

    assert validation.is_valid is False
    # Artifacts are still preserved for reviewer inspection
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
                ]
            },
        ),
    )

    assert validation.is_valid is True


def test_result_reviewer_approval_with_artifacts_requires_inspection() -> None:
    """Reviewer is a quality gate and must inspect artifacts before approval."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("create models")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="created backend/models.py", success=True),
    )
    task.artifacts.append({"path": "backend/models.py", "kind": "file", "metadata": {}})
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )

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
                    }
                ]
            },
        ),
    )

    assert validation.is_valid is False
    assert any("inspect" in error.lower() for error in validation.errors)


def test_result_reviewer_cannot_approve_after_failed_list_files() -> None:
    """Reviewer approval after failed list_files (output error) is invalid."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("create models")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="created backend/models.py", success=True),
    )
    task.artifacts.append({"path": "backend/models.py", "kind": "file", "metadata": {}})
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
                        "name": "list_files",
                        "output": {"error": "Path outside workspace: /"},
                    },
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
    assert any("inspect" in error.lower() for error in validation.errors)


def test_result_reviewer_task_inspect_only_does_not_satisfy_artifact_inspection() -> None:
    """task_inspect alone does not verify workspace/file state for artifact approval."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("create models")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="created backend/models.py", success=True),
    )
    task.artifacts.append({"path": "backend/models.py", "kind": "file", "metadata": {}})
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )

    validation = loop._validate_node_result(
        reviewer,
        LLMResult(
            metadata={
                "tool_results": [
                    {"name": "task_inspect", "output": {"status": "inspected"}},
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


def test_result_reviewer_successful_list_files_satisfies_inspection() -> None:
    """Successful list_files satisfies artifact inspection for approval."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("create models")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="created backend/models.py", success=True),
    )
    task.artifacts.append({"path": "backend/models.py", "kind": "file", "metadata": {}})
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )

    validation = loop._validate_node_result(
        reviewer,
        LLMResult(
            metadata={
                "tool_results": [
                    {"name": "list_files", "output": ["backend/models.py"]},
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
    """A successful task_result_update ends executor turn before reviewer."""
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
    task = loop.root_session.task_store.create_task("write dependency file")
    task.metadata["executor_partial_tool_results"] = [
        {
            "name": "write_file",
            "allowed": True,
            "output": {"success": True, "path": "requirements.txt"},
        }
    ]
    agent = ExecutorResultThenReviewerAgent()

    result = await loop.run(
        agent,
        messages=[{"role": "user", "content": "create requirements"}],
        tools=[],
    )

    assert agent.executor_calls == 1
    assert result == "Final success summary."
    transcript = loop.get_transcript_text(include_node_calls=True)
    assert "[TaskExecutor] LLM input" in transcript
    assert "[ResultReviewer] LLM input" in transcript
    assert "[Response] LLM input" in transcript
