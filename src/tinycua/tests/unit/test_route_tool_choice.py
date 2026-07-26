"""Route tool-choice reliability contracts."""

from __future__ import annotations

from tinycua_sdk.agent.llm_model import LanguageModel

from tinycua.config.node_config import create_node_config
from tinycua.factory import create_tinycua_agent
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode
from tinycua.loops.task_nodes import TinyCUATaskAssessorNode
from tinycua.loops.task_nodes import TinyCUATaskExecutorNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.worker import TinyCUAWorkerNode


def _route_tool_call(name: str, route: str) -> dict:
    return {
        "id": f"call_{name}",
        "type": "function",
        "function": {"name": name, "arguments": f'{{"route": "{route}"}}'},
    }


async def test_query_analyst_requires_route_tool_for_local_chat_completions() -> None:
    """Local Chat Completions models get string required route choice."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(llm_model=model)
    captured_tool_choices = []
    captured_tool_names = []

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        captured_tool_choices.append(agent.config.llm_model.tool_choice)
        captured_tool_names.append([tool.name for tool in tools])
        forced_name = "select_query_route"
        if any(tool.name == forced_name for tool in tools):
            return {"content": "", "tool_calls": [_route_tool_call(forced_name, "passthrough")]}
        return {"content": "final answer", "tool_calls": []}

    agent._call_llm = call_llm  # type: ignore[method-assign]

    await agent.run("Hello there.")

    assert captured_tool_choices[0] == "required"
    assert captured_tool_names[0] == ["select_query_route"]
    assert agent.config.llm_model.tool_choice is None


async def test_worker_requires_route_tool_for_local_chat_completions() -> None:
    """WorkerNode uses local-compatible required string route choice."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(llm_model=model)
    loop = TinyCUALoop()
    worker = TinyCUAWorkerNode(
        node_id="worker",
        config=create_node_config("worker"),
    )
    worker.ensure_session(loop.root_session)
    messages, tools = loop._prepare_node(worker, [], None)
    captured_tool_choices = []
    captured_tool_names = []

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        captured_tool_choices.append(agent.config.llm_model.tool_choice)
        captured_tool_names.append([tool.name for tool in tools])
        return {
            "content": "",
            "tool_calls": [_route_tool_call("select_worker_route", "task_creation")],
        }

    agent._call_llm = call_llm  # type: ignore[method-assign]

    result, _, validation = await loop._call_node_with_retry(
        worker,
        agent,
        messages,
        tools,
    )

    assert validation.is_valid
    assert result.tool_calls[0]["function"]["name"] == "select_worker_route"
    assert captured_tool_choices == ["required"]
    assert captured_tool_names[0] == ["select_worker_route"]
    assert agent.config.llm_model.tool_choice is None


def test_all_chat_completions_use_required_string_tool_choice() -> None:
    """All Chat Completions providers get "required" — the tool list is already narrowed."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="gpt-test",
        base_url="https://api.openai.com/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(llm_model=model)
    loop = TinyCUALoop()
    worker = TinyCUAWorkerNode(
        node_id="worker",
        config=create_node_config("worker"),
    )
    worker.ensure_session(loop.root_session)
    _, tools = loop._prepare_node(worker, [], None)

    tool_choice = loop._forced_tool_choice_for_node(agent, worker, tools)

    assert tool_choice == "required"


def test_task_assessor_uses_read_only_decision_tools_without_task_update() -> None:
    """TaskAssessor narrows to inspection and its dedicated decision tool."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(llm_model=model)
    loop = TinyCUALoop()
    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor"),
    )
    assessor.ensure_session(loop.root_session)
    _, tools = loop._prepare_node(assessor, [], None)

    tool_choice = loop._forced_tool_choice_for_node(agent, assessor, tools)
    narrowed_tools = loop._llm_tools_for_required_choice(
        assessor,
        tools,
        force_required_tool=True,
    )

    assert tool_choice is None
    assert [tool.name for tool in narrowed_tools] == [
        "task_inspect",
        "task_assessment_decision",
    ]


