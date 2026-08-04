"""Tests for TinyCUALoop — node execution, message merging, tool scoping, override, streaming."""

from __future__ import annotations

import asyncio
import collections.abc

import pytest
from unittest.mock import AsyncMock, MagicMock

from tinycua.config.node_config import (
    NodeConfigBase,
    NodeToolPolicy,
    create_node_config,
)
from tinycua.config.types import LLMResult, Tool
from tinycua.config.types import ValidationError
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node_contract import LifecyclePhase
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.task_nodes import (
    TinyCUAAnalysisEffortNode,
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskAssessorNode,
    TinyCUATaskExecutorNode,
)
from tinycua.models.task import TaskResult
from tinycua.models.node_handoff import NodeHandoff
from tinycua.models.node_input import NodeInput
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session import Session
from tinycua_sdk import Agent, LanguageModel
from tinycua_sdk.agent import BaseLoop

from tests.unit.helpers.tinycua_loop_helpers import StubNode, ResponseNode


# --- Basic construction tests ---


def test_tinycua_loop_extends_base_loop():
    """TinyCUALoop is a subclass of SDK BaseLoop."""
    session = Session()
    loop = TinyCUALoop(root_session=session)
    assert isinstance(loop, BaseLoop)


def test_tinycua_loop_creates_session_by_default():
    """TinyCUALoop creates a Session when none provided."""
    loop = TinyCUALoop()
    assert isinstance(loop.root_session, Session)
    assert loop.root_session.session_id is not None


def test_tinycua_loop_uses_provided_session():
    """TinyCUALoop uses the provided session."""
    session = Session()
    loop = TinyCUALoop(root_session=session)
    assert loop.root_session is session


def test_tinycua_loop_has_node_queue():
    """TinyCUALoop creates a NodeQueue by default."""
    loop = TinyCUALoop()
    assert isinstance(loop.queue, NodeQueue)
    assert loop.queue.is_empty() is True


def test_tinycua_loop_stores_session_config():
    """TinyCUALoop stores session_config; factory applies it to session."""
    from tinycua.config.session_config import SessionConfig

    config = SessionConfig(max_context_messages=50)
    loop = TinyCUALoop(session_config=config)
    assert loop.session_config is config
    assert loop.root_session.session_config is None


def test_workspace_session_defaults_external_artifact_store(tmp_path):
    """Embedded workspace sessions get unique system-owned history storage."""
    from tinycua.config.session_config import SessionConfig

    first = TinyCUALoop(session_config=SessionConfig(workspace_dir=tmp_path))
    second = TinyCUALoop(session_config=SessionConfig(workspace_dir=tmp_path))

    assert first.session_dir is not None
    assert first.session_dir.is_relative_to(tmp_path) is False
    assert first.session_dir != second.session_dir


def test_tinycua_loop_has_no_iteration_limit():
    """TinyCUALoop does not impose an iteration limit."""
    loop = TinyCUALoop()
    assert not hasattr(loop, "max_iterations")


def test_compact_runtime_nodes_have_output_budget() -> None:
    """Planner/reviewer/executor nodes are bounded to avoid runaway streams."""
    loop = TinyCUALoop()
    assessor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    planner = TinyCUAInformationDigesterNode(
        node_id="digester",
        config=create_node_config("digester"),
    )

    assert loop._node_max_tokens_override(planner, model=None) is None
    assert loop._node_max_tokens_override(assessor, model=None) is None


def test_worker_state_nodes_have_long_retry_budget() -> None:
    """One-shot worker nodes should not exhaust after only a few attempts."""
    executor = create_node_config("task_executor")
    reviewer = create_node_config("result_reviewer")

    assert executor.retry_policy.max_attempts >= 25
    assert reviewer.retry_policy.max_attempts >= 25


def test_retry_message_is_assistant_self_correction() -> None:
    """Retry continuations should be natural assistant messages, not system force."""
    loop = TinyCUALoop()
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )

    message = loop._stream_retry_message(
        agent=object(),
        node=executor,
        resolved_tools=[Tool(name="task_result_update")],
        error=ValidationError("missing task_result_update"),
        attempt=1,
        llm_result=LLMResult(),
    )

    assert "task_result_update" in message
    assert "I need to" not in message
    assert "ONLY strict JSON" not in message


def test_executor_retry_keeps_action_tools_before_action_evidence() -> None:
    """Executor retries keep action tools available before result update."""
    loop = TinyCUALoop()
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    tools = [Tool(name="write_file"), Tool(name="task_result_update")]
    message = loop._retry_message_for_validation(
        ValidationError("missing task_result_update"),
        executor,
        tools,
        LLMResult(
            metadata={
                "tool_results": [
                    {"name": "task_execute", "output": {"success": True}},
                ]
            }
        ),
    )

    retry_tools = loop._tools_for_retry_attempt(executor, tools, message)

    assert {tool.name for tool in retry_tools} == {"write_file", "task_result_update"}


