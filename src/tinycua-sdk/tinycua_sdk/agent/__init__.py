"""Agent package."""

from tinycua_sdk.agent.agent import Agent
from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.events import (
    AssistantMessage,
    ContentDeltaEvent,
    ContentDoneEvent,
    LLMEvent,
    LLMMessage,
    LLMResponse,
    LLMToolSpec,
    RawSseEvent,
    ReasoningDeltaEvent,
    ReasoningDoneEvent,
    ResponseCompletedEvent,
    ResponseFailedEvent,
    ResponseUsageEvent,
    SystemMessage,
    TokenUsage,
    ToolCallArgumentsDeltaEvent,
    ToolCallArgumentsDoneEvent,
    ToolCallReadyEvent,
    ToolCallStartedEvent,
    ToolResultMessage,
    UserMessage,
)
from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.agent.llm_client import LLMClient, OpenAIResponsesClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.agent.loop import BaseLoop

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentPolicy",
    "AgentExecutor",
    "BaseLoop",
    "LanguageModel",
    "LLMClient",
    "OpenAIResponsesClient",
    # Canonical SSE Events
    "ContentDeltaEvent",
    "ContentDoneEvent",
    "ReasoningDeltaEvent",
    "ReasoningDoneEvent",
    "ToolCallStartedEvent",
    "ToolCallArgumentsDeltaEvent",
    "ToolCallArgumentsDoneEvent",
    "ToolCallReadyEvent",
    "TokenUsage",
    "ResponseUsageEvent",
    "ResponseCompletedEvent",
    "ResponseFailedEvent",
    # Union type
    "LLMEvent",
    # Non-streaming response
    "LLMResponse",
    # Raw SSE event
    "RawSseEvent",
    # Canonical Input Types
    "SystemMessage",
    "UserMessage",
    "AssistantMessage",
    "ToolResultMessage",
    "LLMMessage",
    "LLMToolSpec",
]
