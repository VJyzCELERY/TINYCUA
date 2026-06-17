"""Integration tests for the benchmark pipeline."""

from __future__ import annotations

import pytest

from agents_benchmark.agent_registry import AgentRegistry
from agents_benchmark.base_agent import AgentExecution
from agents_benchmark.runner import BenchmarkRunner


@pytest.fixture
def mock_adapters():
    """Register mock adapters that succeed for all agents."""
    registry = AgentRegistry()
    for name in ["hermes", "claudecode", "codex", "openclaw"]:
        adapter_cls = _make_mock_adapter(name, succeed=True)
        registry.register(name, adapter_cls)
    return registry


@pytest.fixture
def mock_adapters_with_failure():
    """Register adapters where hermes fails and claudecode succeeds."""
    registry = AgentRegistry()
    registry.register("hermes", _make_mock_adapter("hermes", succeed=False))
    registry.register("claudecode", _make_mock_adapter("claudecode", succeed=True))
    registry.register("codex", _make_mock_adapter("codex", succeed=True))
    registry.register("openclaw", _make_mock_adapter("openclaw", succeed=True))
    return registry


def _make_mock_adapter(name: str, succeed: bool = True):
    """Create a mock adapter class that implements BaseAgent."""

    class MockAdapter:
        @property
        def name(self):
            return name

        @property
        def expects_gateway(self):
            return False

        @property
        def transcript_container_path(self):
            return "/workspace/transcript.jsonl"

        def run_task(self, spec):
            if succeed:
                return AgentExecution(elapsed_time=1.0)
            return AgentExecution(elapsed_time=0.5, error=f"{name} failed")

        def collect_usage(self, task_id, output_dir, elapsed_time):
            return {"requests": 1, "total_tokens": 100, "cost": 0.001}

    return MockAdapter


def test_pipeline_runs_all_agents_in_order(mock_adapters):
    """Pipeline must execute agents in fixed order: hermes, claudecode, codex, openclaw."""
    runner = BenchmarkRunner(registry=mock_adapters, results_dir="output")
    result = runner.run_pipeline(agents=["all"], model="test-model")

    assert len(result.agent_results) == 4
    assert list(result.agent_results.keys()) == [
        "hermes",
        "claudecode",
        "codex",
        "openclaw",
    ]


def test_pipeline_filters_agents(mock_adapters):
    """Pipeline must only run agents specified in --agents filter."""
    runner = BenchmarkRunner(registry=mock_adapters, results_dir="output")
    result = runner.run_pipeline(agents=["hermes", "openclaw"], model="test-model")

    assert "hermes" in result.agent_results
    assert "openclaw" in result.agent_results
    assert "claudecode" not in result.agent_results
    assert "codex" not in result.agent_results


def test_pipeline_skips_failed_agent_and_continues(mock_adapters_with_failure):
    """Pipeline must skip a failed agent and continue with the next one."""
    runner = BenchmarkRunner(registry=mock_adapters_with_failure, results_dir="output")
    result = runner.run_pipeline(agents=["all"], model="test-model")

    assert "hermes" in result.agent_results
    assert "claudecode" in result.agent_results
    assert result.summary["hermes"]["status"] == "error"
    assert result.summary["claudecode"]["status"] == "success"