def test_executor_retry_keeps_action_tools_after_action_evidence() -> None:
    """Executor retries stay natural and only validate result update on exit."""
    loop = TinyCUALoop()
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    tools = [Tool(name="write_file"), Tool(name="task_result_update")]
    message = loop._retry_message_for_validation(
        ValidationError("missing task_result_update"),
        executor,
        tools,
        LLMResult(
            metadata={
                "tool_results": [
                    {
                        "name": "write_file",
                        "output": {"success": True, "path": "models/note.py"},
                    },
                ]
            }
        ),
    )

    retry_tools = loop._tools_for_retry_attempt(executor, tools, message)

    assert {tool.name for tool in retry_tools} == {"write_file", "task_result_update"}


def test_executor_retry_keeps_all_tools_after_inspection() -> None:
    """Executor keeps normal ReAct freedom after inspection."""
    loop = TinyCUALoop()
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    tools = [
        Tool(name="list_files"),
        Tool(name="read_file"),
        Tool(name="write_file"),
        Tool(name="task_result_update"),
    ]

    retry_tools = loop._tools_for_retry_attempt(
        executor,
        tools,
        "Use an appropriate action or research tool, then call task_result_update.",
    )

    assert {tool.name for tool in retry_tools} == {
        "list_files",
        "read_file",
        "write_file",
        "task_result_update",
    }


def test_executor_result_update_is_available_during_action_phase() -> None:
    """The owned commit tool is available during ACTION without terminate."""
    loop = TinyCUALoop()
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    result = LLMResult(tool_calls=[{"function": {"name": "task_result_update"}}])

    scoped = loop._tools_for_lifecycle_result(
        executor,
        result,
        [
            Tool(name="read_file"),
            Tool(name="task_result_update"),
            Tool(name="terminate"),
        ],
    )

    assert executor.progress.lifecycle_phase is LifecyclePhase.ACTION
    assert [tool.name for tool in scoped] == ["read_file", "task_result_update"]


def test_ready_assessor_handoff_skips_only_paired_analyzer() -> None:
    """A ready assessment preserves the next configured assessor pass."""
    loop = TinyCUALoop()
    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor"),
    )
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer"),
    )
    next_effort = TinyCUAAnalysisEffortNode(
        node_id="analysis_effort",
        config=create_node_config("analysis_effort"),
    )
    loop.queue = NodeQueue([assessor, analyzer, next_effort])

    handoff = NodeHandoff(
        source_node="task_assessor",
        target_node="task_analyzer",
        instruction="Assessment recorded.",
        payload={
            "decision": "ready",
            "selected_task_ids": [],
            "rationale": "The roadmap is executable.",
        },
    )

    assert loop._skip_ready_assessor_analyzer(assessor, handoff)
    assert [node.node_id for node in loop.queue.items] == [
        "task_assessor",
        "analysis_effort",
    ]

    loop.queue.advance()
    loop.queue.current.session = loop.root_session
    loop.queue.current.run_deterministic(loop.queue)

    assert [node.node_id for node in loop.queue.items[:4]] == [
        "analysis_effort",
        "task_assessor",
        "task_analyzer",
        "analysis_effort",
    ]


def test_analysis_effort_appends_final_assessor_without_analyzer() -> None:
    """Exhausting analysis always leaves one final bounded assessment."""
    loop = TinyCUALoop()
    effort = TinyCUAAnalysisEffortNode(
        node_id="analysis_effort",
        config=create_node_config("analysis_effort"),
        pass_count=2,
        pass_limit=2,
    )
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    loop.queue = NodeQueue([effort, executor])

    effort.run_deterministic(loop.queue)

    assert [node.node_id for node in loop.queue.items] == [
        "analysis_effort",
        "task_assessor",
        "task_executor",
    ]
    final = loop.queue.items[1]
    assert final.config.metadata["task_assessor_mode"] == "final_assessment"


def test_final_assessment_discards_analyzer_handoff_and_proceeds() -> None:
    """Final findings remain task metadata instead of scheduling more analysis."""
    loop = TinyCUALoop()
    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor", mode="final_assessment"),
    )
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor", config=create_node_config("task_executor")
    )
    loop.queue = NodeQueue([assessor, executor])
    loop._pending_handoffs.append(
        NodeHandoff(
            source_node="task_assessor",
            target_node="task_analyzer",
            instruction="Budget exhausted.",
            payload={
                "decision": "analyze",
                "selected_task_ids": ["task-1"],
                "analysis_budget_exhausted": True,
            },
        )
    )

    assert loop._pop_handoff_for_next(assessor) is None
    assert loop._pending_handoffs == []
    loop.queue.advance()
    assert loop.queue.current is executor


def test_response_validation_rejects_internal_transcript_replay() -> None:
    """Final response must not replay node prompts or aggregation JSON."""
    loop = TinyCUALoop()
    response = ResponseNode()

    validation = loop._validate_final_response_content(
        response,
        LLMResult(content="Task under review: abc\n## Current State\n..."),
    )

    assert validation.is_valid is False
    assert "not replay internal" in validation.errors[0]


