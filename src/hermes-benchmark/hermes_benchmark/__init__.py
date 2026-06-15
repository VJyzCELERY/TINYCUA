"""Hermes benchmark — Hermes agent adapter for WildClawBench benchmarking."""

from hermes_benchmark.base_agent import AgentExecution, AgentTaskSpec, BaseAgent
from hermes_benchmark.hermes_agent import HermesAgent
from hermes_benchmark.hermes_config import HermesConfig, load_hermes_config
from hermes_benchmark.compare_results import compare_results

__all__ = [
    "AgentExecution",
    "AgentTaskSpec",
    "BaseAgent",
    "HermesAgent",
    "HermesConfig",
    "load_hermes_config",
    "compare_results",
]
