"""Agent execution capabilities: run, stream, cancel."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncIterator, Union

from tinycua_sdk.agent.definition import AgentDefinition

if TYPE_CHECKING:
    from tinycua_sdk.runner import Runner
    from tinycua_sdk.models.response import StreamEvent
    from tinycua_sdk.agent.loop import DefaultLoop
    from tinycua_sdk.tools.decorators import Tool
    from tinycua_sdk.agent.agent import Agent


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
        plan_mode: str = "direct",
        planning_prompt: str | None = None,
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
            plan_mode=plan_mode,
            planning_prompt=planning_prompt,
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
        self._local_runner: Runner | None = None
        self._loop_cache: DefaultLoop | None = None
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

        # Check if loop_config is a custom code injection (dict with source)
        if isinstance(loop_config, dict):
            class_name = loop_config.get("class_name")
            source = loop_config.get("source")
            helpers = loop_config.get("helpers", [])
            if source:
                namespace: dict = {"DefaultLoop": DefaultLoop}
                for helper in helpers:
                    exec(helper.get("source", ""), namespace)
                exec(source, namespace)
                loop_type = namespace.get(class_name) or namespace.get("DefaultLoop")
                loop = loop_type(runner)
                self._loop_cache = loop
                return loop

        # Use resolve_loop to resolve string/dict config to loop instance
        loop = resolve_loop(loop_config)

        # Set runner on the resolved loop (resolve_loop doesn't set it)
        loop.runner = runner

        self._loop_cache = loop
        return loop

    def _get_backend_config(self) -> tuple[str, str | None, dict[str, str] | None]:
        """Get backend configuration with priority."""
        from tinycua_sdk.config import config

        return (
            self.config.backend_url or config.BACKEND_URL,
            self.config.backend_api_key or config.API_KEY,
            self.config.backend_headers,
        )

    async def _run_deployed(
        self,
        user_input: str,
        plan_mode: bool = False,
        trace: bool = False,
    ) -> Union[str, Any]:
        """Run via backend API when in deployed mode."""
        from tinycua_sdk.config import config

        if not self.config.agent_id:
            raise RuntimeError("Agent not deployed. Call deploy() first.")
        backend_url = self.config.backend_url or config.BACKEND_URL
        backend_api_key = self.config.backend_api_key or config.API_KEY
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
            plan_mode=plan_mode,
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
        from tinycua_sdk.config import config

        if not self.config.agent_id:
            raise RuntimeError("Agent ID required for guest mode.")
        backend_url = self.config.backend_url or config.BACKEND_URL
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
        plan_mode: bool = False,
        trace: bool = False,
        verbose: bool = False,
        stream_sse: bool = False,
        force_local: bool = False,
    ) -> Union[str, Any]:
        """Run the agent with a user input."""
        if self.is_deployed and not force_local:
            return await self._run_deployed(
                user_input, plan_mode=plan_mode, trace=trace
            )
        if self.is_guest and not force_local:
            return await self._run_guest(user_input, instructions)
        self.reset_cancel()
        loop = self._load_loop()
        return await loop.run(
            self,
            user_input,
            plan_mode=plan_mode,
            trace=trace,
            verbose=verbose,
            stream_sse=stream_sse,
        )

    def run_sync(
        self,
        user_input: str,
        instructions: str | None = None,
        plan_mode: bool = False,
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
                plan_mode,
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
