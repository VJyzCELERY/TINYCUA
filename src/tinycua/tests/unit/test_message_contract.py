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
from tinycua.models.task import (
    AggregatedResult,
    ReviewerDecision,
    TaskResult,
    TaskStatus,
)
from tinycua.tools.task_tools import TaskInitTool
from tinycua_sdk import Agent, LanguageModel


_LIFECYCLE_NODE_TYPES = (
    ("task_create", TinyCUATaskCreateNode),
    ("task_analyzer", TinyCUATaskAnalyzerNode),
    ("task_assessor", TinyCUATaskAssessorNode),
    ("task_executor", TinyCUATaskExecutorNode),
    ("result_reviewer", TinyCUAResultReviewerNode),
)


def test_task_create_keeps_user_request_authoritative() -> None:
    """Root generation may paraphrase but never invent or override requirements."""
    node = TinyCUATaskCreateNode(
        node_id="task_create", config=create_node_config("task_create")
    )
    guidance = f"{node._instruction} {TaskInitTool().description}".lower()

    assert "direct paraphrase" in guidance
    assert "never add" in guidance
    assert "never override" in guidance


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
            message["role"] == "user"
            and "[System:" in str(message["content"])
            and (
                "Based on" in str(message["content"])
                or "Your Actual Assigned Task" in str(message["content"])
            )
            for message in messages
        )


def test_assessor_separates_context_only_mission_from_actual_assignment() -> None:
    """Mission context cannot be mistaken for the assessor's delegated task."""
    session = Session()
    root = session.task_store.create_task("Research frontier LLMs")
    root.metadata["mission"] = "Research models and write report.md."
    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor"),
    )
    assessor.ensure_session(session)
    history_before = list(session.chat_history)
    context_before = list(session.session_context)

    messages = assessor.build_messages(session, {})

    rendered = "\n".join(str(message.get("content", "")) for message in messages)
    assert "## Current Mission — Context Only" in rendered
    assert "## Your Actual Assigned Task" in messages[-1]["content"]
    assert "coherent, actionable, and verifiable" in messages[-1]["content"]
    assert "not your assigned task" in rendered
    assert session.chat_history == history_before
    assert session.session_context == context_before


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

    summary_result = LLMResult(
        content="",
        metadata={
            "tool_results": [
                {
                    "name": "summarize_query_context",
                    "output": {
                        "success": True,
                        "context_summary": "Continue the existing note-app work.",
                    },
                }
            ]
        },
    )
    query.on_complete(
        queue,
        DecisionResult(
            route_label="worker",
            analysis_response=summary_result,
            classification_response=summary_result,
        ),
    )

    digester = queue.items[1]
    node_input = queue._inputs[digester.node_id]

    assert isinstance(node_input, NodeInput)
    assert node_input.metadata["original_query"] == "Build a local note app."
    assert node_input.messages
    assert {message["role"] for message in node_input.messages} == {"assistant"}
    assert node_input.messages[0]["content"] == (
        "Context:\nContinue the existing note-app work.\n\n"
        "User Request:\nBuild a local note app."
    )


def test_query_analyst_prompt_includes_root_session_context() -> None:
    """QA receives root context before committing its preliminary summary."""
    loop = TinyCUALoop()
    loop.root_session.input_context = [{"role": "user", "content": "Continue it."}]
    loop.root_session.session_context.append(
        SessionContextEntry(segment="output", content="Earlier migration decision.")
    )
    query = TinyCUAQueryAnalystNode(
        node_id="query_analyst", config=create_node_config("query_analyst")
    )
    loop.queue = NodeQueue(items=[query])

    messages, _tools = loop._prepare_node(query, [], None)

    assert any(
        message["content"] == "Earlier migration decision." for message in messages
    )
    assert any(message["content"] == "Continue it." for message in messages)


