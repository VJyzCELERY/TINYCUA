"""Contracts for actionable TinyCUA traceability."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from tinycua_sdk.agent.llm_model import LanguageModel

from tinycua.config.node_config import NodeConfigBase, create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode, TinyCUATaskExecutorNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session
from tinycua.models.task import TaskStateStore, TaskStatus
from tinycua.tools.task_tools import TaskDecomposeTool
from tinycua.tools.task_tools import TaskResultUpdateTool
from tinycua.tools.task_tools import TaskReviewDecisionTool
from tinycua.tools.task_tools import TaskUpdateTool


async def test_streaming_emits_node_prefixed_transcript_events() -> None:
    """Streaming should expose readable [Node] deltas alongside raw events."""
    terminal = ResponseNode(config=NodeConfigBase())
    loop = TinyCUALoop(queue=NodeQueue(items=[terminal]))
    agent = MagicMock()

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        yield {"type": "response.output_text.delta", "delta": "Hello"}
        yield {"type": "response.output_text.delta", "delta": " world"}
        yield {"type": "response.completed", "finish_reason": "completed"}

    agent._call_llm = call_llm

    stream = await loop.run(
        agent,
        [{"role": "user", "content": "Say hello."}],
        tools=[],
        stream=True,
    )
    events = [event async for event in stream]

    transcript_events = [
        event for event in events if event.get("type") == "transcript.delta"
    ]
    assert transcript_events
    assert transcript_events[0]["delta"].startswith("[Response]")
    assert any(
        event["node_label"] == "Response" for event in loop.get_transcript_events()
    )
    assert loop.get_transcript_text().startswith("[USER] Say hello.")
    assert "[Response] Hello world" in loop.get_transcript_text()


def test_task_tree_renderer_shows_execution_order_numbered() -> None:
    """Task trees render as a numbered post-order list in execution order.

    Execution starts at the DFS left-most leaf (``next_unfinished_leaf``), so
    line 1 of the list is the first task worked on; the root is the goal
    header (no status marker), not a numbered work item. Numbering matches
    ``TaskStateStore.task_number_map`` so the agent can select by number.
    """
    store = TaskStateStore()
    root = store.create_task("Build note app")
    backend = store.create_task("Create backend", parent_id=root.task_id)
    store.create_task("Write API", parent_id=backend.task_id)
    store.create_task("Create frontend", parent_id=root.task_id)
    store.transition(root.task_id, TaskStatus.IN_PROGRESS)

    rendered = TinyCUALoop().render_task_tree(store)

    # Root is the goal header, no status marker on it.
    assert "Root (goal): Build note app" in rendered
    # Post-order: Write API (left-most leaf) first, root last in the list.
    assert rendered.index("Write API") < rendered.index("Create backend")
    assert rendered.index("Create backend") < rendered.index("Create frontend")
    assert "Build note app" not in rendered.split("Task list")[1]  # root not in list
    # Numbered rows.
    assert "1. Task [pending] Write API" in rendered
    assert "2. Task [pending] Create backend" in rendered
    assert "3. Task [pending] Create frontend" in rendered


def test_llm_messages_dedupe_original_query_for_digester() -> None:
    """Digester receives one assistant handoff, not duplicate user queries."""
    user_message = {
        "role": "user",
        "content": "Please create a small note app in the workspace.",
    }
    digester = TinyCUAInformationDigesterNode(
        node_id="digester",
        config=create_node_config("information_digester"),
    )
    queue = NodeQueue(items=[digester])
    queue.set_input(
        digester,
        NodeInput(
            input_type="original_user_query",
            source_node="query_analyst",
            target_node="digester",
            messages=[dict(user_message)],
        ),
    )
    loop = TinyCUALoop(queue=queue)
    loop.root_session.input_context = [dict(user_message)]
    digester.ensure_session(loop.root_session)

    messages = loop._build_node_messages(digester)

    user_messages = [message for message in messages if message.get("role") == "user"]
    assistant_handoffs = [
        message
        for message in messages
        if message.get("role") == "assistant"
        and message.get("content") == user_message["content"]
    ]
    assert user_messages == []
    assert assistant_handoffs == [
        {"role": "assistant", "content": user_message["content"]}
    ]


def test_nonterminal_planner_prose_is_not_replayed_in_transcript() -> None:
    """Planner/refusal dumps from worker internals should not flood notebooks."""
    loop = TinyCUALoop()
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer"),
    )
    content = (
        "I cannot create files in a physical workspace or execute commands on "
        "your system. However, here is a project structure.\n```\napp.py\n```"
    )

    loop._record_node_content_transcript(node, content)

    assert loop.get_transcript_events() == []


def test_task_analyzer_ignores_project_tree_code_dump_titles() -> None:
    """Task analyzer must not infer task state from project-tree prose."""
    session = Session()
    root = session.task_store.create_task("Create note scheduler app")
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer"),
    )
    node.ensure_session(session)

    titles = [session.task_store.tasks[task_id].title for task_id in root.children]
    assert titles == []
    assert not hasattr(node, "parse_loop_result")
    assert {tool.name for tool in node.config.tool_policy.node_tools} >= {
        "task_inspect",
        "task_decompose",
    }


def test_default_agent_exposes_workspace_action_and_web_search_tools(
    tmp_path: Path,
) -> None:
    """TinyCUA agents should be actionable by default, not planner-only."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))

    tool_names = {tool.name for tool in agent.tools}

    assert {
        "write_file",
        "read_file",
        "run_shell",
        "run_python",
        "web_search",
    } <= tool_names


