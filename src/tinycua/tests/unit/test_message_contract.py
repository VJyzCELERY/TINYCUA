"""LLM message contract guardrails."""

from __future__ import annotations

import json

import pytest

from tinycua.config.node_config import NodeMessagePolicy, create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.config.types import LLMResult, Tool
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node_contract import LifecyclePhase
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.node import DecisionNode, DecisionResult
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.task_nodes import (
    TinyCUATaskAnalyzerNode,
    TinyCUATaskAssessorNode,
    TinyCUATaskExecutorNode,
    TinyCUAResultReviewerNode,
)
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.models.chat_record import ChatRecord
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.node_handoff import NodeHandoff
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session
from tinycua.models.session_context_entry import SessionContextEntry
from tinycua.models.task import AggregatedResult, ReviewerDecision, TaskResult, TaskStatus
from tinycua_sdk import Agent, LanguageModel


def test_build_node_messages_filters_blank_messages_and_preserves_roles() -> None:
    """LLM payloads contain no blank message content and keep assistant history."""
    loop = TinyCUALoop()
    node = TinyCUAQueryAnalystNode(
        node_id="query_analyst",
        config=create_node_config("query_analyst"),
    )
    node.config.message_policy = NodeMessagePolicy(
        include_chat_history=True,
        include_input_context=True,
    )
    node.ensure_session(loop.root_session)
    loop.root_session.input_context = [
        {"role": "user", "content": "\n\n"},
        {"role": "user", "content": "Summarize this."},
    ]
    loop.root_session.chat_history.append(
        ChatRecord(role="assistant", content="Prior answer")
    )
    loop.root_session.session_context.append(
        SessionContextEntry(content="", segment="output", source_node_id="x")
    )

    messages = loop._build_node_messages(node)

    assert all(str(message.get("content", "")).strip() for message in messages)
    assert {message["role"] for message in messages} >= {"user"}
    assert not any(message.get("content") == "Prior answer" for message in messages)


def test_downstream_nodes_do_not_replay_raw_user_input() -> None:
    """Only the entry node receives the SDK user message as user-role input."""
    loop = TinyCUALoop()
    raw_request = "Create a note-taking app in the workspace."
    loop.root_session.input_context = [{"role": "user", "content": raw_request}]
    loop.root_session.session_context.append(
        SessionContextEntry(
            content=DigestedInformation(
                context_summary="Need a workspace note-taking app.",
                original_query=raw_request,
            ),
            segment="output",
            source_node_id="digester",
        )
    )

    entry = TinyCUAQueryAnalystNode(
        node_id="query_analyst",
        config=create_node_config("query_analyst"),
    )
    task_create = TinyCUATaskCreateNode(
        node_id="task_create",
        config=create_node_config("task_create"),
    )
    task_analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer"),
    )
    task_executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    for node in (entry, task_create, task_analyzer, task_executor):
        node.ensure_session(loop.root_session)

    entry_messages = loop._build_node_messages(entry)
    downstream_messages = [
        loop._build_node_messages(task_create),
        loop._build_node_messages(task_analyzer),
        loop._build_node_messages(task_executor),
    ]

    assert any(
        message["role"] == "user" and message["content"] == raw_request
        for message in entry_messages
    )
    for messages in downstream_messages:
        assert not any(
            message["role"] == "user" and message["content"] == raw_request
            for message in messages
        )
        # Continuations are now [System: ...] user messages (not assistant).
        assert any(
            message["role"] == "user" and "[System:" in str(message["content"])
            and "Based on" in str(message["content"])
            for message in messages
        )


def test_query_analyst_worker_route_handoff_is_assistant_context() -> None:
    """Worker route passes a CEQ to Digester as internal assistant handoff."""
    query = TinyCUAQueryAnalystNode(
        node_id="query_analyst",
        config=create_node_config("query_analyst"),
    )
    query.session = Session(
        input_context=[
            {"role": "user", "content": "Build a local note app."},
        ]
    )
    response = ResponseNode(config=create_node_config("response"))
    queue = NodeQueue(items=[query, response])
    query._queue = queue

    query.on_complete(
        queue,
        DecisionResult(
            route_label="worker",
            analysis_response=LLMResult(content="worker"),
            classification_response=LLMResult(content="worker"),
        ),
    )

    digester = queue.items[1]
    node_input = queue._inputs[digester.node_id]

    assert isinstance(node_input, NodeInput)
    assert node_input.metadata["original_query"] == "Build a local note app."
    assert node_input.messages
    assert {message["role"] for message in node_input.messages} == {"assistant"}
    assert "Context Enhanced Query" in node_input.messages[0]["content"]


