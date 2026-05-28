"""Integration tests for tool-result file attachment handoff."""

import asyncio

import pytest

from tinycua_sdk import ContentPart, FileAttachment
from tinycua_sdk.agent.loop import BaseLoop


class _RecordingAgent:
    """Minimal agent double that records second-turn messages."""

    instructions = "Use tools when needed."
    skills = []

    def __init__(self, first_response, second_response):
        from collections import deque
        from types import SimpleNamespace

        self.policy = SimpleNamespace(max_tool_calls=5)
        self.is_cancelled = False
        self._cancel_event = asyncio.Event()
        self.calls = []
        self._responses = deque([first_response, second_response])
        self.tool_permissions = {}

    async def _call_llm(self, messages, tools, stream=False):
        self.calls.append(messages)
        try:
            response = self._responses.popleft()
        except IndexError:
            raise AssertionError(
                f"Unexpected LLM call #{len(self.calls)}: no response configured"
            )
        if stream:
            async def _gen():
                for tc in response.get("tool_calls", []):
                    yield {
                        "type": "tool_call.ready",
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "arguments": tc.get("arguments", "{}"),
                    }
                if response.get("content"):
                    yield {
                        "type": "response.output_text.delta",
                        "delta": response["content"],
                    }
                yield {
                    "type": "response.completed",
                    "finish_reason": (
                        "tool_calls" if response.get("tool_calls") else "stop"
                    ),
                    "response": {
                        "usage": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                        }
                    },
                }
            return _gen()
        return response


class _Tool:
    name = "make_image"
    description = "Generate an image."
    parameters = {"type": "object", "properties": {}}

    def invoke(self, **kwargs):
        attachment = FileAttachment.from_bytes(
            b"fake-png-bytes",
            mime_type="image/png",
            filename="generated.png",
        )
        return {
            "content": [
                ContentPart(type="text", text="Generated image."),
                ContentPart(type="file", file=attachment),
            ]
        }


class _AttachmentTool(_Tool):
    def invoke(self, **kwargs):
        attachment = FileAttachment.from_bytes(
            b"fake-png-bytes",
            mime_type="image/png",
            filename="generated.png",
        )
        return {"content": "Generated image.", "attachments": [attachment]}


@pytest.mark.asyncio
async def test_non_streaming_tool_result_file_reaches_second_llm_turn():
    """Non-streaming tool-generated file handoff reaches the second LLM turn."""
    agent = _RecordingAgent(
        first_response={
            "content": "",
            "tool_calls": [
                {"id": "call_1", "name": "make_image", "arguments": "{}"}
            ],
        },
        second_response={"content": "The image is visible."},
    )

    result = await BaseLoop(max_iterations=2).run(agent, [], [_Tool()])

    assert result == "The image is visible."
    second_turn = agent.calls[1]
    tool_result = next(
        msg for msg in second_turn if msg["role"] == "tool_result"
    )
    assert tool_result["call_id"] == "call_1"
    assert isinstance(tool_result["content"], list)
    assert tool_result["content"][1].type == "file"


@pytest.mark.asyncio
async def test_non_streaming_tool_result_attachments_shape_reaches_second_llm_turn():
    """Non-streaming tool-result attachments shape reaches second LLM turn."""
    agent = _RecordingAgent(
        first_response={
            "content": "",
            "tool_calls": [
                {"id": "call_1", "name": "make_image", "arguments": "{}"}
            ],
        },
        second_response={"content": "The image is visible."},
    )

    await BaseLoop(max_iterations=2).run(agent, [], [_AttachmentTool()])

    second_turn = agent.calls[1]
    tool_result = next(
        msg for msg in second_turn if msg["role"] == "tool_result"
    )
    assert tool_result["content"] == "Generated image."
    assert len(tool_result["attachments"]) == 1
    assert (
        tool_result["attachments"][0].filename == "generated.png"
    )


@pytest.mark.asyncio
async def test_streaming_tool_result_file_reaches_second_llm_turn():
    """Streaming tool-generated file handoff reaches second LLM turn."""
    agent = _RecordingAgent(
        first_response={
            "content": "",
            "tool_calls": [
                {"id": "call_1", "name": "make_image", "arguments": "{}"}
            ],
        },
        second_response={"content": "The image is visible."},
    )

    stream_result = await BaseLoop(max_iterations=2).run(
        agent, [], [_Tool()], stream=True,
    )
    async for _ in stream_result:
        pass  # consume stream — assertions target agent.calls below

    second_turn = agent.calls[1]
    tool_result = next(
        msg for msg in second_turn if msg["role"] == "tool_result"
    )
    assert tool_result["call_id"] == "call_1"
    assert isinstance(tool_result["content"], list)
    assert tool_result["content"][1].type == "file"