def test_task_executor_instruction_requires_real_tool_actions(tmp_path: Path) -> None:
    """TaskExecutor prompts must require action, not planner-only prose."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(agent.loop.root_session)
    _, tools = agent.loop._prepare_node(node, agent.tools, None)
    instruction = node.build_instruction()

    assert {"write_file", "run_shell", "run_python", "web_search"} <= {
        tool.name for tool in tools
    }
    assert "MUST use tools" in instruction
    assert "task_result_update" in instruction


def test_task_node_prompts_are_action_first_not_phase_essays() -> None:
    """Worker node prompts should call tools, not invite essay answers."""
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer"),
    )
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )

    prompts = [
        analyzer.build_instruction(),
        analyzer.build_continuation(),
        executor.build_instruction(),
        executor.build_continuation(),
        reviewer.build_instruction(),
        reviewer.build_continuation(),
    ]

    assert all(len(prompt) < 500 for prompt in prompts)
    combined = "\n".join(prompts)
    assert "Phase 1" not in combined
    assert "four phases" not in combined
    assert "Do not write a plan" in combined
    assert "Do not describe what you will do" in combined
    assert "Do not write a long explanation" in combined


def test_task_tool_descriptions_are_brief_but_specific() -> None:
    """Task tool schemas should be clear without prompt-noise essays."""
    tools = [
        TaskUpdateTool(),
        TaskDecomposeTool(),
        TaskResultUpdateTool(),
        TaskReviewDecisionTool(),
    ]
    descriptions = {tool.name: tool.description for tool in tools}

    assert all(len(description) < 220 for description in descriptions.values())
    assert "unfinished" in descriptions["task_update"]
    assert "planning" in descriptions["task_update"]
    assert "sequential subtasks" in descriptions["task_decompose"]
    assert "outcome" in descriptions["task_result_update"]
    assert "approved" in descriptions["task_review_decision"]


async def test_task_executor_validates_tool_owned_result_update(tmp_path: Path) -> None:
    """TaskExecutor validates tool use without forcing model tool choice."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(
        llm_model=model,
        session_config=SessionConfig(workspace_dir=tmp_path),
    )
    agent.loop.root_session.task_store.create_task("Create app.py")
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(agent.loop.root_session)
    messages, tools = agent.loop._prepare_node(node, agent.tools, None)
    captured_tool_choices = []
    captured_tool_names = []

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        captured_tool_choices.append(agent.config.llm_model.tool_choice)
        captured_tool_names.append([tool.name for tool in tools])
        if len(captured_tool_choices) == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_write_file",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": '{"path":"app.py","content":"print(\\"ok\\")"}',
                        },
                    }
                ],
            }
        if len(captured_tool_choices) == 2:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_result_update",
                        "type": "function",
                        "function": {
                            "name": "task_result_update",
                            "arguments": '{"content":"Created app.py","success":true}',
                        },
                    }
                ],
            }
        if len(captured_tool_choices) == 3:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_terminate",
                        "type": "function",
                        "function": {"name": "terminate", "arguments": "{}"},
                    }
                ],
            }
        return {"content": "Created app.py", "tool_calls": []}

    agent._call_llm = call_llm  # type: ignore[method-assign]

    result, _, validation = await agent.loop._call_node_with_retry(
        node,
        agent,
        messages,
        tools,
    )

    assert validation.is_valid
    assert result.content == "Created app.py"
    assert (tmp_path / "app.py").read_text() == 'print("ok")'
    assert captured_tool_choices == [None, None, "required"]
    assert "write_file" in captured_tool_names[0]
    assert "run_shell" in captured_tool_names[0]
    assert "task_execute" not in captured_tool_names[0]
    assert captured_tool_names[2] == ["terminate"]


