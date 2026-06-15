"""Route tool-choice reliability contracts."""

from __future__ import annotations

from tinycua_sdk.agent.llm_model import LanguageModel

from tinycua.config.node_config import create_node_config
from tinycua.factory import create_tinycua_agent
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.worker import TinyCUAWorkerNode


def _route_tool_call(name: str, route: str) -> dict:
    return {
        "id": f"call_{name}",
        "type": "function",
        "function": {"name": name, "arguments": f'{{"route": "{route}"}}'},
    }


async def test_query_analyst_forces_route_tool_choice_for_chat_completions() -> None:
    """QueryAnalyst must force its required route tool, not rely on auto tools."""
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


async def test_worker_forces_route_tool_choice_for_chat_completions() -> None:
    """WorkerNode must force select_worker_route for route decisions."""
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
    assert captured_tool_names == [["select_worker_route"]]
    assert agent.config.llm_model.tool_choice is None


def test_remote_chat_completions_uses_openai_function_tool_choice_shape() -> None:
    """Non-local Chat Completions providers get the OpenAI object form."""
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

    assert tool_choice == {
        "type": "function",
        "function": {"name": "select_worker_route"},
    }


async def test_route_tool_failure_does_not_retry_with_text_continuations() -> None:
    """Route nodes fail over after one bad response instead of teaching retry spam."""
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

    assert attempt == 1
    assert not validation.is_valid
    assert result.content == "passthrough"
    assert len(captured_messages) == 1
    assert "Retry attempt" not in "\n".join(
        message.get("content", "") for message in captured_messages[0]
    )
