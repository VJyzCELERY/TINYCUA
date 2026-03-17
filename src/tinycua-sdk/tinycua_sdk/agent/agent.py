"""Agent with tools and execution capabilities."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncIterator, Union

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.tools.decorators import Tool

if TYPE_CHECKING:
    from tinycua_sdk.runner import Runner
    from tinycua_sdk.models.response import StreamEvent


class Agent:
    """Agent with tools and execution capabilities."""

    MAX_SUB_AGENTS = 10
    DEFAULT_MAX_DEPTH = 3

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
        policy: AgentPolicy | None = None,
        plan_mode: str = "direct",
        planning_prompt: str | None = None,
        mode: str = "local",
        backend_url: str | None = None,
        backend_api_key: str | None = None,
        backend_headers: dict[str, str] | None = None,
        agent_id: str | None = None,
        runner: Any = None,
        sub_agents: list[Agent] | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
        current_depth: int = 0,
        keywords: list[str] | None = None,
        strip_thinking: bool | list[str] | None = None,
    ):
        """Initialize the Agent.

        Args:
            name: Agent name for identification.
            instructions: Additional instructions for the agent.
            system_prompt: System prompt that defines agent behavior.
            model: Model identifier to use.
            provider: LLM provider (openai, ollama, lmstudio).
            base_url: Custom base URL for the LLM API.
            api_key: API key for authentication.
            tools: List of tools available to the agent.
            policy: AgentPolicy instance for behavior settings.
            plan_mode: Execution mode (direct or plan).
            planning_prompt: Custom prompt for planning mode.
            mode: Execution mode (local or remote/deployed).
            backend_url: URL for the backend server (for deployed agents).
            backend_api_key: API key for backend authentication.
            backend_headers: Additional headers for backend requests.
            agent_id: ID of a deployed agent (for loading existing agents).
            runner: Optional runner instance for remote execution.
            sub_agents: List of sub-agents for delegation.
            max_depth: Maximum delegation depth allowed.
            current_depth: Current delegation depth (internal).
            keywords: Keywords for task routing to this agent.
            strip_thinking: Whether to strip thinking tags from responses.

        """
        self.config = AgentConfig(
            name=name,
            instructions=instructions,
            system_prompt=system_prompt,
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            tools=tools or [],
            policy=policy or AgentPolicy(),
            plan_mode=plan_mode,
            planning_prompt=planning_prompt,
            mode=mode,
            backend_url=backend_url,
            backend_api_key=backend_api_key,
            backend_headers=backend_headers,
            agent_id=agent_id,
            strip_thinking=strip_thinking,
            sub_agents=sub_agents or [],
        )
        self._local_runner: Runner | None = None
        self.runner = runner
        self._sub_agents = sub_agents or []
        self.max_depth = max_depth
        self.current_depth = current_depth
        self.keywords = keywords or []
        self.messages: list[dict[str, Any]] = []

    @property
    def sub_agents(self) -> list[Agent]:
        """Get list of sub-agents."""
        return self.config.sub_agents

    def add_sub_agent(self, agent: Agent) -> None:
        """Add a sub-agent to this agent.

        Args:
            agent: The sub-agent to add

        Raises:
            ValueError: If max sub-agents limit exceeded

        """
        if len(self.config.sub_agents) >= self.MAX_SUB_AGENTS:
            raise ValueError(
                f"Maximum {self.MAX_SUB_AGENTS} sub-agents allowed per agent"
            )
        self.config.sub_agents.append(agent)
        self._sub_agents = self.config.sub_agents

    def _get_all_sub_agents(self, depth: int = 0) -> dict[str, Agent]:
        """Get all sub-agents recursively.

        Args:
            depth: Current depth in recursion

        Returns:
            Dict of agent names to agents

        """
        if depth >= self.max_depth:
            return {self.name: self}

        result: dict[str, Agent] = {self.name: self}
        for sub in self._sub_agents:
            result.update(sub._get_all_sub_agents(depth + 1))
        return result

    def _find_sub_agent_for_task(self, task: str) -> Agent | None:
        """Find a sub-agent that can handle the task based on keywords.

        Args:
            task: The task description

        Returns:
            The matching sub-agent or None

        """
        task_lower = task.lower()

        for sub in self._sub_agents:
            sub_keywords = sub.keywords or [sub.name.lower()]
            if any(kw.lower() in task_lower for kw in sub_keywords):
                return sub

        return None

    def _pass_context_to_sub_agent(self, task: str, sub_agent: Agent) -> str:
        """Pass context to sub-agent.

        Args:
            task: The task to pass
            sub_agent: The sub-agent to pass to

        Returns:
            Context string

        """
        return f"""
Parent Task: {task}
Parent Agent: {self.name}
Instructions: {self.instructions}

Please complete this task and return results.
"""

    def _aggregate_results(self, sub_result: str, sub_agent: Agent) -> str:
        """Aggregate results from sub-agent.

        Args:
            sub_result: Result from sub-agent
            sub_agent: The sub-agent that produced the result

        Returns:
            Aggregated result string

        """
        return f"""
