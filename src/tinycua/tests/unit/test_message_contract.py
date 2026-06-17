"""LLM message contract guardrails."""

from __future__ import annotations

from tinycua.config.node_config import NodeMessagePolicy, create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.config.types import LLMResult, Tool
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
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
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session
from tinycua.models.session_context_entry import SessionContextEntry
from tinycua.models.task import AggregatedResult, ReviewerDecision, TaskResult, TaskStatus


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
    assert {message["role"] for message in messages} >= {"assistant", "user"}
    assert any(
        message["role"] == "assistant" and message["content"] == "Prior answer"
        for message in messages
    )


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
        assert any(
            message["role"] == "assistant" and "Based on" in str(message["content"])
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


def test_streamed_task_executor_trace_keeps_native_tools() -> None:
    """Streaming finalization records resolved outer native tools in traces."""
    loop = TinyCUALoop()
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(loop.root_session)

    loop._finalize_streamed_node(
        node,
        ["done"],
        [],
        node.config.tool_policy.resolve_tools([Tool(name="write_file")]),
    )

    assert "write_file" in loop.get_execution_trace()[-1]["resolved_tool_names"]


def test_internal_output_context_uses_assistant_role_not_user() -> None:
    """Node output context is internal assistant continuation, not user text."""
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

    assert any(
        message["role"] == "assistant"
        and message["content"] == "Worker internal analysis"
        for message in messages
    )
    assert not any(
        message["role"] == "user" and message["content"] == "Worker internal analysis"
        for message in messages
    )


def test_decision_node_classification_continuation_uses_assistant_role() -> None:
    """The second decision-node call is internal control flow, not user input."""
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
    assert captured_messages[-1]["role"] == "assistant"
    assert "Internal continuation" in captured_messages[-1]["content"]


def test_structured_internal_context_is_rendered_as_markdown_not_python_repr() -> None:
    """Known internal payloads are rendered as readable markdown before reaching the LLM."""
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
    # Now rendered as markdown, not raw JSON
    assert "## Digested Information" in rendered_context
    assert "Need runtime hardening" in rendered_context
    assert "force route tools" in rendered_context
    assert "## Aggregated Result" in rendered_context


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
    assert "Visible prior answer" in rendered


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
    loop._inject_active_task_input(executor)

    messages, _ = loop._prepare_node(executor, [Tool(name="write_file")])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert raw_request not in rendered
    assert "GLOBAL DIGEST SHOULD NOT REACH EXECUTOR" not in rendered
    assert "CHAT HISTORY SHOULD NOT REACH EXECUTOR" not in rendered
    assert "Create requirements.txt" in rendered
    assert "Build application" in rendered


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
    assert "Prefer relative paths" in rendered
    assert "/templates/index.html" in rendered
    assert "do not rely on shell-specific brace expansion" in rendered
    assert "do not keep repeating read/list inspection" in rendered


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
    task_update = next(tool for tool in tools if tool.name == "task_update")
    tool_surface = f"{task_update.description} {task_update.parameters}"
    combined = f"{rendered}\n{tool_surface}"

    assert "whole task tree" in rendered.lower()
    assert "further decomposition" in rendered.lower()
    assert "task_result_update" not in combined
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
    task_update = next(tool for tool in tools if tool.name == "task_update")
    combined = f"{rendered}\n{task_update.description} {task_update.parameters}"

    assert "local replan" in rendered.lower()
    assert "active task" in rendered.lower()
    assert "Create backend" in rendered
    assert "whole roadmap" in rendered.lower()
    assert "task_result_update" not in combined
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
    assert "Tool-use contract" in messages[0]["content"]


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


def test_stream_invalid_attempt_is_not_recorded_as_node_output() -> None:
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
    combined, validation, _ = loop._finalize_streamed_node(
        node,
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