def test_task_assessor_retry_narrows_to_required_decision_tool() -> None:
    """Assessor retries isolate its decision instead of repeating inspection."""
    loop = TinyCUALoop()
    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor"),
    )
    tools = assessor.config.tool_policy.resolve_tools([])

    retry_tools = loop._tools_for_retry_attempt(
        assessor,
        tools,
        "task_assessor must call successful task-state tool(s): "
        "['task_assessment_decision']",
    )

    assert [tool.name for tool in retry_tools] == ["task_assessment_decision"]


# --- _execute_node tests ---


async def test_execute_node_calls_agent_with_node_messages():
    """_execute_node() builds messages from node and calls agent._call_llm()."""
    stub = StubNode("node output")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )
    agent._call_llm.assert_called()


async def test_run_sync_continues_until_terminal():
    """Loop continues through nonterminal nodes until ResponseNode."""
    stub = StubNode("node output")
    terminal = ResponseNode()
    queue = NodeQueue(items=[stub, terminal])

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )

    assert agent._call_llm.call_count == 2


async def test_execute_node_records_chat_history():
    """_execute_node() appends each node's LLM call to root_session.chat_history."""
    stub = StubNode("history test")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    session = loop.root_session
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert len(session.chat_history) > 0


async def test_execute_node_records_session_context():
    """_execute_node() records session_context via node.record_output()."""
    stub = StubNode("context test")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    session = loop.root_session
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert len(session.session_context) > 0


async def test_execute_node_stops_at_terminal():
    """_execute_node() stops processing when a terminal node is encountered."""
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "final", "tool_calls": None})

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert isinstance(result, str)


# --- message merging tests ---


async def test_message_merging_populates_input_context():
    """run() merges SDK messages into root_session.input_context."""
    loop = TinyCUALoop()
    session = loop.root_session
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]

    await loop.run(
        agent=agent,
        messages=messages,
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert session.input_context == messages


async def test_message_merging_preserves_order():
    """Merged messages retain their original order."""
    loop = TinyCUALoop()
    session = loop.root_session
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]

    await loop.run(
        agent=agent,
        messages=messages,
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert [m["content"] for m in session.input_context] == ["first", "second", "third"]


# --- tool scoping tests ---


async def test_tool_scoping_filters_tools_per_node():
    """NodeToolPolicy.resolve_tools() filters outer tools per node config."""
    policy = NodeToolPolicy(
        include_agent_tools="selected",
        allowed_agent_tool_names=["tool_a"],
    )
    config = NodeConfigBase(tool_policy=policy)
    node = StubNode()
    node.config = config

    tool_a = MagicMock()
    tool_a.name = "tool_a"
    tool_b = MagicMock()
    tool_b.name = "tool_b"
    outer_tools = [tool_a, tool_b]
    resolved = config.tool_policy.resolve_tools(outer_tools)
    assert len(resolved) == 1


async def test_tool_scoping_all_tools():
    """NodeToolPolicy with include_agent_tools='all' passes all tools through."""
    policy = NodeToolPolicy(include_agent_tools="all")
    config = NodeConfigBase(tool_policy=policy)
    node = StubNode()
    node.config = config

    tool_a = MagicMock()
    tool_a.name = "tool_a"
    tool_b = MagicMock()
    tool_b.name = "tool_b"
    outer_tools = [tool_a, tool_b]
    resolved = config.tool_policy.resolve_tools(outer_tools)
    assert len(resolved) == 2


@pytest.mark.asyncio
async def test_execute_tool_calls_unwraps_provider_nested_arguments() -> None:
    """Provider adapters unwrap {arguments:{...}} only for real tool kwargs."""
    loop = TinyCUALoop()
    calls = []

    class WriteLikeTool(Tool):
        def __init__(self) -> None:
            super().__init__(
                name="write_file",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            )

        def __call__(self, path: str, content: str) -> dict[str, object]:
            calls.append((path, content))
            return {"success": True, "path": path}

    agent = Agent(llm_model=LanguageModel())
    results = await loop._execute_tool_calls(
        agent,
        [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "arguments": '{"arguments":{"path":"app.py","content":"print(1)"}}',
                },
            }
        ],
        [WriteLikeTool()],
    )

    assert calls == [("app.py", "print(1)")]
    assert results[0]["output"] == {"success": True, "path": "app.py"}


@pytest.mark.asyncio
async def test_execute_tool_calls_preserves_full_normalized_url_provenance() -> None:
    """Evidence records the exact executed URL after provider argument unwrapping."""
    loop = TinyCUALoop()
    calls = []
    url = "https://example.test/models/" + "frontier-model-" * 40

    class FetchLikeTool(Tool):
        def __init__(self) -> None:
            super().__init__(
                name="fetch_url",
                parameters={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                    "additionalProperties": False,
                },
            )

        def __call__(self, url: str) -> dict[str, object]:
            calls.append(url)
            return {"success": True, "content": "model profile"}

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [
            {
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "arguments": {"arguments": {"url": url}},
                },
            }
        ],
        [FetchLikeTool()],
    )

    assert calls == [url]
    assert results[0]["outcome"]["invocation"]["url"] == url


