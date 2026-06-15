"""LLM message contract guardrails."""

from __future__ import annotations

from tinycua.config.node_config import NodeMessagePolicy, create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.node import DecisionNode
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.chat_record import ChatRecord
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session_context_entry import SessionContextEntry
from tinycua.models.task import AggregatedResult, TaskResult


def test_build_node_messages_filters_blank_messages_and_preserves_roles() -> None:
    """LLM payloads contain no blank message content and keep assistant history."""
    loop = TinyCUALoop()
    node = ResponseNode(config=create_node_config("response"))
    node.config.message_policy = NodeMessagePolicy(include_chat_history=True)
    node.ensure_session(loop.root_session)
    loop.root_session.input_context = [
        {"role": "user", "content": "\n\n"},
        {"role": "user", "content": "Summarize this."},
    ]
    loop.root_session.chat_history.append(ChatRecord(role="assistant", content="Prior answer"))
    loop.root_session.session_context.append(
        SessionContextEntry(content="", segment="output", source_node_id="x")
    )

    messages = loop._build_node_messages(node)

    assert all(str(message.get("content", "")).strip() for message in messages)
    assert {message["role"] for message in messages} >= {"assistant", "user"}
    assert any(message["role"] == "assistant" and message["content"] == "Prior answer" for message in messages)


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
        message["role"] == "user"
        and message["content"] == "Worker internal analysis"
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


def test_structured_internal_context_is_rendered_as_json_not_python_repr() -> None:
    """Known internal payloads are compact JSON before reaching the LLM."""
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
    assert '"type":"DigestedInformation"' in rendered_context
    assert '"type":"AggregatedResult"' in rendered_context


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
