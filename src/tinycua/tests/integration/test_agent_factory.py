"""Integration tests for Agent Factory Contract (Milestone 1.1)."""

import pytest
from tinycua_sdk.agent import Agent, BaseLoop
from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session


def make_mock_call_llm(
    content: str = "Hello",
    stream_events: list[dict] | None = None,
    classification_label: str = "worker",
):
    """Create a mock agent._call_llm matching the actual contract.

    Returns a callable that behaves like the real agent._call_llm():
    - When called with stream=False: returns a dict (via AsyncMock)
    - When called with stream=True: returns an AsyncIterator (async generator)

    The mock tracks call count to support the two-step DecisionNode flow:
    - Odd calls (1st, 3rd, ...) return analysis content
    - Even calls (2nd, 4th, ...) return classification_label

    Note: We must return two separate callables because Python cannot mix
    ``yield`` and ``return`` in the same function body.
    """
    events = stream_events or [
        {"type": "response.output_text.delta", "delta": content},
        {"type": "response.completed", "finish_reason": "completed"},
    ]

    # Non-streaming: async callable that tracks call count for two-step flow
    class _CallLLMNonStream:
        def __init__(self):
            self._call_count = 0

        async def __call__(self, *_args, **_kwargs):
            self._call_count += 1
            if self._call_count % 2 == 0:
                # Classification call (even): return valid label
                return {
                    "content": classification_label,
                    "tool_calls": None,
                    "usage": None,
                    "finish_reason": "completed",
                    "model": None,
                }
            # Analysis call (odd): return content
            return {
                "content": content,
                "tool_calls": None,
                "usage": None,
                "finish_reason": "completed",
                "model": None,
            }

    call_llm_non_stream = _CallLLMNonStream()

    # Streaming: async generator function
    async def call_llm_stream(*_args, **_kwargs):
        for event in events:
            yield event

    class _CallLLMRouter:
        """Routes calls to streaming or non-streaming mock based on stream kwarg."""

        def __init__(self):
            self._non_stream = call_llm_non_stream
            self._stream = call_llm_stream

        def __call__(self, *args, stream=False, **kwargs):
            if stream:
                return self._stream(*args, **kwargs)
            return self._non_stream(*args, **kwargs)

    return _CallLLMRouter()


class TestCreateTinyCUAAgent:
    """Tests for the create_tinycua_agent factory function."""

    def test_factory_returns_agent_with_tinycua_loop(self):
        """Factory returns SDK Agent with TinyCUALoop attached."""
        agent = create_tinycua_agent()
        assert isinstance(agent, Agent)
        assert isinstance(agent.loop, TinyCUALoop)
        assert isinstance(agent.loop, BaseLoop)

    def test_factory_creates_new_session_when_none(self):
        """When no session provided, factory creates a new root session."""
        agent = create_tinycua_agent()
        loop = agent.loop
        assert isinstance(loop.root_session, Session)
        assert loop.root_session.session_id is not None

    def test_factory_uses_provided_session(self):
        """When session is provided, factory uses it."""
        session = Session()
        agent = create_tinycua_agent(session=session)
        assert agent.loop.root_session is session

    def test_factory_applies_session_config(self):
        """Provided SessionConfig is applied to the session."""
        config = SessionConfig(max_context_messages=100)
        agent = create_tinycua_agent(session_config=config)
        assert agent.loop.session_config == config
        assert agent.loop.root_session.session_config == config

    def test_factory_accepts_agent_kwargs(self):
        """Factory passes **agent_kwargs through to SDK Agent."""
        agent = create_tinycua_agent(name="test-agent", instructions="Be helpful")
        assert agent.name == "test-agent"
        assert agent.instructions == "Be helpful"

    def test_tinycua_loop_extends_base_loop(self):
        """TinyCUALoop is a subclass of SDK BaseLoop."""
        session = Session()
        loop = TinyCUALoop(root_session=session)
        assert isinstance(loop, BaseLoop)