@pytest.mark.asyncio
async def test_execute_tool_calls_preserves_real_arguments_parameter() -> None:
    """Nested unwrapping must not break tools with a genuine arguments kwarg."""
    loop = TinyCUALoop()
    calls = []

    class ArgumentsTool(Tool):
        def __init__(self) -> None:
            super().__init__(
                name="argument_sink",
                parameters={
                    "type": "object",
                    "properties": {"arguments": {"type": "object"}},
                    "required": ["arguments"],
                    "additionalProperties": False,
                },
            )

        def __call__(self, arguments: dict[str, object]) -> dict[str, object]:
            calls.append(arguments)
            return {"success": True}

    agent = Agent(llm_model=LanguageModel())
    results = await loop._execute_tool_calls(
        agent,
        [
            {
                "type": "function",
                "function": {
                    "name": "argument_sink",
                    "arguments": '{"arguments":{"value":1}}',
                },
            }
        ],
        [ArgumentsTool()],
    )

    assert calls == [{"value": 1}]
    assert results[0]["output"] == {"success": True}


@pytest.mark.asyncio
async def test_execute_tool_calls_discards_duplicate_terminate() -> None:
    """One model response cannot execute termination more than once."""
    loop = TinyCUALoop()
    calls = []

    class TerminateTool(Tool):
        def __init__(self) -> None:
            super().__init__(name="terminate", parameters={"type": "object"})

        def __call__(self) -> dict[str, object]:
            calls.append("terminate")
            return {"success": True}

    agent = Agent(llm_model=LanguageModel())
    results = await loop._execute_tool_calls(
        agent,
        [
            {"function": {"name": "terminate", "arguments": {}}},
            {"function": {"name": "terminate", "arguments": {}}},
        ],
        [TerminateTool()],
    )

    assert calls == ["terminate"]
    assert [result["name"] for result in results] == ["terminate"]


def test_coerce_structured_tool_calls_accepts_allowed_tool_key_payload() -> None:
    """Local tool-call shims may emit {tool_name:{...}} instead of tool_calls."""
    loop = TinyCUALoop()
    tool = Tool(
        name="task_review_decision",
        parameters={
            "type": "object",
            "properties": {
                "decision": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["decision"],
            "additionalProperties": False,
        },
    )
    result = LLMResult(
        content=(
            '<tool_call>{"task_review_decision":{"decision":"needs_revision",'
            '"rationale":"inspect requirements"}}</tool_call>'
        ),
    )

    loop._coerce_structured_tool_calls(result, [tool])

    assert result.tool_calls == [
        {
            "id": "call_json_0_task_review_decision",
            "type": "function",
            "function": {
                "name": "task_review_decision",
                "arguments": '{"decision": "needs_revision", "rationale": "inspect requirements"}',
            },
        }
    ]


def test_coerce_structured_tool_calls_accepts_multiline_allowed_tool_payload() -> None:
    """Local models may emit explicit tool JSON with literal newlines."""
    loop = TinyCUALoop()
    tool = Tool(
        name="task_result_update",
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "task_id": {"type": "string"},
                "success": {"type": "boolean"},
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    )
    result = LLMResult(
        content=(
            '{"task_result_update":{"content":"Successfully initialized\n'
            '**Status:**\nAll required infrastructure is in place.",'
            '"task_id":"task-1","success":true}}</tool_call>'
        ),
    )

    loop._coerce_structured_tool_calls(result, [tool])

    assert result.tool_calls
    assert result.tool_calls[0]["function"]["name"] == "task_result_update"
    arguments = result.tool_calls[0]["function"]["arguments"]
    assert "All required infrastructure" in arguments


def test_coerce_structured_tool_calls_accepts_name_arguments_payload() -> None:
    """Local models may emit explicit {name, arguments} tool-call JSON."""
    loop = TinyCUALoop()
    tool = Tool(
        name="task_execute",
        parameters={
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "additionalProperties": False,
        },
    )
    result = LLMResult(
        content=(
            '{"name":"task_execute","arguments":{"task_id":"task-1"}}</tool_call>'
        ),
    )

    loop._coerce_structured_tool_calls(result, [tool])

    assert result.tool_calls
    assert result.tool_calls[0]["function"]["name"] == "task_execute"
    assert result.tool_calls[0]["function"]["arguments"] == '{"task_id": "task-1"}'


def test_coerce_structured_tool_calls_accepts_multiple_name_arguments_payloads() -> (
    None
):
    """Multiple explicit local-model tool payloads become one tool batch."""
    loop = TinyCUALoop()
    tools = [Tool(name="task_execute"), Tool(name="list_files")]
    result = LLMResult(
        content=(
            '{"name":"task_execute","arguments":{"task_id":"task-1"}}'
            "</tool_call>\n"
            '{"name":"list_files","arguments":{"path":"."}}</tool_call>'
        ),
    )

    loop._coerce_structured_tool_calls(result, tools)

    assert [item["function"]["name"] for item in result.tool_calls] == [
        "task_execute",
        "list_files",
    ]


def test_coerce_structured_tool_calls_ignores_prose_without_allowed_tool_key() -> None:
    """Compatibility coercion still ignores arbitrary prose JSON."""
    loop = TinyCUALoop()
    result = LLMResult(content='I think {"decision":"approved"} is fine.')

    loop._coerce_structured_tool_calls(result, [Tool(name="task_review_decision")])

    assert result.tool_calls == []


# --- override_instructions tests ---


async def test_override_instructions_passed_to_node():
    """override_instructions reaches node.build_instruction() during message building."""
    stub = StubNode("override test")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "default"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions="custom instructions",
        stream=False,
    )
    agent._call_llm.assert_called()