def test_forwarded_output_is_not_duplicated_in_next_node_prompt() -> None:
    """Direct NodeInput handoff wins over duplicate session-context replay."""
    loop = TinyCUALoop()
    worker = TinyCUAWorkerNode(
        node_id="worker",
        config=create_node_config("worker"),
    )
    loop.queue = NodeQueue(items=[worker])
    worker.ensure_session(loop.root_session)
    entry = SessionContextEntry(
        content=DigestedInformation(
            context_summary="Need runtime hardening",
            original_query="Finalize TinyCUA runtime",
        ),
        segment="output",
        source_node_id="digester",
    )
    loop.root_session.session_context.append(entry)
    loop.queue.set_input(
        worker,
        NodeInput(
            input_type="forwarded_output",
            source_node="digester",
            target_node="worker",
            messages=[
                {
                    "role": "assistant",
                    "content": '{"context_summary":"Need runtime hardening"}',
                }
            ],
            metadata={"source_record_ids": [entry.record_id]},
        ),
    )

    messages = loop._build_node_messages(worker)
    rendered = "\n".join(message["content"] for message in messages)

    assert rendered.count("Need runtime hardening") == 1


@pytest.mark.asyncio
async def test_streamed_task_executor_trace_keeps_native_tools() -> None:
    """Streaming finalization records resolved outer native tools in traces."""
    loop = TinyCUALoop()
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(loop.root_session)

    agent = Agent(llm_model=LanguageModel())
    await loop._finalize_streamed_node(
        node,
        agent,
        ["done"],
        [],
        node.config.tool_policy.resolve_tools([Tool(name="write_file")]),
    )

    assert "write_file" in loop.get_execution_trace()[-1]["resolved_tool_names"]


def test_action_tool_call_enters_commit_with_its_summary() -> None:
    """An action batch advances to the focused commit continuation."""
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )

    assert TinyCUALoop._advance_lifecycle_phase(
        node,
        LLMResult(
            content="Action Summary: wrote the requested file.",
            tool_calls=[{"function": {"name": "write_file"}}],
        ),
    )
    assert node.progress.lifecycle_phase is LifecyclePhase.COMMIT
    assert node.progress.action_summary == "Action Summary: wrote the requested file."


@pytest.mark.asyncio
async def test_streamed_action_tool_call_enters_commit() -> None:
    """Streaming action calls must expose the commit tools on the next turn."""
    loop = TinyCUALoop()
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(loop.root_session)

    await loop._finalize_streamed_node(
        node,
        Agent(llm_model=LanguageModel()),
        ["Action Summary: wrote the requested file."],
        [{"function": {"name": "write_file", "arguments": "{}"}}],
        [Tool(name="write_file")],
    )

    assert node.progress.lifecycle_phase is LifecyclePhase.COMMIT


def test_internal_output_context_uses_assistant_role_not_user() -> None:
    """Root session output context is not implicit downstream prompt input."""
    loop = TinyCUALoop()
    node = ResponseNode(config=create_node_config("response"))
    node.ensure_session(loop.root_session)
    loop.root_session.session_context.append(
        SessionContextEntry(
            content="Worker internal analysis",
            segment="output",
            source_node_id="worker",
        )
    )

    messages = loop._build_node_messages(node)

    assert not any(
        message.get("content") == "Worker internal analysis"
        for message in messages
    )


