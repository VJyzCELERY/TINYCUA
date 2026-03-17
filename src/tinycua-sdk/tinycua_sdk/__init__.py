"""tinycua_sdk - TINYCUA AI Agent Development Kit."""

from tinycua_sdk.agent import Agent, AgentConfig, AgentPolicy
from tinycua_sdk.clients.agent_client import AgentClient
from tinycua_sdk.clients.backend import BackendClient
from tinycua_sdk.clients.client import ResponsesClient
from tinycua_sdk.models.request import Message, ResponseRequest, ToolDefinition
from tinycua_sdk.models.response import (
    FunctionCall,
    FunctionCallOutput,
    MessageItem,
    OutputItem,
    Response,
    StreamEvent,
    StreamEventType,
    Usage,
)
from tinycua_sdk.models.result import PlanRunResult, RunResult, ToolCall
from tinycua_sdk.models.task import PlanningResult, TaskPlan, TodoItem
from tinycua_sdk.runner import Runner
from tinycua_sdk.session import Session
from tinycua_sdk.tools.decorators import Tool, tool


async def get_agent(
    agent_id: str,
    backend_url: str,
    backend_api_key: str | None = None,
    backend_headers: dict[str, str] | None = None,
) -> dict:
    """Get agent details from backend by ID.

    Args:
        agent_id: ID of the agent
        backend_url: Backend server URL
        backend_api_key: API key for authentication
        backend_headers: Custom headers for auth and multi-tenancy

    Returns:
        Agent configuration dict from backend

    """
    client = BackendClient(
        base_url=backend_url,
        api_key=backend_api_key,
        headers=backend_headers,
    )
    return await client.get_agent(agent_id)


async def list_agents(
    backend_url: str,
    backend_api_key: str | None = None,
    backend_headers: dict[str, str] | None = None,
) -> list[dict]:
    """List all agents in backend.

    Args:
        backend_url: Backend server URL
        backend_api_key: API key for authentication
        backend_headers: Custom headers for auth and multi-tenancy

    Returns:
        List of agent configuration dicts

    """
    client = BackendClient(
        base_url=backend_url,
        api_key=backend_api_key,
        headers=backend_headers,
    )
    return await client.list_agents()


async def health_check(
    backend_url: str,
) -> bool:
    """Check if backend is healthy.

    Args:
        backend_url: Backend server URL

    Returns:
        True if backend is healthy, False otherwise

    """
    client = BackendClient(base_url=backend_url)
    return await client.health_check()


__all__ = [
    "ResponsesClient",
    "AgentClient",
    "BackendClient",
    "Agent",
    "AgentConfig",
    "AgentPolicy",
    "Tool",
    "tool",
    "Message",
    "ResponseRequest",
    "ToolDefinition",
    "Response",
    "StreamEvent",
    "StreamEventType",
    "Usage",
    "MessageItem",
    "FunctionCall",
    "FunctionCallOutput",
    "OutputItem",
    "Runner",
    "Session",
    "TaskPlan",
    "TodoItem",
    "PlanningResult",
    "RunResult",
    "ToolCall",
    "PlanRunResult",
    "get_agent",
    "list_agents",
    "health_check",
]