class TestAgentRun:
    """Tests for agent.run() through the full factory -> agent -> loop chain."""

    @pytest.mark.asyncio
    async def test_run_returns_string_when_not_streaming(self):
        """agent.run() returns string when stream=False.

        The two-step DecisionNode flow (analysis → classification) produces
        '[Analysis] ... [Classification] ...' output. Using 'passthrough'
        classification avoids spawning extra nodes (unlike 'worker').
        """
        agent = create_tinycua_agent()
        agent._call_llm = make_mock_call_llm(content="Hello", classification_label="passthrough")
        result = await agent.run("hello")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_run_returns_async_iterator_when_streaming(self):
        """agent.run() returns async iterator when stream=True.

        QueryAnalyst uses non-streaming two-step flow (analysis → classification).
        Using 'passthrough' classification avoids spawning extra nodes.
        Only the terminal ResponseNode yields streaming events.
        """
        agent = create_tinycua_agent()
        agent._call_llm = make_mock_call_llm(content="Hi", classification_label="passthrough")
        result = await agent.run("hello", stream=True)
        assert hasattr(result, '__aiter__')
        events = [e async for e in result]
        assert len(events) > 0
        assert events[0]["type"] == "response.output_text.delta"
        assert events[0]["delta"] == "Hi"
        session = agent.loop.root_session
        # QueryAnalyst records classification, ResponseNode yields streaming events
        assert len(session.chat_history) == 2
        assert session.chat_history[0]["role"] == "assistant"
        assert "[Classification]" in session.chat_history[0]["content"]
        assert session.chat_history[1]["role"] == "assistant"
        assert session.input_context[0]["role"] == "user"
        assert session.input_context[0]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_run_populates_session_chat_history(self):
        """agent.run() records assistant responses in session chat history.

        User messages are stored in input_context, not chat_history.
        Uses 'passthrough' classification to avoid spawning extra nodes.
        """
        agent = create_tinycua_agent()
        agent._call_llm = make_mock_call_llm(content="Hello", classification_label="passthrough")
        await agent.run("hello")
        session = agent.loop.root_session
        # Default queue has QueryAnalyst + ResponseNode, both execute and record
        assert len(session.chat_history) == 2
        assert session.chat_history[0]["role"] == "assistant"
        # QueryAnalyst content includes two-step classification output
        assert "[Analysis]" in session.chat_history[0]["content"]
        assert "[Classification]" in session.chat_history[0]["content"]
        assert session.input_context[0]["role"] == "user"
        assert session.input_context[0]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_run_does_not_record_empty_assistant_response(self):
        """Empty assistant responses are not recorded in chat history.

        Note: QueryAnalyst's two-step flow always records a classification
        result ([Analysis] + [Classification]) even when the LLM content
        is empty. The ResponseNode (second node) records nothing when empty.
        Uses 'passthrough' classification to avoid spawning extra nodes.
        """
        agent = create_tinycua_agent()
        agent._call_llm = make_mock_call_llm(content="", classification_label="passthrough")
        await agent.run("hello")
        session = agent.loop.root_session
        # QueryAnalyst always records classification output; ResponseNode skips empty
        assert len(session.chat_history) == 1
        assert "[Classification]" in session.chat_history[0]["content"]
        assert session.input_context[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_run_stream_does_not_record_empty_assistant_response(self):
        """Empty streaming responses are not recorded in chat history.

        Note: QueryAnalyst's two-step flow in streaming mode does NOT yield
        streaming events (classification uses non-streaming agent._call_llm).
        Only the ResponseNode yields streaming events.
        Uses 'passthrough' classification to avoid spawning extra nodes.
        """
        agent = create_tinycua_agent()
        agent._call_llm = make_mock_call_llm(
            content="",
            stream_events=[{"type": "response.completed", "finish_reason": "completed"}],
            classification_label="passthrough",
        )
        result = await agent.run("hello", stream=True)
        events = [e async for e in result]
        # Only ResponseNode yields streaming events (QueryAnalyst uses non-streaming flow)
        assert len(events) == 1
        session = agent.loop.root_session
        # QueryAnalyst records classification; ResponseNode skips empty content
        assert len(session.chat_history) == 1
        assert "[Classification]" in session.chat_history[0]["content"]
        assert session.input_context[0]["role"] == "user"