def test_decision_node_classification_continuation_uses_system_user_role() -> None:
    """The second decision-node call is internal control flow, not user input.

    Internal continuations use ``user`` role with a ``[System: ...]`` prefix
    (not ``assistant``) to prevent llama.cpp from "continuing" from the
    pre-filled text instead of generating a fresh response.
    """
    node = DecisionNode(
        node_id="decision",
        config=create_node_config("response"),
        classification_labels=["alpha", "beta"],
    )
    messages = [{"role": "user", "content": "External user request"}]
    captured_messages = []

    def capture_call(call_messages):
        captured_messages.extend(call_messages)
        return LLMResult(content="ok")

    node._call_llm = capture_call  # type: ignore[method-assign]

    captured = node._classification_call(messages, LLMResult(content="analysis"))

    assert captured.content == "ok"
    assert messages[-1] == {"role": "user", "content": "External user request"}
    assert captured_messages[-1]["role"] == "user"
    assert "Internal continuation" in captured_messages[-1]["content"]
    assert "[System:" in captured_messages[-1]["content"]


def test_response_node_continuation_is_not_assistant_role() -> None:
    """Response node continuation must not be assistant role.

    llama.cpp/LM Studio continues from the last assistant message. If the
    continuation is assistant, the model 'continues' the continuation text
    instead of generating a fresh response (output_tokens=1, continuation
    text echoed as output). The continuation must be a [System: ...] user
    message so the model generates a fresh response.
    """
    loop = TinyCUALoop()
    node = ResponseNode(config=create_node_config("response"))
    node.ensure_session(loop.root_session)

    messages = node.build_messages(loop.root_session, {})

    # No assistant message should contain the continuation text.
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert not any("Summarize" in m.get("content", "") for m in assistant_msgs)
    # The continuation should be a [System: ...] user message.
    system_user_msgs = [
        m for m in messages
        if m["role"] == "user" and "[System:" in m.get("content", "")
    ]
    assert any("Summarize" in m.get("content", "") for m in system_user_msgs)


def test_structured_internal_context_is_rendered_as_markdown_not_python_repr() -> None:
    """Structured root context is not implicitly rendered into later prompts."""
    loop = TinyCUALoop()
    node = ResponseNode(config=create_node_config("response"))
    node.ensure_session(loop.root_session)
    loop.root_session.session_context.append(
        SessionContextEntry(
            content=DigestedInformation(
                context_summary="Need runtime hardening",
                key_points=["force route tools"],
                original_query="Finalize TinyCUA runtime",
            ),
            segment="output",
            source_node_id="digester",
        )
    )
    loop.root_session.session_context.append(
        SessionContextEntry(
            content=AggregatedResult(
                root_task_id="root-1",
                accepted_results=[TaskResult(task_id="task-1", content="done")],
                final_context="completed",
            ),
            segment="output",
            source_node_id="result_aggregation",
        )
    )

    messages = loop._build_node_messages(node)
    rendered_context = "\n".join(message["content"] for message in messages)

    assert "DigestedInformation(" not in rendered_context
    assert "AggregatedResult(" not in rendered_context
    assert "## Digested Information" not in rendered_context
    assert "Need runtime hardening" not in rendered_context
    assert "force route tools" not in rendered_context
    assert "## Aggregated Result" not in rendered_context


def test_internal_retry_and_tool_only_chat_records_are_not_llm_bound() -> None:
    """Final prompts exclude retry diagnostics and durable tool audit records."""
    loop = TinyCUALoop()
    node = ResponseNode(config=create_node_config("response"))
    node.config.message_policy = NodeMessagePolicy(include_chat_history=True)
    node.ensure_session(loop.root_session)
    loop.root_session.chat_history.append(
        ChatRecord(
            role="assistant",
            content="RETRY_EXHAUSTED node=query_analyst",
            record_type="retry",
            visibility="internal",
        )
    )
    loop.root_session.chat_history.append(
        ChatRecord(
            role="tool",
            content={"name": "task_inspect", "output": "internal"},
            record_type="tool_result",
            visibility="tool_only",
        )
    )
    loop.root_session.chat_history.append(
        ChatRecord(role="assistant", content="Visible prior answer")
    )

    messages = loop._build_node_messages(node)
    rendered = "\n".join(message["content"] for message in messages)

    assert "RETRY_EXHAUSTED" not in rendered
    assert "task_inspect" not in rendered
    assert "Visible prior answer" not in rendered