def test_result_reviewer_is_not_provider_forced() -> None:
    """Reviewer can inspect/decide naturally; runtime validates the result."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(llm_model=model)
    loop = TinyCUALoop()
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    reviewer.ensure_session(loop.root_session)
    _, tools = loop._prepare_node(reviewer, [], None)

    tool_choice = loop._forced_tool_choice_for_node(agent, reviewer, tools)
    llm_tools = loop._llm_tools_for_required_choice(
        reviewer,
        tools,
        force_required_tool=True,
    )

    assert tool_choice is None
    assert {tool.name for tool in llm_tools} >= {"task_inspect", "task_review_decision"}


def test_task_executor_does_not_force_provider_tool_choice() -> None:
    """Executor runs as a normal ReAct agent, not a forced-tool node."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(llm_model=model)
    loop = TinyCUALoop()
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    executor.ensure_session(loop.root_session)
    _, tools = loop._prepare_node(executor, agent.tools, None)

    tool_choice = loop._forced_tool_choice_for_node(agent, executor, tools)

    assert tool_choice is None


def test_result_reviewer_retry_keeps_inspection_tools() -> None:
    """Reviewer retry keeps read-only evidence tools available."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(llm_model=model)
    loop = TinyCUALoop()
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    reviewer.ensure_session(loop.root_session)
    _, tools = loop._prepare_node(reviewer, agent.tools, None)

    retry_tools = loop._tools_for_retry_attempt(
        reviewer,
        tools,
        "I need to call task_review_decision with the current evidence.",
    )

    assert {tool.name for tool in retry_tools} >= {"read_file", "list_files", "task_review_decision"}


def test_task_analyzer_retry_keeps_update_and_decompose_tools() -> None:
    """Analyzer retry keeps both valid task-state choices available."""
    loop = TinyCUALoop()
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer"),
    )
    analyzer.ensure_session(loop.root_session)
    _, tools = loop._prepare_node(analyzer, [], None)
    retry_message = loop._natural_retry_message(
        ValueError(
            "task_analyzer must call at least one successful task-state tool "
            "from ['task_decompose', 'task_update']"
        ),
        analyzer,
        tools,
    )

    retry_tools = loop._tools_for_retry_attempt(analyzer, tools, retry_message)

    assert "task_decompose" in retry_message
    retry_tool_names = {tool.name for tool in retry_tools}
    assert {"task_update", "task_decompose"}.issubset(retry_tool_names)


def test_task_executor_keeps_react_tools_without_provider_force() -> None:
    """Executor keeps tools available without provider-level forced choice."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(llm_model=model)
    loop = TinyCUALoop()
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    executor.ensure_session(loop.root_session)
    _, tools = loop._prepare_node(executor, [], None)

    tool_choice = loop._forced_tool_choice_for_node(agent, executor, tools)
    llm_tools = loop._llm_tools_for_required_choice(
        executor,
        tools,
        force_required_tool=True,
    )

    assert tool_choice is None
    assert "task_result_update" in {tool.name for tool in llm_tools}
    assert "task_execute" not in {tool.name for tool in llm_tools}


async def test_route_tool_failure_retries_then_fails_closed() -> None:
    """Route nodes retry required tool calls and then fail closed."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )
    agent = create_tinycua_agent(llm_model=model)
    loop = TinyCUALoop()
    query = TinyCUAQueryAnalystNode(
        node_id="query_analyst",
        config=create_node_config("query_analyst"),
    )
    query.ensure_session(loop.root_session)
    loop.root_session.input_context = [{"role": "user", "content": "hello"}]
    messages, tools = loop._prepare_node(query, [], None)
    captured_messages = []

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        captured_messages.append(list(messages))
        return {"content": "passthrough", "tool_calls": []}

    agent._call_llm = call_llm  # type: ignore[method-assign]

    result, attempt, validation = await loop._call_node_with_retry(
        query,
        agent,
        messages,
        tools,
    )

    assert attempt == 3
    assert not validation.is_valid
    assert result.content == "passthrough"
    assert len(captured_messages) == 3
    # FR-004: retry is a [System: ...] directive naming the required tool.
    assert "Call select_query_route" in "\n".join(
        message.get("content", "") for message in captured_messages[-1]
    )
    retry_counts = [
        sum(
            "Call select_query_route" in str(message.get("content", ""))
            for message in call_messages
        )
        for call_messages in captured_messages
    ]
    assert retry_counts == [0, 1, 1]
    assert captured_messages[-1][-1]["role"] == "user"
    assert not captured_messages[-1][-1]["content"].startswith("Runtime validation:")
