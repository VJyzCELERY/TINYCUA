"""Agent package for TINYCUA application."""

from tinycua.agent.default_agent import create_default_agent
from tinycua.agent.lifecycle import AgentLifecycle

__all__ = ["AgentLifecycle", "create_default_agent"]