def test_task_executor_prompt_is_limited_to_active_task_context() -> None:
    """Executor prompts exclude root user/digester context and use active task input."""
    loop = TinyCUALoop()
    raw_request = "ORIGINAL FULL USER REQUEST SHOULD NOT REACH EXECUTOR"
    loop.root_session.input_context = [{"role": "user", "content": raw_request}]
    loop.root_session.session_context.append(
        SessionContextEntry(
            content=DigestedInformation(
                context_summary="GLOBAL DIGEST SHOULD NOT REACH EXECUTOR",
                original_query=raw_request,
            ),
            segment="output",
            source_node_id="digester",
        )
    )
    loop.root_session.chat_history.append(
        ChatRecord(role="assistant", content="CHAT HISTORY SHOULD NOT REACH EXECUTOR")
    )
    root = loop.root_session.task_store.create_task("Build application")
    active = loop.root_session.task_store.create_task(
        "Create requirements.txt",
        parent_id=root.task_id,
    )
    loop.root_session.task_store.active_task_id = active.task_id
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    loop.queue = NodeQueue(items=[executor])

    messages, _ = loop._prepare_node(executor, [Tool(name="write_file")])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert raw_request not in rendered
    assert "GLOBAL DIGEST SHOULD NOT REACH EXECUTOR" not in rendered
    assert "CHAT HISTORY SHOULD NOT REACH EXECUTOR" not in rendered
    assert "Create requirements.txt" in rendered
    assert "Build application" in rendered
    assert '"active_task_id"' not in rendered
    assert '"task_tree"' not in rendered


def test_worker_forwards_digested_handoff_to_task_create() -> None:
    """Worker route handoff preserves the user request for task creation."""
    loop = TinyCUALoop()
    digest = DigestedInformation(
        context_summary="Build a note taking app with Python backend and web UI",
        original_query="Can you build me a note taking app?",
    )
    worker = TinyCUAWorkerNode(
        node_id="worker",
        config=create_node_config("worker"),
    )
    worker.session = loop.root_session
    loop.queue = NodeQueue(items=[worker])
    worker.build_messages(
        loop.root_session,
        NodeHandoff(
            source_node="digester",
            target_node="worker",
            instruction="Use this request context.",
            payload={"digested_information": digest},
        ),
    )

    worker.on_complete(
        loop.queue,
        DecisionResult(
            route_label="task_creation",
            analysis_response=LLMResult(),
            classification_response=LLMResult(),
        ),
    )
    task_create = loop.queue.items[1]
    handoff = loop.queue._inputs[task_create.node_id]  # noqa: SLF001 - verifies queue wiring.

    assert isinstance(handoff, NodeHandoff)
    assert handoff.payload["digested_information"] is digest


def test_task_executor_prompt_includes_workspace_path_discipline(tmp_path) -> None:
    """Executor prompts tell models how to address workspace paths generically."""
    loop = TinyCUALoop(session_config=SessionConfig(workspace_dir=tmp_path))
    loop.root_session.session_config = loop.session_config
    loop.root_session.task_store.create_task("Write web files")
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )

    messages, _ = loop._prepare_node(executor, [Tool(name="write_file")])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert str(tmp_path.resolve()) in rendered
    assert "relative paths" in rendered.lower()
    assert "do not rely on shell-specific brace expansion" in rendered
    assert "do not keep repeating read/list inspection" in rendered


@pytest.mark.parametrize(
    ("node", "unavailable_tools"),
    [
        (
            "task_analyzer",
            {"task_create", "task_decompose", "task_shrink", "task_update", "terminate"},
        ),
        ("task_assessor", {"node_handoff", "terminate"}),
        ("task_executor", {"task_result_update", "terminate"}),
        ("result_reviewer", {"task_review_decision", "terminate"}),
    ],
)
def test_lifecycle_action_prompts_do_not_require_commit_tools(
    node: str, unavailable_tools: set[str]
) -> None:
    """Action prompts name only tools available during the action phase."""
    loop = TinyCUALoop()
    task_node = {
        "task_analyzer": TinyCUATaskAnalyzerNode,
        "task_assessor": TinyCUATaskAssessorNode,
        "task_executor": TinyCUATaskExecutorNode,
        "result_reviewer": TinyCUAResultReviewerNode,
    }[node](node_id=node, config=create_node_config(node))

    messages, _ = loop._prepare_node(task_node, [])

    rendered = json.dumps(messages)
    assert not any(tool_name in rendered for tool_name in unavailable_tools)