def test_query_analyst_passthrough_forwards_the_committed_ceq() -> None:
    """Routing changes the CEQ recipient, not its summary or user-request data."""
    query = TinyCUAQueryAnalystNode(
        node_id="query_analyst", config=create_node_config("query_analyst")
    )
    query.session = Session(input_context=[{"role": "user", "content": "Hello."}])
    response = ResponseNode(config=create_node_config("response"))
    queue = NodeQueue(items=[query, response])
    summary_result = LLMResult(
        metadata={
            "tool_results": [
                {
                    "name": "summarize_query_context",
                    "output": {"success": True, "context_summary": "Greet the user."},
                }
            ]
        }
    )

    query.on_complete(
        queue,
        DecisionResult(
            route_label="passthrough",
            analysis_response=summary_result,
            classification_response=summary_result,
        ),
    )

    handoff = queue._inputs[response.node_id]  # noqa: SLF001 - queue contract.
    assert (
        handoff.messages[0]["content"]
        == "Context:\nGreet the user.\n\nUser Request:\nHello."
    )
    assert handoff.metadata["original_query"] == "Hello."


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


@pytest.mark.parametrize(("node_id", "node_type"), _LIFECYCLE_NODE_TYPES)
def test_lifecycle_action_summary_enters_commit(
    node_id: str,
    node_type,
) -> None:
    """Every lifecycle node advances after its action summary turn."""
    node = node_type(
        node_id=node_id,
        config=create_node_config(node_id),
    )

    result = LLMResult(
        content="Action Summary: wrote the requested file.",
        tool_calls=[],
    )
    assert TinyCUALoop._advance_lifecycle_phase(
        node,
        result,
    )
    assert node.progress.lifecycle_phase is LifecyclePhase.COMMIT
    assert node.progress.action_summary == "Action Summary: wrote the requested file."


@pytest.mark.asyncio
@pytest.mark.parametrize(("node_id", "node_type"), _LIFECYCLE_NODE_TYPES)
async def test_streamed_lifecycle_action_summary_enters_commit(
    node_id: str,
    node_type,
) -> None:
    """A completed streamed action batch advances every lifecycle node to commit."""

    class SuccessfulTool(Tool):
        def __call__(self) -> dict[str, bool]:
            return {"success": True}

    loop = TinyCUALoop()
    node = node_type(
        node_id=node_id,
        config=create_node_config(node_id),
    )
    node.ensure_session(loop.root_session)

    await loop._finalize_streamed_node(
        node,
        Agent(llm_model=LanguageModel()),
        ["Action Summary: completed the requested check."],
        [{"function": {"name": "run_shell", "arguments": "{}"}}],
        [SuccessfulTool(name="run_shell")],
    )

    assert node.progress.lifecycle_phase is LifecyclePhase.COMMIT


def test_terminate_phase_hides_terminate_without_executor_commit() -> None:
    """TaskExecutor cannot expose terminate until it has staged a result."""
    loop = TinyCUALoop()
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.progress.satisfied_requirements.add("task_result_update")
    node.progress.advance_lifecycle(LifecyclePhase.TERMINATE)

    tools = loop._phase_tools(
        node,
        [Tool(name="task_result_update"), Tool(name="terminate")],
        LifecyclePhase.TERMINATE,
    )

    assert [tool.name for tool in tools] == ["task_result_update"]