[Sub-agent: {sub_agent.name}]
Result: {sub_result}

Summary: Completed via delegation to {sub_agent.name}
"""

    @property
    def policy(self) -> AgentPolicy:
        """Get agent policy (backward compatibility)."""
        return self.config.policy

    @property
    def name(self) -> str:
        """Get agent name."""
        return self.config.name

    @property
    def mode(self) -> str:
        """Get agent mode (local or deployed)."""
        return self.config.mode

    @property
    def agent_id(self) -> str | None:
        """Get deployed agent ID."""
        return self.config.agent_id

    @property
    def is_deployed(self) -> bool:
        """Check if agent is in deployed mode."""
        return self.config.mode == "deployed"

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
    def instructions(self) -> str:
        """Get agent instructions."""
        return self.config.instructions

    @property
    def system_prompt(self) -> str:
        """Get system prompt."""
        return self.config.system_prompt

    @property
    def model(self) -> str:
        """Get model name."""
        return self.config.model

    @property
    def provider(self) -> str:
        """Get provider name."""
        return self.config.provider

    @property
    def tools(self) -> list[Tool]:
        """Get agent tools."""
        return self.config.tools

    def add_tool(self, tool: Tool) -> None:
        """Add a tool to the agent."""
        self.config.tools.append(tool)

    def add_tools(self, tools: list[Tool]) -> None:
        """Add multiple tools to the agent."""
        self.config.tools.extend(tools)

    def to_config(self) -> dict[str, Any]:
        """Serialize agent config to dict."""
        return self.config.to_config()

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> Agent:
        """Create agent from config dict."""
        config = AgentConfig.from_config(data)
        agent = cls(
            name=config.name,
            instructions=config.instructions,
            system_prompt=config.system_prompt,
            model=config.model,
            provider=config.provider,
            base_url=config.base_url,
            api_key=config.api_key,
            tools=config.tools,
            policy=config.policy,
            plan_mode=config.plan_mode,
            planning_prompt=config.planning_prompt,
            strip_thinking=config.strip_thinking,
        )
        return agent

    def _get_runner(self) -> Runner:
        """Get or create the internal runner."""
        from tinycua_sdk.runner import Runner

        if self._local_runner is None:
            self._local_runner = Runner(self.config)
        return self._local_runner

    async def run(
        self,
        user_input: str,
        instructions: str | None = None,
        trace: bool = False,
        verbose: bool = False,
        stream_sse: bool = False,
        force_local: bool = False,
    ) -> Union[str, Any]:
        """Run the agent with a user input.

        Args:
            user_input: The user's message
            instructions: Optional custom instructions
            trace: If True, return RunResult with trace info
            verbose: If True, log raw SSE events
            stream_sse: If True, yield all SSE events as they happen
            force_local: If True, run locally even if deployed

        Returns:
            Assistant response string, RunResult if trace=True, or AsyncIterator if stream_sse=True

        """
        if self.is_deployed and not force_local:
            return await self._run_deployed(user_input, instructions, trace)

        self.reset_cancel()
        from tinycua_sdk.runner import Runner

        runner = Runner(self.config, cancel_event=self.cancel_event)

        runner.trace = trace
        runner.verbose = verbose
        runner.stream_sse = stream_sse

        if stream_sse:
            return runner.chat_sse(user_input, instructions=instructions)

        try:
            result = await runner.chat(
                user_input, instructions=instructions, trace=trace
            )
            return result
        finally:
            await runner.close()

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
            self.run(user_input, instructions, trace, verbose, force_local=force_local)
        )

    async def stream(
        self,
        user_input: str,
        instructions: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream response events from the agent.

        Args:
            user_input: The user's message
            instructions: Optional custom instructions

        Yields:
            StreamEvent objects with type and data

        """
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
        """Synchronous version of stream()."""
        return self.stream(user_input, instructions)

    async def _run_deployed(
        self,
        user_input: str,
        instructions: str | None = None,
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
        ):
            if isinstance(event, dict):
                if event.get("type") == "content":
                    response_text += event.get("data", {}).get("content", "")

        self.messages.append({"role": "assistant", "content": response_text})

        return response_text

    def _get_backend_config(self) -> tuple[str, str | None, dict[str, str] | None]:
        """Get backend configuration with priority.

        Returns:
            Tuple of (backend_url, api_key, headers)

        """
        from tinycua_sdk.config import config

        backend_url = self.config.backend_url or config.BACKEND_URL
        api_key = self.config.backend_api_key or config.API_KEY
        headers = self.config.backend_headers

        return backend_url, api_key, headers

    async def deploy(self) -> dict[str, Any]:
        """Deploy the agent and its tools to the backend.

        After deployment, the agent will be in "deployed" mode
        and will call the backend instead of running locally.

        This method:
        1. Queries backend for existing tools
        2. Auto-detects external and internal dependencies
        3. Detects circular dependencies
        4. Computes version hashes
        5. Uploads tools in topological order (deps first)

        Returns:
            Deployment result with agent_id and status

        Raises:
            RuntimeError: If circular dependency detected
        """
        from tinycua_sdk.clients import BackendClient
        from tinycua_sdk.tools.resolver import (
            analyze_source,
            find_internal_calls,
            detect_circular,
            compute_version,
            topological_sort,
        )

        backend_url, backend_api_key, backend_headers = self._get_backend_config()

        client = BackendClient(
            base_url=backend_url,
            api_key=backend_api_key,
            headers=backend_headers,
        )

        tools = list(self.config.tools)
        tool_names = {t.name for t in tools}

        existing_tools: dict[str, dict[str, Any]] = {}
        try:
            backend_tools = await client.list_tools()
            for t in backend_tools:
                existing_tools[t.get("name", "")] = t
        except Exception:
            pass

        for tool in tools:
            if tool._source:
                external_deps = analyze_source(tool._source)
                tool._external_dependencies = external_deps

                internal_calls = find_internal_calls(tool._source)
                tool_deps = []
                for call_name in internal_calls:
                    if call_name in tool_names and call_name != tool.name:
                        dep_tool = next((t for t in tools if t.name == call_name), None)
                        if dep_tool:
                            tool_deps.append(
                                {
                                    "id": getattr(dep_tool, "_id", ""),
                                    "name": call_name,
                                    "version": getattr(dep_tool, "_version", ""),
                                }
                            )
                tool._tool_dependencies = tool_deps

                tool._version = compute_version(
                    tool._source or "",
                    tool._tool_dependencies,
                )

        tool_map = {t.name: t for t in tools}
        cycle = detect_circular(tools, tool_map)
        if cycle:
            cycle_str = " → ".join(cycle)
            raise RuntimeError(f"Circular dependency detected: {cycle_str}")

        sorted_tools = topological_sort(tools)

        tools_to_upload = []
        for tool in sorted_tools:
            existing = existing_tools.get(tool.name, {})
            if existing.get("version") != tool._version:
                tools_to_upload.append(tool)

        for tool in tools_to_upload:
            bundle = tool.to_bundle()
            try:
                await client.deploy_tool(bundle)
            except Exception as e:
                raise RuntimeError(f"Failed to deploy tool {tool.name}: {e}")

        deployment = {
            "agent": self.to_config(),
            "tools": [],
        }

        for tool in self.config.tools:
            deployment["tools"].append(
                {
                    "name": tool.name,
                    "bundle": tool.to_bundle(),
                }
            )

        response = await client.deploy_agent(agent_config=deployment)

        self.config.mode = "deployed"
        self.config.agent_id = response["agent_id"]
        self.config.backend_url = backend_url

        return response

    async def delete(self) -> None:
        """Delete the agent from the backend."""
        from tinycua_sdk.clients import BackendClient

        if not self.config.agent_id:
            raise RuntimeError("Agent not deployed")

        backend_url, backend_api_key, backend_headers = self._get_backend_config()

        client = BackendClient(
            base_url=backend_url,
            api_key=backend_api_key,
            headers=backend_headers,
        )

        await client.delete_agent(agent_id=self.config.agent_id)

        self.config.agent_id = None
        self.config.mode = "local"

    @classmethod
    async def load_agent(
        cls,
        agent_id: str,
        backend_url: str,
        backend_api_key: str | None = None,
        backend_headers: dict[str, str] | None = None,
    ) -> Agent:
        """Load an existing agent from the backend.

        Args:
            agent_id: ID of the agent to load
            backend_url: Backend server URL
            backend_api_key: API key for authentication
            backend_headers: Custom headers for auth

        Returns:
            Agent instance with configuration from backend

        """
        from tinycua_sdk.clients import BackendClient

        client = BackendClient(
            base_url=backend_url,
            api_key=backend_api_key,
            headers=backend_headers,
        )

        agent_data = await client.get_agent(agent_id)

        agent = cls.from_config(agent_data)
        agent.config.agent_id = agent_id
        agent.config.mode = "deployed"
        agent.config.backend_url = backend_url

        return agent

    def __str__(self) -> str:
        """Return formatted string representation of the agent.

        Returns:
            Formatted string with agent details

        """
        lines = [
            f"Agent: {self.config.name}",
            f"  Mode: {self.config.mode}",
            f"  Model: {self.config.model}",
            f"  Provider: {self.config.provider}",
        ]

        if self.config.agent_id:
            lines.append(f"  Agent ID: {self.config.agent_id}")
            lines.append(f"  Backend: {self.config.backend_url}")

        if self.config.backend_headers:
            lines.append(f"  Headers: {list(self.config.backend_headers.keys())}")

        lines.append(f"  Tools: {len(self.config.tools)}")
        lines.append(f"  Sub-agents: {len(self.config.sub_agents)}")

        return "\n".join(lines)


__all__ = ["Agent", "AgentConfig", "AgentPolicy"]