# --- stream tests ---


async def test_stream_false_returns_string():
    """run(stream=False) returns a string response."""
    stub = StubNode("string result")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert isinstance(result, str)


async def test_stream_true_returns_async_iterator():
    """run(stream=True) returns an async iterator with content deltas."""
    stub = StubNode("streaming response")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []

    async def mock_stream(*args, **kwargs):
        yield {"type": "response.output_text.delta", "delta": "Hello"}
        yield {"type": "response.output_text.delta", "delta": " world"}
        yield {"type": "response.completed", "finish_reason": "completed"}

    agent._call_llm = mock_stream

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )
    assert isinstance(result, collections.abc.AsyncIterator)
    events = [e async for e in result]
    assert len(events) > 0
    assert any(e["type"] == "response.output_text.delta" for e in events)


async def test_streamed_direct_commit_does_not_restart_completed_lifecycle_node() -> (
    None
):
    """A successful ACTION commit completes instead of being redispatched."""
    node = TinyCUATaskCreateNode(
        node_id="task_create",
        config=create_node_config("task_create"),
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[node]))
    calls = 0

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent.tool_permissions = {}
    agent.is_cancelled = False
    agent.policy = MagicMock(max_tool_calls=100)
    agent._cancel_event = asyncio.Event()

    async def mock_stream(*args, **kwargs):
        nonlocal calls
        del args, kwargs
        calls += 1
        if calls == 1:
            yield {
                "type": "tool_call.ready",
                "id": "task-init",
                "name": "task_init",
                "arguments": '{"title":"Initialized root","acceptance_clauses":["done"]}',
            }
            return
        raise AssertionError("completed lifecycle node was redispatched")

    async def mock_call(*args, **kwargs):
        return mock_stream(*args, **kwargs)

    agent._call_llm = mock_call

    async for _event in loop._stream_node_events(
        node,
        agent,
        [],
        None,
        loop.queue.input_for_current(),
    ):
        pass

    assert calls == 1
    assert node.node_id not in loop.root_session.node_progress


async def test_commit_retries_until_reviewer_decision_then_auto_completes() -> None:
    """A valid commit completes without a separate terminate turn."""
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[reviewer]))
    store = loop.root_session.task_store
    root = store.create_task("Root")
    task = store.create_task("Work", parent_id=root.task_id)
    store.record_result(task.task_id, TaskResult(content="done", success=True))
    reviewer.ensure_session(loop.root_session)
    tool_sets: list[set[str]] = []
    commit_calls = 0

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent.tool_permissions = {}
    agent.is_cancelled = False
    agent.policy = MagicMock(max_tool_calls=100)
    agent._cancel_event = asyncio.Event()

    async def mock_stream(_messages, tools, *, stream=False):
        nonlocal commit_calls
        del stream
        names = {tool.name for tool in tools}
        tool_sets.append(names)
        commit_calls += 1
        if commit_calls == 1:
            yield {"type": "response.completed", "finish_reason": "completed"}
            return
        if commit_calls == 2:
            yield {
                "type": "tool_call.ready",
                "id": "review",
                "name": "task_review_decision",
                "arguments": (
                    '{"task_id":"' + task.task_id + '",'
                    '"decision":"needs_revision",'
                    '"rationale":"[finding]: retry [validate]: rerun",'
                    '"review_summary":"The validation must be rerun.",'
                    '"new_findings":["Retry and rerun validation."]}'
                ),
            }
            return
        yield {"type": "response.completed", "finish_reason": "completed"}

    async def mock_call(*args, **kwargs):
        return mock_stream(*args, **kwargs)

    agent._call_llm = mock_call

    async for _event in loop._stream_node_events(
        reviewer,
        agent,
        [],
        None,
        loop.queue.input_for_current(),
    ):
        pass

    assert commit_calls == 2
    assert tool_sets[0] == {"task_inspect", "artifact_inspect"}
    assert tool_sets[1] == {
        "task_review_decision",
        "json_draft_create",
    }
    assert not store._staged_reviewer_decisions
    assert task.reviewer_decisions[-1]["decision"] == "needs_revision"