def test_executor_action_phase_exposes_result_update_without_terminate() -> None:
    """Executor ACTION can report directly but cannot request termination."""
    loop = TinyCUALoop()
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )

    tools = loop._phase_tools(
        node,
        [
            Tool(name="read_file"),
            Tool(name="write_file"),
            Tool(name="task_result_update"),
            Tool(name="terminate"),
        ],
        LifecyclePhase.ACTION,
    )

    assert [tool.name for tool in tools] == [
        "read_file",
        "write_file",
        "task_result_update",
    ]
    assert TinyCUALoop._advance_lifecycle_phase(
        node,
        LLMResult(
            metadata={
                "tool_results": [{"name": "read_file", "output": {"success": True}}]
            }
        ),
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
        message.get("content") == "Worker internal analysis" for message in messages
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
        m
        for m in messages
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


def test_task_executor_renders_reviewer_verify_only_context() -> None:
    """Curated completed-work evidence directs the next executor to validate only."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("Validate generated module")
    task.metadata["context"] = ["Module already exists at src/module.py."]
    task.metadata["suggested_mode"] = "verify_only"
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )

    messages, _ = loop._prepare_node(executor, [])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert "Module already exists at src/module.py." in rendered
    assert "validate existing work before making changes" in rendered.lower()


@pytest.mark.parametrize(
    ("node", "owned_commit_tools"),
    [
        (
            "task_analyzer",
            {"task_decompose", "task_shrink", "task_update"},
        ),
        ("task_assessor", {"task_assessment_decision"}),
        ("result_reviewer", {"task_review_decision"}),
    ],
)
def test_lifecycle_action_prompts_expose_owned_commit_without_terminate(
    node: str, owned_commit_tools: set[str]
) -> None:
    """ACTION prompts expose only the node's intended phase tools."""
    loop = TinyCUALoop()
    task_node = {
        "task_analyzer": TinyCUATaskAnalyzerNode,
        "task_assessor": TinyCUATaskAssessorNode,
        "task_executor": TinyCUATaskExecutorNode,
        "result_reviewer": TinyCUAResultReviewerNode,
    }[node](node_id=node, config=create_node_config(node))

    messages, _ = loop._prepare_node(task_node, [])

    rendered = json.dumps(messages)
    if node == "result_reviewer":
        assert all(tool_name not in rendered for tool_name in owned_commit_tools)
    else:
        assert all(tool_name in rendered for tool_name in owned_commit_tools)
    assert "terminate" not in rendered


def test_task_create_prompt_does_not_request_legacy_terminate() -> None:
    """Task creation ends after its commit tool without a terminate instruction."""
    node = TinyCUATaskCreateNode(
        node_id="task_create",
        config=create_node_config("task_create"),
    )

    continuation = node.build_continuation()

    assert "root task" in continuation
    assert "task_init" not in continuation
    assert "terminate" not in continuation.lower()


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
    active = loop.root_session.task_store.create_task(
        "Active leaf", parent_id=root.task_id
    )
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


def test_result_reviewer_renders_active_description_and_advisory_root_criteria() -> (
    None
):
    """Leaf review is gated by its own work, not immutable root criteria."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task(
        "Ship application",
        acceptance_clauses=["The entire application is deployed."],
    )
    active = loop.root_session.task_store.create_task(
        "Implement parser",
        parent_id=root.task_id,
        description="Parse quoted CSV fields without data loss.",
    )
    loop.root_session.task_store.record_result(
        active.task_id,
        TaskResult(content="Parser tests pass.", success=True),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    reviewer.ensure_session(loop.root_session)

    rendered = reviewer.build_continuation(loop.root_session)

    assert "Active task description: Parse quoted CSV fields" in rendered
    assert "Root acceptance criteria" in rendered
    assert "immutable advisory context" in rendered
    assert "not leaf gates" in rendered
    assert "judge only the active task" in rendered.lower()


def test_result_reviewer_renders_root_criteria_as_final_gates() -> None:
    """When the root itself is reviewed, its acceptance criteria are gates."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task(
        "Ship application",
        acceptance_clauses=["The application passes its browser workflow."],
    )
    loop.root_session.task_store.record_result(
        root.task_id,
        TaskResult(content="Application completed.", success=True),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    reviewer.ensure_session(loop.root_session)

    rendered = reviewer.build_continuation(loop.root_session)

    assert "Root acceptance criteria (final review gates)" in rendered
    assert "verify every applicable criterion" in rendered.lower()
    assert "browser workflow" in rendered


def test_result_reviewer_renders_bounded_executor_evidence() -> None:
    """Reviewer sees executor commands and outcomes without full payloads."""
    loop = TinyCUALoop()
    task = loop.root_session.task_store.create_task("Verify application")
    result = TaskResult(content="Browser flow passes.", success=True)
    result.metadata["tool_results"] = [
        {
            "name": "run_shell",
            "outcome": {
                "tool_name": "run_shell",
                "success": True,
                "exit_code": 0,
                "error": None,
                "invocation": {"command": "sh .agent_scripts/browser.sh"},
                "content": "large output that should not be replayed",
            },
        }
    ]
    loop.root_session.task_store.record_result(task.task_id, result)
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    reviewer.ensure_session(loop.root_session)

    rendered = reviewer.build_continuation(loop.root_session)

    assert "Executor tool-call evidence" in rendered
    assert "sh .agent_scripts/browser.sh" in rendered
    assert "success=True" in rendered
    assert "exit_code=0" in rendered
    assert "large output" not in rendered


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
        metadata={"new_findings": ["The failed attempt needs revision."]},
    )
    reviewer.parse_loop_result(
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "task_review_decision",
                        "output": {"task_id": task.task_id},
                    }
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
        metadata={
            "finding_updates": [{"finding_id": "finding-1", "status": "ADDRESSED"}]
        },
    )
    reviewer.parse_loop_result(
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "task_review_decision",
                        "output": {"task_id": task.task_id},
                    }
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


