"""WildClawBench adapter for TinyCUA.

Provides TinyCUAAgent — a WildClawBench-compatible BaseAgent implementation
that wraps the tinycua run CLI as a subprocess.
"""

from tinycua.wildclawbench.agent import TinyCUAAgent
from tinycua.wildclawbench.base_agent import AgentExecution, AgentTaskSpec, BaseAgent

__all__ = ["AgentExecution", "AgentTaskSpec", "BaseAgent", "TinyCUAAgent"]
