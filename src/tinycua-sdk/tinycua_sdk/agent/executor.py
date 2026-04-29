"""Agent execution capabilities: run, stream, cancel."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Union

from tinycua_sdk.agent.definition import AgentDefinition
from tinycua_sdk.core.config import SDKConfig

if TYPE_CHECKING:
    from tinycua_sdk.models.response import StreamEvent
    from tinycua_sdk.agent.loop import DefaultLoop
    from tinycua_sdk.tools.decorators import Tool
    from tinycua_sdk.agent.agent import Agent


_security_logger = logging.getLogger("tinycua_sdk.security")

import uuid


class ToolExecutor:
    """Executor with proper error handling for tool execution.

    Provides standardized error handling by returning dicts with
    success/error status instead of raising exceptions.
    """

    def __init__(self, registry=None):
        """Initialize ToolExecutor.

        Args:
            registry: Optional tool registry for tool lookup.
        """
        self.registry = registry

    def execute(self, tool_name: str, tool: Any, arguments: dict | None = None) -> dict:
        """Execute tool with error handling.

        Args:
            tool_name: Name of the tool to execute.
            tool: The Tool instance to execute.
            arguments: Arguments to pass to the tool.

        Returns:
            Dict with success status and result/error.
        """
        arguments = arguments or {}

        try:
            result = tool.invoke(**arguments)

            return {
                "success": True,
                "result": result,
                "tool_name": tool_name,
            }

        except asyncio.TimeoutError as e:
            _security_logger.error("Tool execution timeout: %s", tool_name)
            return {
                "success": False,
                "error": f"Tool '{tool_name}' timed out",
                "tool_name": tool_name,
            }

        except (ValueError, TypeError, RuntimeError, OSError, AttributeError) as e:
            ref_id = str(uuid.uuid4())
            _security_logger.error(
                "Tool execution error (ref_id=%s): %s: %s",
                ref_id,
                tool_name,
                e,
                exc_info=True,
            )
            return {
                "success": False,
                "error": "Tool execution failed",
                "tool_name": tool_name,
                "ref_id": ref_id,
            }

    async def execute_async(
        self, tool_name: str, tool: Any, arguments: dict | None = None
    ) -> dict:
        """Execute tool asynchronously with error handling.

        Args:
            tool_name: Name of the tool to execute.
            tool: The Tool instance to execute.
            arguments: Arguments to pass to the tool.

        Returns:
            Dict with success status and result/error.
        """
        arguments = arguments or {}

        try:
            result = tool.invoke(**arguments)
            if asyncio.iscoroutine(result):
                result = await result

            return {
                "success": True,
                "result": result,
                "tool_name": tool_name,
            }

        except asyncio.TimeoutError as e:
            _security_logger.error("Tool execution timeout: %s", tool_name)
            return {
                "success": False,
                "error": f"Tool '{tool_name}' timed out",
                "tool_name": tool_name,
            }

        except (ValueError, TypeError, RuntimeError, OSError, AttributeError) as e:
            ref_id = str(uuid.uuid4())
            _security_logger.error(
                "Tool execution error (ref_id=%s): %s: %s",
                ref_id,
                tool_name,
                e,
                exc_info=True,
            )
            return {
                "success": False,
                "error": "Tool execution failed",
                "tool_name": tool_name,
                "ref_id": ref_id,
            }


# Module-level cache for global SDKConfig
_global_config: SDKConfig | None = None


def _get_global_config() -> SDKConfig:
    """Get cached global config or load new one."""
    global _global_config
    if _global_config is None:
        _global_config = SDKConfig.load()
    return _global_config


class AgentExecutor(AgentDefinition):
    """Adds execution capabilities on top of AgentDefinition.

    Provides run(), run_sync(), stream(), stream_sync(), cancel control,
    and internal runner/loop management.
    """

    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        system_prompt: str = "You are a helpful assistant.",
        model: str = "gpt-4o-mini",
        provider: str = "openai-compatible",
        base_url: str | None = None,
        api_key: str | None = None,
        tools: list[Tool] | None = None,
        policy: Any = None,
        mode: str = "local",
        backend_url: str | None = None,
        backend_api_key: str | None = None,
        backend_headers: dict[str, str] | None = None,
        agent_id: str | None = None,
        runner: Any = None,
        sub_agents: list[Agent] | None = None,
        max_depth: int = AgentDefinition.DEFAULT_MAX_DEPTH,
        current_depth: int = 0,
        keywords: list[str] | None = None,
        strip_thinking: bool | list[str] | None = None,
        loop: Any = None,
        skills: list[str] | None = None,
    ):
        """Initialize AgentExecutor."""
        super().__init__(
            name=name,
            instructions=instructions,
            system_prompt=system_prompt,
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            tools=tools,
            policy=policy,
            mode=mode,
            backend_url=backend_url,
            backend_api_key=backend_api_key,
            backend_headers=backend_headers,
            agent_id=agent_id,
            sub_agents=sub_agents,
            max_depth=max_depth,
            current_depth=current_depth,
            keywords=keywords,
            strip_thinking=strip_thinking,
            loop=loop,
            skills=skills,
        )
        self._local_runner: Any | None = None
        self._loop_cache: Any | None = None
        self.runner = runner

    @property
    def cancel_event(self) -> asyncio.Event:
        """Get the cancel event for interrupting execution."""
        if not hasattr(self, "_cancel_event") or self._cancel_event is None:
            self._cancel_event = asyncio.Event()
        return self._cancel_event

    def cancel(self) -> None:
        """Cancel current run/stream."""
        self.cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        """Check if execution has been cancelled."""
        return self.cancel_event.is_set()

    def reset_cancel(self) -> None:
        """Reset cancel state for next run."""
        self.cancel_event.clear()

    async def run(
        self,
        user_input: str,
        instructions: str | None = None,
        trace: bool = False,
        verbose: bool = False,
        stream_sse: bool = False,
        force_local: bool = False,
        messages: list[dict[str, Any]] | None = None,
    ) -> Union[str, Any]:
        """Run the agent with a user input.

        Raises:
            NotImplementedError: The execution infrastructure has been removed.
        """
        raise NotImplementedError("Agent execution infrastructure has been removed.")

    def run_sync(
        self,
        user_input: str,
        instructions: str | None = None,
        trace: bool = False,
        verbose: bool = False,
        force_local: bool = False,
        messages: list[dict[str, Any]] | None = None,
    ) -> Union[str, Any]:
        """Synchronous version of run().

        Raises:
            NotImplementedError: The execution infrastructure has been removed.
        """
        raise NotImplementedError("Agent execution infrastructure has been removed.")

    async def stream(
        self,
        user_input: str,
        instructions: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream response events from the agent.

        Raises:
            NotImplementedError: The execution infrastructure has been removed.
        """
        raise NotImplementedError("Agent execution infrastructure has been removed.")

    def stream_sync(
        self,
        user_input: str,
        instructions: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Alias for stream() — returns an async iterator.

        Raises:
            NotImplementedError: The execution infrastructure has been removed.
        """
        raise NotImplementedError("Agent execution infrastructure has been removed.")

    @staticmethod
    def execute_subprocess(
        command: str,
        timeout: int = 30,
        cwd: str | None = None,
    ) -> dict:
        """Execute command in subprocess securely.

        Uses subprocess.run with shell=False for secure execution.

        Args:
            command: Command string to execute.
            timeout: Timeout in seconds.
            cwd: Working directory for command execution.

        Returns:
            Dict with returncode, stdout, and stderr.
        """
        import subprocess
        import shlex

        _security_logger.debug("Executing subprocess: %s", command)
        parsed = shlex.split(command)
        result = subprocess.run(
            parsed,
            capture_output=True,
            timeout=timeout,
            shell=False,
            cwd=cwd,
        )
        _security_logger.debug("Subprocess completed with returncode: %s", result.returncode)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.decode("utf-8", errors="replace"),
            "stderr": result.stderr.decode("utf-8", errors="replace"),
        }

    @staticmethod
    def check_tool_permission(tool_name: str) -> bool:
        """Check if a tool can be executed based on permissions.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if tool is allowed, False otherwise.
        """
        from tinycua_sdk.security.permissions import PermissionSystem

        ps = PermissionSystem()
        allowed = ps.check_permission(tool_name)

        if not allowed:
            _security_logger.warning("Permission denied for tool: %s", tool_name)
        else:
            _security_logger.debug("Permission granted for tool: %s", tool_name)

        return allowed

    @staticmethod
    def check_tool_approval_required(tool_name: str) -> bool:
        """Check if a tool requires approval before execution.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if approval is required, False otherwise.
        """
        from tinycua_sdk.security.permissions import PermissionSystem

        ps = PermissionSystem()
        required = ps.requires_approval(tool_name)

        if required:
            _security_logger.info("Approval required for tool: %s", tool_name)

        return required