def test_task_assessor_prompt_reviews_whole_tree_plan_quality() -> None:
    """Assessor reviews generic plan quality, not implementation choices."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("Build application")
    loop.root_session.task_store.create_task(
        "Create backend",
        parent_id=root.task_id,
        description="Provide the persistence-backed application API.",
    )
    loop.root_session.task_store.create_task("Create frontend", parent_id=root.task_id)
    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor"),
    )

    messages, tools = loop._prepare_node(assessor, [])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)
    decision_tool = next(
        tool for tool in tools if tool.name == "task_assessment_decision"
    )
    tool_surface = f"{decision_tool.description} {decision_tool.parameters}"
    combined = f"{rendered}\n{tool_surface}"

    assert "whole roadmap" in rendered.lower()
    assert "recursively refinable outcomes" in rendered.lower()
    assert "current granularity" in rendered.lower()
    assert "focused execution attempt and meaningful review" in rendered.lower()
    assert "materially improves execution or review" in rendered.lower()
    assert "large or further decomposable is not sufficient reason" in rendered.lower()
    assert "impose unsupported implementation choices" in rendered.lower()
    assert "Provide the persistence-backed application API." in rendered
    assert "narrowest useful node" in rendered
    assert "task_result_update" not in combined
    assert "task_update" not in combined
    assert "task_assessment_decision" in rendered
    assert "complete" not in combined.lower()
    assert "fail executed work" not in combined.lower()
    assert "execution evidence" not in combined.lower()


def test_task_analyzer_planning_snapshot_includes_descriptions() -> None:
    """Analyzer sees the context already stored on each planning task."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task(
        "Build application",
        description="Deliver the complete application requested by the user.",
    )
    loop.root_session.task_store.create_task(
        "Implement persistence",
        parent_id=root.task_id,
        description="Store text blocks in SQLite and preserve them across restarts.",
    )
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )

    messages, _ = loop._prepare_node(analyzer, [])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert "Store text blocks in SQLite and preserve them across restarts." in rendered
    assert "Deliver the complete application requested by the user." in rendered


def test_task_assessor_local_replan_prompt_is_active_region_only() -> None:
    """Reviewer replan assessor is scoped to the active/local task region."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("Build application")
    active = loop.root_session.task_store.create_task(
        "Create backend",
        parent_id=root.task_id,
        description="Expose the application API.",
    )
    loop.root_session.task_store.create_task(
        "Create frontend",
        parent_id=root.task_id,
        description="Render the browser interface.",
    )
    loop.root_session.task_store.active_task_id = active.task_id
    config = create_node_config("task_assessor", mode="local_replan")
    config.metadata["replan_reason"] = (
        "The original approach cannot satisfy the request."
    )
    assessor = TinyCUATaskAssessorNode(node_id="task_assessor", config=config)

    messages, tools = loop._prepare_node(assessor, [])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)
    decision_tool = next(
        tool for tool in tools if tool.name == "task_assessment_decision"
    )
    combined = f"{rendered}\n{decision_tool.description} {decision_tool.parameters}"

    assert "local replan" in rendered.lower()
    assert "active task" in rendered.lower()
    assert "Create backend" in rendered
    assert "Expose the application API." in rendered
    assert "Render the browser interface." in rendered
    assert "The original approach cannot satisfy the request." in rendered
    assert "recursively refinable outcomes" in rendered.lower()
    assert "current granularity" in rendered.lower()
    assert "do not reassess the whole roadmap" in rendered.lower()
    assert "task_result_update" not in combined
    assert "task_update" not in combined
    assert "task_assessment_decision" in rendered
    assert "execution evidence" not in combined.lower()


def test_task_analyzer_local_replan_prompt_does_not_replan_root() -> None:
    """Local replan analyzer is scoped away from root-roadmap decomposition."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("ROOT ROADMAP")
    active = loop.root_session.task_store.create_task(
        "Create frontend files",
        parent_id=root.task_id,
    )
    loop.root_session.task_store.create_task(
        "Create backend API", parent_id=root.task_id
    )
    loop.root_session.task_store.active_task_id = active.task_id
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer", mode="local_replan"),
    )

    messages, _ = loop._prepare_node(analyzer, [])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert "Local task region for replan" in rendered
    assert "Create frontend files" in rendered
    assert active.task_id in rendered
    assert "Do not decompose the root roadmap" in rendered
    assert "Task snapshot:" not in rendered


