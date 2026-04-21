"""Agent execution capabilities: run, stream, cancel."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Union

from tinycua_sdk.agent.definition import AgentDefinition
from tinycua_sdk.core.config import SDKConfig

if TYPE_CHECKING:
    from tinycua_sdk.runner import Runner
    from tinycua_sdk.models.response import StreamEvent
    from tinycua_sdk.agent.loop import DefaultLoop
    from tinycua_sdk.tools.decorators import Tool
    from tinycua_sdk.agent.agent import Agent


_security_logger = logging.getLogger("tinycua_sdk.security")

import traceback


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
            _security_logger.error(f"Tool execution timeout: {tool_name}")
            return {
                "success": False,
                "error": f"Tool '{tool_name}' timed out",
                "tool_name": tool_name,
            }

        except Exception as e:
            _security_logger.error(f"Tool execution error: {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "traceback": traceback.format_exc(),
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
            _security_logger.error(f"Tool execution timeout: {tool_name}")
            return {
                "success": False,
                "error": f"Tool '{tool_name}' timed out",
                "tool_name": tool_name,
            }

        except Exception as e:
            _security_logger.error(f"Tool execution error: {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "traceback": traceback.format_exc(),
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
    guest session state, and internal runner/loop management.
    """

    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        system_prompt: str = "You are a helpful assistant.",
        model: str = "gpt-4o-mini",
        provider: str = "openai",
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
        planning_prompt: str | None = None,
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
            planning_prompt=planning_prompt,
        )
        self._local_runner: Runner | None = None
        self._loop_cache: BaseLoop | None = None
        self.runner = runner
        self.messages: list[dict[str, Any]] = []

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

    @property
    def guest_session_id(self) -> str | None:
        """Get guest session ID."""
        return getattr(self, "_guest_session_id", None)

    @guest_session_id.setter
    def guest_session_id(self, value: str | None) -> None:
        """Set guest session ID."""
        self._guest_session_id = value

    def _get_runner(self) -> Runner:
        """Get or create the internal runner."""
        from tinycua_sdk.runner import Runner

        if self._local_runner is None:
            self._local_runner = Runner(self.config)
        return self._local_runner

    def _load_loop(self) -> DefaultLoop:
        """Load custom loop from config or use DefaultLoop."""
        from tinycua_sdk.agent.loop import DefaultLoop, resolve_loop
        from tinycua_sdk.runner import Runner

        if self._loop_cache is not None:
            return self._loop_cache
        runner = Runner(self.config, cancel_event=self.cancel_event)
        loop_config = getattr(self.config, "loop", None)

        # Check if loop_config is already a loop instance
        if loop_config is not None and hasattr(loop_config, "run"):
            loop_config.runner = runner
            self._loop_cache = loop_config
            return loop_config

        # Use resolve_loop to resolve string/dict config to loop instance
        loop = resolve_loop(loop_config)

        # Set runner on the resolved loop (resolve_loop doesn't set it)
        loop.runner = runner

        self._loop_cache = loop
        return loop

    def _get_backend_config(self) -> tuple[str, str | None, dict[str, str] | None]:
        """Get backend configuration with priority."""
        global_config = _get_global_config()
        backend_url = (
            self.config.backend_url
            if self.config.backend_url is not None
            else global_config.backend_url
        )
        backend_api_key = (
            self.config.backend_api_key
            if self.config.backend_api_key is not None
            else global_config.llm.api_key.get_secret_value()
        )
        return (
            backend_url,
            backend_api_key,
            self.config.backend_headers,
        )

    async def _run_deployed(
        self,
        user_input: str,
        trace: bool = False,
    ) -> Union[str, Any]:
        """Run via backend API when in deployed mode."""
        if not self.config.agent_id:
            raise RuntimeError("Agent not deployed. Call deploy() first.")
        global_config = _get_global_config()
        backend_url = (
            self.config.backend_url
            if self.config.backend_url is not None
            else global_config.backend_url
        )
        backend_api_key = (
            self.config.backend_api_key
            if self.config.backend_api_key is not None
            else global_config.llm.api_key.get_secret_value()
        )
        from tinycua_sdk.clients import BackendClient

        client = BackendClient(
            base_url=backend_url,
            api_key=backend_api_key,
            headers=self.config.backend_headers,
        )
        self.messages.append({"role": "user", "content": user_input})
        response_text = ""
        async for event in client.execute(
            agent_id=self.config.agent_id,
            messages=self.messages,
            tools=[t.to_config() for t in self.tools],
        ):
            if isinstance(event, dict) and event.get("type") == "content":
                response_text += event.get("data", {}).get("content", "")
        self.messages.append({"role": "assistant", "content": response_text})
        return response_text

    async def _run_guest(
        self,
        user_input: str,
        instructions: str | None = None,
    ) -> str:
        """Run via backend API in guest mode (no auth required)."""
        if not self.config.agent_id:
            raise RuntimeError("Agent ID required for guest mode.")
        global_config = _get_global_config()
        backend_url = (
            self.config.backend_url
            if self.config.backend_url is not None
            else global_config.backend_url
        )
        from tinycua_sdk.clients import BackendClient

        client = BackendClient(base_url=backend_url)
        self.messages.append({"role": "user", "content": user_input})
        response_text = ""
        async for event in client.guest_run(
            agent_id=self.config.agent_id,
            user_input=user_input,
            session_id=self.guest_session_id,
        ):
            if isinstance(event, dict):
                if event.get("type") == "content":
                    response_text += event.get("data", {}).get("content", "")
                elif event.get("type") == "session_id":
                    self._guest_session_id = event.get("data", {}).get("session_id")
        self.messages.append({"role": "assistant", "content": response_text})
        return response_text

    async def run(
        self,
        user_input: str,
        instructions: str | None = None,
        trace: bool = False,
        verbose: bool = False,
        stream_sse: bool = False,
        force_local: bool = False,
    ) -> Union[str, Any]:
        """Run the agent with a user input."""
        if self.is_deployed and not force_local:
            return await self._run_deployed(user_input, trace=trace)
        if self.is_guest and not force_local:
            return await self._run_guest(user_input, instructions)
        self.reset_cancel()
        loop = self._load_loop()
        return await loop.run(
            self,
            user_input,
            trace=trace,
            verbose=verbose,
            stream_sse=stream_sse,
        )

    def run_sync(
        self,
        user_input: str,
        instructions: str | None = None,
        trace: bool = False,
        verbose: bool = False,
        force_local: bool = False,
    ) -> Union[str, Any]:
        """Synchronous version of run()."""
        import asyncio

        return asyncio.run(
            self.run(
                user_input,
                instructions,
                trace,
                verbose,
                force_local=force_local,
            ),
        )

    async def stream(
        self,
        user_input: str,
        instructions: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream response events from the agent."""
        from tinycua_sdk.runner import Runner

        self.reset_cancel()
        runner = Runner(self.config, cancel_event=self.cancel_event)
        runner.verbose = False
        runner.trace = False
        try:
            async for event in runner.stream_with_tools(user_input, instructions):
                yield event
        finally:
            await runner.close()

    def stream_sync(
        self,
        user_input: str,
        instructions: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Alias for stream() — returns an async iterator."""
        return self.stream(user_input, instructions)

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

        _security_logger.debug(f"Executing subprocess: {command}")
        parsed = shlex.split(command)
        result = subprocess.run(
            parsed,
            capture_output=True,
            timeout=timeout,
            shell=False,
            cwd=cwd,
        )
        _security_logger.debug(f"Subprocess completed with returncode: {result.returncode}")
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
            _security_logger.warning(
                f"Permission denied for tool: {tool_name}"
            )
        else:
            _security_logger.debug(
                f"Permission granted for tool: {tool_name}"
            )

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
            _security_logger.info(
                f"Approval required for tool: {tool_name}"
            )

        return required