async def test_task_executor_executes_continued_tool_calls(tmp_path: Path) -> None:
    """Tool feedback continuations should execute follow-up file writes."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(
        llm_model=model,
        session_config=SessionConfig(workspace_dir=tmp_path),
    )
    agent.loop.root_session.task_store.create_task("Create backend.py")
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(agent.loop.root_session)
    messages, tools = agent.loop._prepare_node(node, agent.tools, None)
    responses = [
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "call_list_files",
                    "type": "function",
                    "function": {"name": "list_files", "arguments": "{}"},
                }
            ],
        },
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "call_write_file",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path":"backend.py","content":"print(\\"ok\\")"}',
                    },
                }
            ],
        },
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "call_result_update",
                    "type": "function",
                    "function": {
                        "name": "task_result_update",
                        "arguments": '{"content":"Created backend.py","success":true}',
                    },
                }
            ],
        },
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "call_terminate",
                    "type": "function",
                    "function": {"name": "terminate", "arguments": "{}"},
                }
            ],
        },
    ]

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        return responses.pop(0)

    agent._call_llm = call_llm  # type: ignore[method-assign]

    result, _, validation = await agent.loop._call_node_with_retry(
        node,
        agent,
        messages,
        tools,
    )

    assert validation.is_valid
    assert result.content == "Created backend.py"
    assert (tmp_path / "backend.py").read_text() == 'print("ok")'
    assert [item["name"] for item in result.metadata["tool_results"]] == [
        "list_files",
        "write_file",
        "task_result_update",
        "terminate",
    ]


async def test_executor_env_check_success_is_left_for_reviewer(tmp_path: Path) -> None:
    """Executor may record weak success; reviewer owns the quality gate."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(
        llm_model=model,
        session_config=SessionConfig(workspace_dir=tmp_path),
    )
    task = agent.loop.root_session.task_store.create_task("Build app")
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(agent.loop.root_session)
    messages, tools = agent.loop._prepare_node(node, agent.tools, None)
    responses = [
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "call_env",
                    "type": "function",
                    "function": {
                        "name": "run_python",
                        "arguments": '{"code":"import sys; print(sys.version)"}',
                    },
                }
            ],
        },
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "call_update",
                    "type": "function",
                    "function": {
                        "name": "task_result_update",
                        "arguments": '{"content":"Python works","success":true}',
                    },
                }
            ],
        },
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "call_terminate",
                    "type": "function",
                    "function": {"name": "terminate", "arguments": "{}"},
                }
            ],
        },
    ]

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        return responses.pop(0)

    agent._call_llm = call_llm  # type: ignore[method-assign]

    result, _, validation = await agent.loop._call_node_with_retry(
        node,
        agent,
        messages,
        tools,
    )

    assert validation.is_valid
    assert result.content == "Python works"
    assert task.result is not None
    assert task.result.success is True
    assert not list(tmp_path.glob("*.py"))