def test_local_replan_uses_bound_target_after_active_task_changes() -> None:
    """Queued local replans retain the reviewed task rather than a later active leaf."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("ROOT")
    target = loop.root_session.task_store.create_task("Target", parent_id=root.task_id)
    other = loop.root_session.task_store.create_task("Other", parent_id=root.task_id)
    loop.root_session.task_store.active_task_id = other.task_id
    config = create_node_config("task_analyzer", mode="local_replan")
    config.metadata["replan_task_id"] = target.task_id
    analyzer = TinyCUATaskAnalyzerNode(node_id="task_analyzer", config=config)

    messages, _ = loop._prepare_node(analyzer, [])
    rendered = "\n".join(str(message.get("content", "")) for message in messages)

    assert f"Active: Target (id={target.task_id})" in rendered
    assert f"Active: Other (id={other.task_id})" not in rendered


def test_local_replan_region_keeps_sibling_results_private() -> None:
    """Local replan sees sibling title/status but only the active result."""
    from tinycua.loops.task_nodes import (
        _local_task_region,
        _render_local_region_markdown,
    )
    from tinycua.models.task import TaskResult, TaskStatus

    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("Build application")
    # Sibling A — completed with a result.
    sibling_a = loop.root_session.task_store.create_task(
        "Fetch Vellum data", parent_id=root.task_id
    )
    sibling_a.status = TaskStatus.COMPLETED
    sibling_a.result = TaskResult(
        content="full vellum content",
        summary="Vellum: Claude Opus 4.8 #1",
        success=True,
    )
    # Active task — in-progress with a partial result.
    active = loop.root_session.task_store.create_task(
        "Fetch Kaggle dataset", parent_id=root.task_id
    )
    active.status = TaskStatus.IN_PROGRESS
    active.result = TaskResult(
        content="partial kaggle",
        summary="Kaggle: GPT-5.5 scores 89% MMLU",
        success=True,
    )
    loop.root_session.task_store.active_task_id = active.task_id
    # Sibling B — pending, no result.
    loop.root_session.task_store.create_task(
        "Fetch AlphaCorp article", parent_id=root.task_id
    )

    region = _local_task_region(loop.root_session)
    rendered = _render_local_region_markdown(region)

    # Active task result is rendered (full summary, no truncation).
    assert f"Active: Fetch Kaggle dataset (id={active.task_id})" in rendered
    assert "Kaggle: GPT-5.5 scores 89% MMLU" in rendered
    # Completed sibling remains visible as roadmap awareness without its result.
    assert "Fetch Vellum data" in rendered
    assert "Vellum: Claude Opus 4.8 #1" not in rendered
    # Pending sibling shows title + status, no result line (it has none).
    assert "Fetch AlphaCorp article" in rendered
    assert all("result" not in sibling for sibling in region["siblings"])
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
                    {
                        "name": "digest_information",
                        "allowed": True,
                        "output": {
                            "success": True,
                            "context_summary": "Relevant context was gathered.",
                        },
                    }
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
                    {
                        "name": "digest_information",
                        "allowed": True,
                        "output": {
                            "success": True,
                            "context_summary": "Relevant context was gathered.",
                        },
                    },
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
