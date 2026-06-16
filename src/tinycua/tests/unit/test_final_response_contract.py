"""Final response contracts: no synthetic success and observable final stream."""

from __future__ import annotations

import pytest

from tinycua.config.node_config import create_node_config
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


def test_task_executor_validation_failure_schedules_local_replan() -> None:
    """Executor validation failures become local replan, not task results."""
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

    assert recovered is True
    assert task.result is None
    assert task.reviewer_decisions == []
    assert loop.root_session.task_store.active_task_id == task.task_id
    assert [node.node_id for node in loop.queue.items] == [
        "task_executor",
        "task_assessor",
        "task_analyzer",
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


def test_task_executor_read_only_evidence_replans_instead_of_looping() -> None:
    """Read/list-only inspection is not enough to continue executor forever."""
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
    assert task.metadata["runtime_validation_failure"]["recovery"] == "local_replan"
    assert task.metadata["runtime_validation_failure"]["tool_results"]
    assert "repeating inspection" in task.metadata["runtime_validation_failure"]["guidance"]
    assert [node.node_id for node in loop.queue.items] == [
        "task_executor",
        "task_assessor",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
        "response",
    ]


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
    assert [node.node_id for node in loop.queue.items] == [
        "task_assessor",
        "task_executor",
        "response",
    ]
    root = loop.root_session.task_store.tasks[loop.root_session.task_store.root_task_id]
    assert root.metadata["assessor_recovery"]["recovery"] == "skip_analyzer"


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
    loop.root_session.task_store.create_task("write dependency file")
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
