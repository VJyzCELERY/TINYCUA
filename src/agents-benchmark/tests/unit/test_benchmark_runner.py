"""Unit tests for BenchmarkRunner."""

from __future__ import annotations

from agents_benchmark.agent_registry import AgentRegistry
from agents_benchmark.base_agent import AgentExecution
from agents_benchmark.runner import BenchmarkRunner


class MockAdapter:
    """Minimal mock adapter for testing."""

    def __init__(self, name="mock", succeed=True):
        self._name = name
        self._succeed = succeed

    @property
    def name(self):
        return self._name

    @property
    def expects_gateway(self):
        return False

    @property
    def transcript_container_path(self):
        return "/workspace/transcript.jsonl"

    def run_task(self, spec):
        if self._succeed:
            return AgentExecution(elapsed_time=1.0)
        return AgentExecution(elapsed_time=0.5, error="mock failure")

    def collect_usage(self, task_id, output_dir, elapsed_time):
        return {"requests": 1, "total_tokens": 100, "cost": 0.001}


def _make_registry(*names_succeed):
    """Create a registry with mock adapters."""
    registry = AgentRegistry()
    for name, succeed in names_succeed:
        cls = lambda n=name, s=succeed: MockAdapter(name=n, succeed=s)
        registry.register(name, cls)
    return registry


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner."""

    def test_pipeline_runs_agents_in_order(self):
        """Pipeline must run agents in the defined order."""
        registry = _make_registry(
            ("hermes", True),
            ("claudecode", True),
            ("codex", True),
            ("openclaw", True),
        )
        runner = BenchmarkRunner(registry=registry)
        result = runner.run_pipeline(agents=["all"], model="test")

        assert list(result.agent_results.keys()) == [
            "hermes",
            "claudecode",
            "codex",
            "openclaw",
        ]

    def test_agent_filtering(self):
        """Pipeline must only run filtered agents."""
        registry = _make_registry(
            ("hermes", True),
            ("claudecode", True),
            ("codex", True),
            ("openclaw", True),
        )
        runner = BenchmarkRunner(registry=registry)
        result = runner.run_pipeline(agents=["hermes", "openclaw"], model="test")

        assert "hermes" in result.agent_results
        assert "openclaw" in result.agent_results
        assert "claudecode" not in result.agent_results
        assert "codex" not in result.agent_results

    def test_failed_agent_is_skipped(self):
        """Pipeline must skip failed agents and continue."""
        registry = _make_registry(
            ("hermes", False),
            ("claudecode", True),
        )
        runner = BenchmarkRunner(registry=registry)
        result = runner.run_pipeline(agents=["all"], model="test")

        assert result.summary["hermes"]["status"] == "error"
        assert result.summary["claudecode"]["status"] == "success"

    def test_empty_agent_list(self):
        """Empty agent list must produce empty results."""
        registry = _make_registry(("hermes", True))
        runner = BenchmarkRunner(registry=registry)
        result = runner.run_pipeline(agents=[], model="test")

        assert result.agent_results == {}
        assert result.summary == {}

    def test_pipeline_result_summary(self):
        """Pipeline result must contain summary per agent."""
        registry = _make_registry(
            ("hermes", True),
            ("claudecode", True),
        )
        runner = BenchmarkRunner(registry=registry)
        result = runner.run_pipeline(agents=["all"], model="test")

        assert "hermes" in result.summary
        assert result.summary["hermes"]["status"] == "success"
        assert "claudecode" in result.summary
        assert result.summary["claudecode"]["status"] == "success"