async def test_task_executor_rejects_planner_only_without_scaffold_fallback(
    tmp_path: Path,
) -> None:
    """Planner-only executor output must fail visibly instead of scaffolding."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(
        llm_model=model,
        session_config=SessionConfig(workspace_dir=tmp_path),
    )
    agent.loop.root_session.input_context = [
        {
            "role": "user",
            "content": "Create a note taking app with a scheduler in the workspace.",
        }
    ]
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(agent.loop.root_session)
    messages, tools = agent.loop._prepare_node(node, agent.tools, None)

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        return {"content": "Here is a plan for the app.", "tool_calls": []}

    agent._call_llm = call_llm  # type: ignore[method-assign]

    result, _, validation = await agent.loop._call_node_with_retry(
        node,
        agent,
        messages,
        tools,
    )

    assert not validation.is_valid
    assert not (tmp_path / "backend.py").exists()
    assert not (tmp_path / "webapp" / "index.html").exists()
    assert not (tmp_path / "scheduler.py").exists()
    assert "Created workspace scaffold" not in result.content
    assert "tool_results" not in result.metadata


def test_transcript_events_suppress_internal_repr_noise() -> None:
    """Transcript output should not surface dataclass repr echoes to users."""
    loop = TinyCUALoop()

    event = loop._record_transcript_event(
        "transcript.node",
        "Worker",
        "Useful update\nDigestedInformation(context_summary='secret echo')\nAggregatedResult(root_task_id='x')",
        node_id="worker",
    )

    assert "Useful update" in event["content"]
    assert "DigestedInformation(" not in event["content"]
    assert "AggregatedResult(" not in event["content"]


def test_transcript_sanitizer_preserves_user_code_lines() -> None:
    """Sanitization should not delete arbitrary function-call code examples."""
    loop = TinyCUALoop()

    event = loop._record_transcript_event(
        "transcript.node",
        "Response",
        "Run this function:\nmain()\ntask_init()",
        node_id="response",
    )

    assert "main()" in event["content"]
    assert "task_init()" not in event["content"]


async def test_reusing_session_preserves_in_memory_context(tmp_path: Path) -> None:
    """A provided Session can continue across agent instances/runs in memory."""
    from tinycua.models.session import Session

    session = Session()
    config = SessionConfig(workspace_dir=tmp_path)
    first = create_tinycua_agent(session=session, session_config=config)
    second = create_tinycua_agent(session=session, session_config=config)

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        tool_names = {tool.name for tool in tools}
        if "select_query_route" in tool_names:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "select_query_route",
                            "arguments": '{"route":"passthrough"}',
                        },
                    }
                ],
            }
        return {"content": "remembered", "tool_calls": []}

    first._call_llm = call_llm  # type: ignore[method-assign]
    second._call_llm = call_llm  # type: ignore[method-assign]

    await first.run("Remember this session.")
    session.todo.append({"content": "continue work", "status": "pending"})
    task = session.task_store.create_task("Continue app")
    session.task_store.transition(task.task_id, "in_progress")
    session.task_store.transition(task.task_id, "completed")
    await second.run("Continue.")

    assert second.loop.root_session is session
    assert session.todo == [{"content": "continue work", "status": "pending"}]
    assert session.task_store.root_task_id is not None
    assert session.input_context[-1]["content"] == "Continue."