def test_result_reviewer_prompt_excludes_stale_session_review_context() -> None:
    """Reviewer sees the active result under review, not old review blobs."""
    loop = TinyCUALoop()
    loop.root_session.session_context.append(
        SessionContextEntry(
            content={"type": "reviewed_task_context", "result": "STALE FAILURE"},
            segment="output",
            source_node_id="result_reviewer",
        )
    )
    task = loop.root_session.task_store.create_task("Current task")
    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="CURRENT RESULT", success=True),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    reviewer.ensure_session(loop.root_session)

    messages = loop._build_node_messages(reviewer)
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert "CURRENT RESULT" in rendered
    assert "STALE FAILURE" not in rendered


def test_result_reviewer_prefers_active_leaf_over_parent_aggregate() -> None:
    """Reviewer prompt and default review tool target stay aligned."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("Parent aggregate")
    active = loop.root_session.task_store.create_task("Active leaf", parent_id=root.task_id)
    root.result = TaskResult(content="STALE PARENT AGGREGATE")
    loop.root_session.task_store.record_result(
        active.task_id,
        TaskResult(content="ACTIVE LEAF RESULT", success=True),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    reviewer.ensure_session(loop.root_session)

    messages = loop._build_node_messages(reviewer)
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert "ACTIVE LEAF RESULT" in rendered
    assert "STALE PARENT AGGREGATE" not in rendered


def test_result_reviewer_updates_unified_task_context_without_context_append() -> None:
    """Reviewer context stays in the unified task tree, not session side channels."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("Retry task")
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    reviewer.ensure_session(loop.root_session)

    loop.root_session.task_store.record_result(
        task.task_id,
        TaskResult(content="failed attempt", success=False),
    )
    loop.root_session.task_store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.REJECTED,
        rationale="needs retry",
    )
    reviewer.parse_loop_result(
        LLMResult(
            metadata={
                "tool_results": [
                    {"name": "task_review_decision", "output": {"task_id": task.task_id}}
                ]
            }
        ),
        None,
    )

    task.result = TaskResult(content="recovered result", success=True)
    task.status = TaskStatus.IN_PROGRESS
    loop.root_session.task_store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.APPROVED,
        rationale="accepted",
    )
    reviewer.parse_loop_result(
        LLMResult(
            metadata={
                "tool_results": [
                    {"name": "task_review_decision", "output": {"task_id": task.task_id}}
                ]
            }
        ),
        None,
    )

    assert task.reviewer_decisions[-1]["decision"] == "approved"
    assert task.result is not None
    assert task.result.summary == "recovered result"
    assert "latest_review_context" not in task.metadata
    assert not any(
        getattr(entry, "source_node_id", "") == "result_reviewer"
        and getattr(entry, "content", {}).get("type") == "reviewed_task_context"
        for entry in loop.root_session.session_context
    )


def test_result_reviewer_prompt_uses_unified_task_context() -> None:
    """Reviewer sees active result plus future task context in one task snapshot."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("Build app")
    first = loop.root_session.task_store.create_task(
        "Create project scaffold",
        parent_id=root.task_id,
    )
    second = loop.root_session.task_store.create_task(
        "Create module x",
        parent_id=root.task_id,
    )
    loop.root_session.task_store.record_result(
        first.task_id,
        TaskResult(content="Created backend/app.py and frontend/index.html."),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )

    messages, _tools = loop._prepare_node(reviewer, [])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert "Unified task context" in rendered
    assert "Task under review" in rendered
    assert first.task_id in rendered
    assert second.task_id in rendered
    assert "Create module x" in rendered
    assert "Created backend/app.py" in rendered


def test_task_assessor_prompt_is_whole_tree_decomposition_only() -> None:
    """Assessor sees decomposition-gate context, not executor completion concepts."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("Build application")
    loop.root_session.task_store.create_task("Create backend", parent_id=root.task_id)
    loop.root_session.task_store.create_task("Create frontend", parent_id=root.task_id)
    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor"),
    )

    messages, tools = loop._prepare_node(assessor, [])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)
    node_handoff = next(tool for tool in tools if tool.name == "node_handoff")
    tool_surface = f"{node_handoff.description} {node_handoff.parameters}"
    combined = f"{rendered}\n{tool_surface}"

    assert "whole roadmap" in rendered.lower()
    assert "further decomposition" in rendered.lower()
    assert "task_result_update" not in combined
    assert "task_update" not in combined
    assert "node_handoff" not in rendered
    assert "complete" not in combined.lower()
    assert "fail executed work" not in combined.lower()
    assert "execution evidence" not in combined.lower()


