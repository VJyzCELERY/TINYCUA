"""Retry prompt framing contracts (FR-004).

Retries must be framed as ``[System: ...]`` directives in ``role:"user"``
messages, using imperative voice, without the old "Correction for the
previous response:" wrapper or the first-person "I need to" -> second-person
"You need to" conversion.
"""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult, ValidationError
from tinycua.loops.node_contract import LifecyclePhase
from tinycua.loops.task_nodes import (
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskExecutorNode,
)
from tinycua.loops.tinycua_loop import TinyCUALoop


def _node(node_id: str):
    """Build a node by id with default config."""
    factories = {
        "task_analyzer": TinyCUATaskAnalyzerNode,
        "task_executor": TinyCUATaskExecutorNode,
        "result_reviewer": TinyCUAResultReviewerNode,
    }
    factory = factories[node_id]
    return factory(node_id=node_id, config=create_node_config(node_id))


def test_retry_prompt_uses_system_prefix() -> None:
    """The retry prompt wrapper prefixes with [System:, not 'Correction...'."""
    loop = TinyCUALoop()

    wrapped = loop._retry_prompt_for_llm("Call task_result_update now.")

    assert wrapped.startswith("[System:")
    assert "Call task_result_update now." in wrapped
    assert "Correction for the previous response" not in wrapped


def test_retry_prompt_no_first_person_conversion() -> None:
    """Directive voice is imperative; no 'I need to' -> 'You need to' flip."""
    loop = TinyCUALoop()

    wrapped = loop._retry_prompt_for_llm("Call terminate to advance the runtime.")

    # The directive is emitted directly, not flipped from first person.
    assert "I need to" not in wrapped
    assert "You need to" not in wrapped


def test_natural_retry_message_is_imperative_directive() -> None:
    """_natural_retry_message builds imperative directives, not 'I need to...'."""
    loop = TinyCUALoop()
    node = _node("task_executor")

    message = loop._natural_retry_message(
        ValidationError("Missing required tool call: task_result_update"),
        node,
        node.config.tool_policy.resolve_tools([]),
    )

    assert "I need to" not in message
    assert "task_result_update" in message


def test_retry_message_for_executor_missing_result_update() -> None:
    """Executor retry guidance names the required tool imperatively."""
    loop = TinyCUALoop()
    node = _node("task_executor")

    message = loop._retry_message_for_validation(
        ValidationError("Missing required tool call: task_result_update"),
        node,
        node.config.tool_policy.resolve_tools([]),
        LLMResult(),
    )

    assert "I need to" not in message
    assert "task_result_update" in message


def test_retry_message_for_terminate_is_directive() -> None:
    """Terminate retry guidance is a [System:]-ready imperative directive."""
    loop = TinyCUALoop()
    node = _node("result_reviewer")
    node.progress.lifecycle_phase = LifecyclePhase.TERMINATE

    message = loop._retry_message_for_validation(
        ValidationError("result_reviewer completed its required work; call terminate."),
        node,
        node.config.tool_policy.resolve_tools([]),
        LLMResult(),
    )

    assert "I need to" not in message
    assert "terminate" in message


def test_messages_with_retry_prompt_emits_system_prefixed_user() -> None:
    """The retry turn is a user-role message with [System: prefix."""
    loop = TinyCUALoop()

    messages = loop._messages_with_retry_prompt(
        [{"role": "system", "content": "sys"}, {"role": "assistant", "content": "hi"}],
        retry_feedback=[],
        retry_message="Call task_result_update now.",
    )

    retry_msg = messages[-1]
    assert retry_msg["role"] == "user"
    assert retry_msg["content"].startswith("[System:")


if __name__ == "__main__":
    # ponytail: self-check
    test_retry_prompt_uses_system_prefix()
    test_retry_prompt_no_first_person_conversion()
    test_natural_retry_message_is_imperative_directive()
    test_retry_message_for_executor_missing_result_update()
    test_retry_message_for_terminate_is_directive()
    test_messages_with_retry_prompt_emits_system_prefixed_user()
    print("ok")
