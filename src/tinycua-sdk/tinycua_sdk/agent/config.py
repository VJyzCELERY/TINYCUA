"""Agent configuration classes."""

import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tinycua_sdk.tools.decorators import Tool

if TYPE_CHECKING:
    from tinycua_sdk.agent import Agent


@dataclass
class AgentPolicy:
    """Policy for agent behavior."""

    max_tool_calls: int = 10
    parallel_tool_calls: bool = True
    temperature: float = 1.0


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str = "assistant"
    instructions: str = ""
    system_prompt: str = "You are a helpful assistant."
    model: str = "gpt-5-nano"
    provider: str = "openai"
    base_url: str | None = None
    api_key: str | None = None
    tools: list[Tool] = field(default_factory=list)
    policy: AgentPolicy = field(default_factory=AgentPolicy)
    plan_mode: str = "direct"
    planning_prompt: str | None = None
    # Deployed mode settings
    mode: str = "local"  # "local" or "deployed"
    backend_url: str | None = None
    backend_api_key: str | None = None
    backend_headers: dict[str, str] | None = None
    agent_id: str | None = None
    # Thinking strip: None=default patterns, False=disable, list=custom regex
    strip_thinking: bool | list[str] | None = None
    # Sub-agents for delegation
    sub_agents: list["Agent"] = field(default_factory=list)
    # Custom loop configuration
    loop: Any = None  # DefaultLoop subclass

    def to_config(self) -> dict[str, Any]:
        """Serialize agent config to dict."""
        loop_config = None
        if self.loop is not None:
            from tinycua_sdk.agent.loop_resolver import analyze_loop_source

            loop_class = self.loop.__class__
            class_name = loop_class.__name__

            module = inspect.getmodule(loop_class)
            if module and module.__file__:
                with open(module.__file__, "r") as f:
                    module_source = f.read()
            else:
                module_source = ""

            class_source = inspect.getsource(loop_class)
            dependencies, helpers = analyze_loop_source(class_source)

            if not helpers and module_source:
                dependencies, helpers = analyze_loop_source(module_source)

            loop_config = {
                "class_name": class_name,
                "source": class_source,
                "dependencies": dependencies,
                "helpers": helpers,
            }

        return {
            "name": self.name,
            "instructions": self.instructions,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "tools": [
                t.to_config() if hasattr(t, "to_config") else t for t in self.tools
            ],
            "policy": {
                "max_tool_calls": self.policy.max_tool_calls,
                "parallel_tool_calls": self.policy.parallel_tool_calls,
                "temperature": self.policy.temperature,
            },
            "plan_mode": self.plan_mode,
            "planning_prompt": self.planning_prompt,
            "strip_thinking": self.strip_thinking,
            "loop": loop_config,
        }

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "AgentConfig":
        """Deserialize agent config from dict."""
        policy_data = data.get("policy", {})
        policy = AgentPolicy(
            max_tool_calls=policy_data.get("max_tool_calls", 10),
            parallel_tool_calls=policy_data.get("parallel_tool_calls", True),
            temperature=policy_data.get("temperature", 1.0),
        )
        loop_config = data.get("loop")

        return cls(
            name=data.get("name", "assistant"),
            instructions=data.get("instructions", ""),
            system_prompt=data.get("system_prompt", "You are a helpful assistant."),
            model=data.get("model", "gpt-4o-mini"),
            provider=data.get("provider", "openai"),
            base_url=data.get("base_url"),
            api_key=data.get("api_key"),
            tools=data.get("tools", []),
            policy=policy,
            plan_mode=data.get("plan_mode", "direct"),
            planning_prompt=data.get("planning_prompt"),
            strip_thinking=data.get("strip_thinking"),
            loop=loop_config,  # Store raw config for later materialization
        )


__all__ = ["AgentConfig", "AgentPolicy"]