def test_task_assessor_local_replan_prompt_is_active_region_only() -> None:
    """Reviewer replan assessor is scoped to the active/local task region."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("Build application")
    active = loop.root_session.task_store.create_task(
        "Create backend",
        parent_id=root.task_id,
    )
    loop.root_session.task_store.create_task("Create frontend", parent_id=root.task_id)
    loop.root_session.task_store.active_task_id = active.task_id
    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor", mode="local_replan"),
    )

    messages, tools = loop._prepare_node(assessor, [])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)
    node_handoff = next(tool for tool in tools if tool.name == "node_handoff")
    combined = f"{rendered}\n{node_handoff.description} {node_handoff.parameters}"

    assert "local replan" in rendered.lower()
    assert "active task" in rendered.lower()
    assert "Create backend" in rendered
    assert "whole roadmap" in rendered.lower()
    assert "task_result_update" not in combined
    assert "task_update" not in combined
    assert "node_handoff" not in rendered
    assert "execution evidence" not in combined.lower()


def test_task_analyzer_local_replan_prompt_does_not_replan_root() -> None:
    """Local replan analyzer is scoped away from root-roadmap decomposition."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("ROOT ROADMAP")
    active = loop.root_session.task_store.create_task(
        "Create frontend files",
        parent_id=root.task_id,
    )
    loop.root_session.task_store.create_task("Create backend API", parent_id=root.task_id)
    loop.root_session.task_store.active_task_id = active.task_id
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer", mode="local_replan"),
    )

    messages, _ = loop._prepare_node(analyzer, [])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert "Local task region for replan" in rendered
    assert "Create frontend files" in rendered
    assert "Do not decompose the root roadmap" in rendered
    assert "Task snapshot:" not in rendered


def test_local_replan_region_shows_sibling_and_child_results() -> None:
    """Local replan region (analyzer + assessor) renders full result summaries.

    Both the active task and its siblings/children carry their result summary
    in the rendered region so the assessor/analyzer can see exactly what was
    found and decide whether the region needs refinement — not just titles +
    statuses.
    """
    from tinycua.loops.task_nodes import _local_task_region, _render_local_region_markdown
    from tinycua.models.task import TaskResult, TaskStatus

    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("Build application")
    # Sibling A — completed with a result.
    sibling_a = loop.root_session.task_store.create_task("Fetch Vellum data", parent_id=root.task_id)
    sibling_a.status = TaskStatus.COMPLETED
    sibling_a.result = TaskResult(content="full vellum content", summary="Vellum: Claude Opus 4.8 #1", success=True)
    # Active task — in-progress with a partial result.
    active = loop.root_session.task_store.create_task("Fetch Kaggle dataset", parent_id=root.task_id)
    active.status = TaskStatus.IN_PROGRESS
    active.result = TaskResult(content="partial kaggle", summary="Kaggle: GPT-5.5 scores 89% MMLU", success=True)
    loop.root_session.task_store.active_task_id = active.task_id
    # Sibling B — pending, no result.
    loop.root_session.task_store.create_task("Fetch AlphaCorp article", parent_id=root.task_id)

    region = _local_task_region(loop.root_session)
    rendered = _render_local_region_markdown(region)

    # Active task result is rendered (full summary, no truncation).
    assert "Active: Fetch Kaggle dataset" in rendered
    assert "Kaggle: GPT-5.5 scores 89% MMLU" in rendered
    # Completed sibling result is rendered.
    assert "Fetch Vellum data" in rendered
    assert "Vellum: Claude Opus 4.8 #1" in rendered
    # Pending sibling shows title + status, no result line (it has none).
    assert "Fetch AlphaCorp article" in rendered
    # The region dict carries results for children + siblings (for any caller
    # that wants the structured form, not just the markdown render).
    assert any(s.get("result") == "Vellum: Claude Opus 4.8 #1" for s in region["siblings"])
    assert region["active_task"]["result"] == "Kaggle: GPT-5.5 scores 89% MMLU"


