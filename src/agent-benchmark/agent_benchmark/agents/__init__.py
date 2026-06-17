"""Agent registry — get_agent() returns the right adapter by name."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_benchmark.base_agent import BaseAgent

_REGISTRY: dict[str, str] = {
    "openclaw": "agent_benchmark.agents.openclaw:OpenClawAgent",
    "claudecode": "agent_benchmark.agents.claude_code:ClaudeCodeAgent",
    "codex": "agent_benchmark.agents.codex:CodexAgent",
    "hermesagent": "agent_benchmark.agents.hermes_agent:HermesAgent",
}


def get_agent(name: str, **kwargs: object) -> BaseAgent:
    """Instantiate an agent adapter by name.

    Args:
        name: Harness name — "openclaw", "claudecode", "codex", or "hermesagent".
        **kwargs: Passed to the agent constructor (e.g., config_path for Hermes).

    Returns:
        Initialized BaseAgent instance.

    Raises:
        ValueError: If name is not in the registry.
    """
    if name not in _REGISTRY:
        valid = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Unknown agent '{name}'. Valid: {valid}")

    import importlib

    module_path, class_name = _REGISTRY[name].rsplit(":", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(**kwargs)


def list_agents() -> list[str]:
    """Return sorted list of available agent names."""
    return sorted(_REGISTRY)
