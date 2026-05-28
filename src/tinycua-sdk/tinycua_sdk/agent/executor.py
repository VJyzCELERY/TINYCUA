"""Tool executor and agent executor base."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, cast

from tinycua_sdk.agent.llm_client import LLMClient
from tinycua_sdk.providers.registry import ProviderRegistry, get_provider_registry

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.agent.config import AgentConfig
    from tinycua_sdk.agent.events import LLMEvent, LLMMessage, LLMResponse, LLMToolSpec
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

    def __init__(self, config: AgentConfig, registry: ProviderRegistry | None = None) -> None:
        self.config = config
        self._registry = registry
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
            import os

            from tinycua_sdk.providers.constants import (
                OPENAI_BASE_URL,
            )
            from tinycua_sdk.providers.upload import UploadSession  # noqa: PLC0415
            from tinycua_sdk.providers.utility import normalize_base_url

            registry = self._registry or get_provider_registry()

            # Resolve base URL for cache scoping using the same
            # resolution order as the provider clients.
            model = self.config.llm_model
            base_url = model.base_url
            if not base_url:
                provider_caps = model.provider.upper().replace("-", "_")
                env_key = f"{provider_caps}_BASE_URL"
                base_url = (
                    os.environ.get(env_key)
                    or os.environ.get("LLM_BASE_URL")
                    or OPENAI_BASE_URL
                )
            base_url = normalize_base_url(base_url)

            # Build UploadSession with optional persistent cache
            upload_session = UploadSession(
                provider=model.provider,
                base_url=base_url,
                cache_dir=self.config.cache_dir,
                cache_max_entries=self.config.cache_max_entries,
                session_cache_max_entries=self.config.session_cache_max_entries,
                cache_namespace=self.config.cache_namespace,
                upload_timeout=self.config.upload_timeout,
            )

            self._llm_client = registry.create_client(
                self.config.llm_model,
                upload_session=upload_session,
            )
        return self._llm_client

    async def _call_llm(
        self,
        messages: list[LLMMessage],
        tools: list[Tool] | None = None,
        stream: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMEvent]:
        """Call the LLM with messages and optional tools.

        Configuration is bound at client construction via
        ``self.config.llm_model`` — different configurations require
        creating a new client through the registry.

        Args:
            messages: Canonical message list.
            tools: Optional list of Tool instances.
            stream: When True, return an async iterator of canonical stream events.

        Returns:
            ``LLMResponse`` when stream=False, or ``AsyncIterator[LLMEvent]``
            when streaming.
        """
        client = self._get_llm_client()
        tool_schemas: list[LLMToolSpec] | None = cast(
            "list[LLMToolSpec] | None",
            [t.to_config() for t in tools] if tools else None,
        )
        return cast(
            "LLMResponse | AsyncIterator[LLMEvent]",
            await client.chat(messages, tool_schemas, stream=stream),
        )


__all__ = ["ToolExecutor", "AgentExecutor"]