def test_digester_may_digest_without_forced_context_retrieval() -> None:
    """Digester can choose digest-only; retrieval is encouraged, not forced."""
    loop = TinyCUALoop()
    digester = TinyCUAInformationDigesterNode(
        node_id="digester",
        config=create_node_config("digester"),
    )

    digest_only = loop._validate_node_result(
        digester,
        LLMResult(
            content="",
            metadata={
                "tool_results": [
                    {"name": "digest_information", "allowed": True, "output": {}}
                ]
            },
        ),
    )
    retrieved_and_digested = loop._validate_node_result(
        digester,
        LLMResult(
            content="",
            metadata={
                "tool_results": [
                    {
                        "name": "enhanced_context_retrieval",
                        "allowed": True,
                        "output": {},
                    },
                    {"name": "digest_information", "allowed": True, "output": {}},
                ]
            },
        ),
    )

    assert digest_only.is_valid is True
    assert retrieved_and_digested.is_valid is True


def test_prepare_node_merges_tool_contract_into_single_system_message() -> None:
    """_prepare_node produces exactly one system message containing the tool contract."""
    loop = TinyCUALoop()
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(loop.root_session)

    messages, _ = loop._prepare_node(node, [Tool(name="write_file")])

    system_msgs = [m for m in messages if m.get("role") == "system"]
    assert len(system_msgs) == 1
    assert messages[0]["role"] == "system"
    assert "You are the TaskExecutor" in messages[0]["content"]
    # The SDK exposes tools natively (function schemas + tool_choice); the node
    # must NOT re-list tools as prose or instruct the LLM how to call them.
    assert "## Available actions" not in messages[0]["content"]
    assert "## Tool use" not in messages[0]["content"]
    assert "strict JSON" not in messages[0]["content"]


def test_normalize_system_messages_merges_late_system_messages() -> None:
    """Defensive normalizer collapses scattered system messages into one."""
    loop = TinyCUALoop()
    messages = [
        {"role": "system", "content": "A"},
        {"role": "assistant", "content": "B"},
        {"role": "system", "content": "C"},
    ]

    normalized = loop._normalize_system_messages(messages)

    system_msgs = [m for m in normalized if m.get("role") == "system"]
    assert len(system_msgs) == 1
    assert normalized[0]["role"] == "system"
    assert "A" in normalized[0]["content"]
    assert "C" in normalized[0]["content"]
    assert normalized[1] == {"role": "assistant", "content": "B"}


@pytest.mark.asyncio
async def test_stream_invalid_attempt_is_not_recorded_as_node_output() -> None:
    """Invalid streamed node output does not become reusable session context."""
    loop = TinyCUALoop()
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(loop.root_session)
    # Record a valid baseline output first
    node.session.session_context.append(
        SessionContextEntry(
            content="prior valid output",
            segment="output",
            source_node_id="task_executor",
        )
    )
    context_before = len(node.session.session_context)

    # Stream an invalid attempt (no tool calls, no task_result_update)
    agent = Agent(llm_model=LanguageModel())
    combined, validation, _ = await loop._finalize_streamed_node(
        node,
        agent,
        ["plan only answer"],
        [],
        node.config.tool_policy.resolve_tools([Tool(name="write_file")]),
    )

    assert not validation.is_valid
    # No new session context entry should have been added for the invalid content
    assert len(node.session.session_context) == context_before
    # Trace should still record the validation error for observability
    trace = loop.get_execution_trace()
    assert any(entry.get("validation_errors") for entry in trace)