async def test_streaming_reentry_is_consumed_before_node_restarts() -> None:
    """A streaming retry cannot leak its re-entry flag past redispatch."""
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[reviewer]))
    reviewer.ensure_session(loop.root_session)
    reviewer.progress.advance_lifecycle(LifecyclePhase.COMMIT)
    reviewer.progress.recovery_attempts["focused_retry"] = 1
    loop._recovery_reentry = True

    events = loop._stream_node_events(
        reviewer,
        MagicMock(),
        [],
        None,
        loop.queue.input_for_current(),
    )
    event = await anext(events)
    await events.aclose()

    assert event["type"] == "node.started"
    assert loop._recovery_reentry is False
    assert reviewer.progress.lifecycle_phase == LifecyclePhase.ACTION
    assert reviewer.progress.recovery_attempts == {"focused_retry": 1}


async def test_commit_stream_does_not_delegate_lifecycle_to_sdk(monkeypatch) -> None:
    """TinyCUA, not the SDK loop, owns lifecycle tool execution."""
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    loop = TinyCUALoop()
    reviewer.ensure_session(loop.root_session)
    reviewer.progress.advance_lifecycle(LifecyclePhase.COMMIT)
    iteration_limits: list[int] = []
    base_run = BaseLoop.run

    async def tracking_run(self, *args, **kwargs):
        iteration_limits.append(self.max_iterations)
        return await base_run(self, *args, **kwargs)

    monkeypatch.setattr(BaseLoop, "run", tracking_run)

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent.tool_permissions = {}
    agent.is_cancelled = False
    agent.policy = MagicMock(max_tool_calls=100)
    agent._cancel_event = asyncio.Event()

    async def mock_stream(*args, **kwargs):
        del args, kwargs
        yield {"type": "response.completed", "finish_reason": "completed"}

    agent._call_llm = mock_stream
    commit_tools = loop._phase_tools(
        reviewer,
        reviewer.config.tool_policy.resolve_tools([]),
        LifecyclePhase.COMMIT,
    )

    async for _event in loop._collect_stream_events(
        reviewer,
        agent,
        [],
        commit_tools,
        [],
        [],
        False,
        False,
        "result_reviewer",
        1,
    ):
        pass

    assert iteration_limits == []


async def test_run_sync_consumes_canonical_stream_runtime():
    """Non-stream run drains _run_stream instead of executing a second loop."""
    loop = TinyCUALoop()
    calls = 0

    async def fake_stream(agent, tools, override_instructions=None):
        nonlocal calls
        del agent, tools, override_instructions
        calls += 1
        yield {
            "type": "response.output_text.delta",
            "node_id": "response",
            "delta": "final",
        }

    loop._run_stream = fake_stream  # type: ignore[method-assign]

    result = await loop._run_sync(MagicMock(), [], None)

    assert result == "final"
    assert calls == 1


async def test_stream_true_emits_nonterminal_token_deltas():
    """Streaming mode emits token deltas for nonterminal LLM nodes too."""
    stub = StubNode("streaming nonterminal", node_id="planner")
    terminal = ResponseNode()
    queue = NodeQueue(items=[stub, terminal])

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    call_count = 0

    async def mock_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {"type": "response.output_text.delta", "delta": "plan"}
            yield {"type": "response.output_text.delta", "delta": " tokens"}
        else:
            yield {"type": "response.output_text.delta", "delta": " final"}

    agent._call_llm = mock_stream

    result = await loop.run(agent, messages=[], tools=[], stream=True)
    events = [event async for event in result]

    planner_deltas = [
        event
        for event in events
        if event.get("type") == "response.output_text.delta"
        and event.get("node_id") == "planner"
    ]
    assert [event["delta"] for event in planner_deltas] == ["plan", " tokens"]
    assert stub.session is not None
    assert [entry.content for entry in stub.session.session_context] == ["plan tokens"]


async def test_stream_task_executor_receives_injected_active_task_context():
    """Streaming executor path injects the same active-task context as sync path."""
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    queue = NodeQueue(items=[executor])
    loop = TinyCUALoop(queue=queue)
    root = loop.root_session.task_store.create_task("Build application")
    active = loop.root_session.task_store.create_task(
        "Create requirements.txt",
        parent_id=root.task_id,
    )
    loop.root_session.task_store.active_task_id = active.task_id
    captured_messages = []

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent.tool_permissions = {}

    async def mock_stream(messages, tools, *, stream=False):
        del tools, stream
        captured_messages.extend(messages)
        yield {"type": "response.output_text.delta", "delta": "working"}
        yield {
            "type": "tool_call.ready",
            "id": "call_1",
            "name": "task_result_update",
            "arguments": '{"content":"done","success":true}',
        }
        yield {
            "type": "tool_call.ready",
            "id": "call_2",
            "name": "terminate",
            "arguments": "{}",
        }

    agent._call_llm = mock_stream

    # Provide real tools so validation passes and the unbounded recovery loop
    # doesn't spin forever.
    from tinycua.tools.task_tools import TaskResultUpdateTool, TerminateTool

    task_result_tool = TaskResultUpdateTool()
    task_result_tool.bind_task_store(loop.root_session.task_store)
    terminate_tool = TerminateTool()

    async for _event in loop._stream_node_events(
        executor,
        agent,
        [task_result_tool, terminate_tool],
        None,
        loop.queue.input_for_current(),
    ):
        pass

    rendered = "\n".join(
        str(message.get("content", "")) for message in captured_messages
    )
    assert "Create requirements.txt" in rendered
    assert "Build application" in rendered


