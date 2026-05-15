"""Tool executor and agent executor base."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.llm_client import LLMClient, OpenAICompatibleClient

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.agent.config import AgentConfig
    from tinycua_sdk.security.approval import ApprovalWorkflow
    from tinycua_sdk.tools.decorators import Tool


class ToolExecutor:
    """Static tool execution path with permission and approval checks."""

    @staticmethod
    async def execute(tool: Tool, arguments: dict, agent: Agent) -> Any:
        """Execute a tool with permission and approval checks."""
        permission = agent.tool_permissions.get(tool.name, "allow")

        if permission == "deny":
            return {"error": f"Tool '{tool.name}' is denied by permission map."}

        if permission not in ("allow", "ask"):
            return {
                "error": f"Tool '{tool.name}' has invalid permission '{permission}'. Denying execution."
            }

        if permission == "ask":
            workflows = ToolExecutor._normalize_workflows(agent.approval_workflow)
            if not workflows:
                return {
                    "error": f"Tool '{tool.name}' requires approval but no approval_workflow is configured."
                }
            for workflow in workflows:
                approval = await workflow.request_approval(tool.name, arguments)
                if not approval.get("approved"):
                    return approval

        return tool.invoke(**arguments)

    @staticmethod
    def _normalize_workflows(
        workflow: ApprovalWorkflow | list[ApprovalWorkflow] | None,
    ) -> list[ApprovalWorkflow]:
        if workflow is None:
            return []
        if isinstance(workflow, list):
            return workflow
        return [workflow]


class AgentExecutor:
    """Base executor providing config storage, cancellation, and LLM client."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._cancelled = False
        self._cancel_event = asyncio.Event()
        self._llm_client: LLMClient | None = None

    @property
    def is_cancelled(self) -> bool:
        """Check if execution has been cancelled."""
        return self._cancelled

    def cancel(self) -> None:
        """Cancel current execution."""
        self._cancelled = True
        self._cancel_event.set()

    async def close(self) -> None:
        """Close the LLM client and release resources."""
        if self._llm_client is not None:
            await self._llm_client.close()
            self._llm_client = None

    async def __aenter__(self) -> "AgentExecutor":
        """Enter async context."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context and close resources."""
        await self.close()

    def _get_llm_client(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = OpenAICompatibleClient()
        return self._llm_client

    async def _call_llm(
        self,
        messages: list[dict],
        tools: list[Tool] | None = None,
        stream: bool = False,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """Call the LLM with messages and optional tools.

        Args:
            messages: List of message dicts.
            tools: Optional list of Tool instances.
            stream: When True, return an async iterator of SSE chunk events.

        Returns:
            Normalized response dict or async iterator of event dicts.
        """
        client = self._get_llm_client()
        tool_schemas = [t.to_config() for t in tools] if tools else None
        return await client.chat(
            messages, tool_schemas, self.config.llm_model, stream=stream
        )


__all__ = ["ToolExecutor", "AgentExecutor"]