async def test_stream_retry_prompt_replaces_prior_retry_prompt() -> None:
    """Streaming retries use base context plus one current retry prompt."""
    query = TinyCUAQueryAnalystNode(
        node_id="query_analyst",
        config=create_node_config("query_analyst"),
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[query]))
    loop.root_session.input_context = [{"role": "user", "content": "hello"}]
    query.ensure_session(loop.root_session)
    captured_messages: list[list[dict]] = []

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []

    async def mock_stream(messages, tools, *, stream=False):
        del tools, stream
        captured_messages.append(list(messages))
        yield {"type": "response.output_text.delta", "delta": "passthrough"}
        # After 3 retries, produce a select_query_route tool call so the
        # unbounded recovery loop succeeds and the test doesn't spin forever.
        if len(captured_messages) > 3:
            yield {
                "type": "tool_call.ready",
                "id": "call_summary",
                "name": "summarize_query_context",
                "arguments": '{"context_summary":"Pass the request through."}',
            }
            yield {
                "type": "tool_call.ready",
                "id": "call_route",
                "name": "select_query_route",
                "arguments": '{"route":"passthrough","reason":"test"}',
            }
        yield {"type": "response.completed", "finish_reason": "completed"}

    agent._call_llm = mock_stream

    # Provide routing tools used by the QueryAnalyst retry path.
    from tinycua.config.types import Tool as SimpleTool
    from tinycua.tools.query_context_summary import QueryContextSummaryTool

    route_tool = SimpleTool(name="select_query_route")
    route_tool.__call__ = lambda **kw: {"success": True, "route": "passthrough"}  # type: ignore[method-assign]

    async for _event in loop._stream_node_events(
        query,
        agent,
        [QueryContextSummaryTool(), route_tool],
        None,
        loop.queue.input_for_current(),
    ):
        pass

    retry_counts = [
        sum(
            "Call summarize_query_context" in str(message.get("content", ""))
            for message in call_messages
        )
        for call_messages in captured_messages
    ]
    assert retry_counts[:3] == [0, 1, 1]  # first 3 are the normal retries


async def test_stream_digester_digest_only_does_not_route_to_response():
    """Digester may choose digest-only without terminal failure routing."""
    digester = TinyCUAInformationDigesterNode(
        node_id="digester",
        config=create_node_config("digester"),
    )
    response = ResponseNode()
    queue = NodeQueue(items=[digester, response])
    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent.tool_permissions = {}
    agent.is_cancelled = False
    agent.policy = MagicMock(max_tool_calls=100)
    agent._cancel_event = asyncio.Event()

    async def mock_stream(messages, tools, *, stream=False):
        del messages, tools, stream
        yield {
            "type": "tool_call.ready",
            "id": "commit-digest",
            "name": "digest_information",
            "arguments": (
                '{"context_summary":"Relevant context was gathered.",'
                '"key_points":[],"advisory_instructions":[],'
                '"constraints":[],"known_gaps":[]}'
            ),
        }

    agent._call_llm = mock_stream

    events = [
        event
        async for event in loop._stream_node_events(
            digester,
            agent,
            [],
            None,
            loop.queue.input_for_current(),
        )
    ]

    assert any(
        event.get("type") == "node.completed" and event.get("node_id") == "digester"
        for event in events
    )
    assert loop.queue.current is digester
    assert not any(
        entry.get("node_id") == "response" for entry in loop.get_execution_trace()
    )


async def test_stream_digester_observes_exploration_before_structured_commit() -> None:
    """Exploration cannot complete Digester before its structured commit."""
    digester = TinyCUAInformationDigesterNode(
        node_id="digester",
        config=create_node_config("digester"),
    )
    queue = NodeQueue(items=[digester])
    queue.set_input(
        digester,
        NodeInput(
            input_type="worker",
            metadata={"original_query": "Summarize the available context"},
        ),
    )
    loop = TinyCUALoop(queue=queue)
    calls = 0

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent.tool_permissions = {}
    agent.is_cancelled = False
    agent.policy = MagicMock(max_tool_calls=100)
    agent._cancel_event = asyncio.Event()

    async def mock_stream(_messages, tools, *, stream=False):
        nonlocal calls
        del stream
        calls += 1
        assert "digest_information" in {tool.name for tool in tools}
        if calls == 1:
            yield {
                "type": "tool_call.ready",
                "id": "inspect-context",
                "name": "list_files",
                "arguments": '{"path":"."}',
            }
            return
        if calls == 2:
            yield {
                "type": "tool_call.ready",
                "id": "commit-digest",
                "name": "digest_information",
                "arguments": (
                    '{"context_summary":"Relevant context was gathered.",'
                    '"key_points":["One relevant input was found"],'
                    '"constraints":[],"advisory_instructions":[],'
                    '"known_gaps":[]}'
                ),
            }
            return
        raise AssertionError("Digester continued after its successful commit")

    agent._call_llm = mock_stream

    async for _event in loop._stream_node_events(
        digester,
        agent,
        [Tool(name="list_files")],
        None,
        queue.input_for_current(),
    ):
        pass

    assert calls == 2
    digests = [
        entry.content
        for entry in loop.root_session.session_context
        if isinstance(entry.content, DigestedInformation)
    ]
    assert digests[-1].context_summary == "Relevant context was gathered."
    assert digests[-1].original_query == "Summarize the available context"


# --- Existing passthrough tests (backward compat) ---


async def test_run_records_user_message():
    """run() records user messages in input_context (not chat_history)."""
    stub = StubNode("response")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={
            "content": "Hi",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )
    messages = [{"role": "user", "content": "hello"}]
    await loop.run(agent, messages, tools=[], stream=False)
    # User messages are stored in input_context, not chat_history
    user_msgs = [m for m in loop.root_session.input_context if m["role"] == "user"]
    assert len(user_msgs) == 1
    assert user_msgs[0]["content"] == "hello"
    # chat_history should not contain user messages (ChatRecord objects)
    chat_user_msgs = [m for m in loop.root_session.chat_history if m.role == "user"]
    assert len(chat_user_msgs) == 0


async def test_run_records_assistant_response():
    """run() records assistant response in chat_history."""
    stub = StubNode("response")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={
            "content": "Hello there",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )
    messages = [{"role": "user", "content": "hi"}]
    await loop.run(agent, messages, tools=[], stream=False)
    assistant_msgs = [
        m for m in loop.root_session.chat_history if m.role == "assistant"
    ]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[-1].content == "Hello there"


async def test_run_calls_build_system_message_with_override():
    """run() passes override_instructions to node execution via _build_node_messages."""
    stub = StubNode("response")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={
            "content": "ok",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )
    messages = [{"role": "user", "content": "test"}]
    with pytest.MonkeyPatch.context() as m:
        original_build = loop._build_node_messages
        called_with = []

        def spy_build(node, override=None):
            called_with.append(override)
            return original_build(node, override)

        m.setattr(loop, "_build_node_messages", spy_build)
        await loop.run(
            agent,
            messages,
            tools=[],
            override_instructions="custom instructions",
            stream=False,
        )
    assert "custom instructions" in called_with


async def test_run_with_empty_messages():
    """run() handles empty messages list gracefully."""
    stub = StubNode("response")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={
            "content": "No input needed",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )
    result = await loop.run(agent, messages=[], tools=[], stream=False)
    assert isinstance(result, str)
    # No user messages to record, but assistant response is still recorded
    assistant_msgs = [
        m for m in loop.root_session.chat_history if m.role == "assistant"
    ]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[-1].content == "No input needed"


async def test_run_stream_records_chat_history():
    """run(stream=True) records accumulated content in chat_history."""
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []

    async def mock_stream(*args, **kwargs):
        yield {"type": "response.output_text.delta", "delta": "Hello"}
        yield {"type": "response.output_text.delta", "delta": " world"}
        yield {"type": "response.completed", "finish_reason": "completed"}

    agent._call_llm = mock_stream
    messages = [{"role": "user", "content": "hi"}]
    result = await loop.run(agent, messages, tools=[], stream=True)
    events = [e async for e in result]
    # Events now include lifecycle events (node.started, node.llm_call, node.completed)
    # in addition to LLM delta events
    delta_events = [e for e in events if e.get("type") == "response.output_text.delta"]
    assert [event["delta"] for event in delta_events] == ["Hello world"]
    assistant_msgs = [
        m for m in loop.root_session.chat_history if m.role == "assistant"
    ]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[-1].content == "Hello world"


async def test_ensure_terminal_skipped_when_no_default():
    """run() skips ensure_terminal() when default_terminal_node is None."""
    stub = StubNode("response")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue, default_terminal_node=None)
    original = loop.queue.ensure_terminal
    called = False

    def track_call(*args, **kwargs):
        nonlocal called
        called = True
        return original(*args, **kwargs)

    loop.queue.ensure_terminal = track_call

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={
            "content": "ok",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )

    await loop.run(agent, [{"role": "user", "content": "hi"}], tools=[], stream=False)
    assert not called, (
        "ensure_terminal should not be called when default_terminal_node is None"
    )


async def test_tinycua_loop_ensure_terminal_bootstrap():
    """run() calls ensure_terminal() on queue at bootstrap."""
    terminal_node = ResponseNode()

    loop = TinyCUALoop(default_terminal_node=terminal_node)
    queue = loop.queue

    original_ensure_terminal = queue.ensure_terminal
    ensure_terminal_called = []

    def mock_ensure_terminal(default_terminal_node):
        ensure_terminal_called.append(default_terminal_node)
        return original_ensure_terminal(default_terminal_node)

    queue.ensure_terminal = mock_ensure_terminal

    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={
            "content": "ok",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )
    messages = [{"role": "user", "content": "test"}]

    await loop.run(agent, messages, tools=[], stream=False)

    assert len(ensure_terminal_called) == 1
    assert ensure_terminal_called[0] is terminal_node
