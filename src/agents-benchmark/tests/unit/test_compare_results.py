"""Unit tests for N-way comparison (compare_agents)."""

from __future__ import annotations

from agents_benchmark.compare import compare_agents


class TestCompareAgents:
    """Tests for compare_agents function."""

    def test_returns_expected_structure(self):
        """compare_agents must return dict with expected top-level keys."""
        result = compare_agents({})
        assert "agents" in result
        assert "per_task_comparison" in result
        assert "aggregate" in result

    def test_empty_results(self):
        """compare_agents must handle empty results gracefully."""
        result = compare_agents({})
        assert result["per_task_comparison"] == []
        assert result["agents"] == []
        assert result["aggregate"] == {}

    def test_two_agent_comparison(self):
        """Two-agent comparison must produce correct per-task entries."""
        agent_results = {
            "hermes": [{"task_id": "t1", "score": 1.0, "status": "success"}],
            "claudecode": [{"task_id": "t1", "score": 0.5, "status": "success"}],
        }
        result = compare_agents(agent_results)

        assert len(result["per_task_comparison"]) == 1
        entry = result["per_task_comparison"][0]
        assert entry["task_id"] == "t1"
        assert entry["hermes_score"] == 1.0
        assert entry["claudecode_score"] == 0.5

    def test_three_agent_comparison(self):
        """Three-agent comparison must include all agents."""
        agent_results = {
            "hermes": [{"task_id": "t1", "score": 1.0, "status": "success"}],
            "claudecode": [{"task_id": "t1", "score": 0.5, "status": "success"}],
            "codex": [{"task_id": "t1", "score": 0.8, "status": "success"}],
        }
        result = compare_agents(agent_results)

        assert result["agents"] == ["claudecode", "codex", "hermes"]
        entry = result["per_task_comparison"][0]
        assert entry["hermes_score"] == 1.0
        assert entry["claudecode_score"] == 0.5
        assert entry["codex_score"] == 0.8

    def test_missing_tasks_appear_with_nulls(self):
        """Tasks missing in some agents must appear with null scores."""
        agent_results = {
            "hermes": [{"task_id": "t1", "score": 1.0, "status": "success"}],
            "codex": [],
        }
        result = compare_agents(agent_results)

        entry = result["per_task_comparison"][0]
        assert entry["hermes_score"] == 1.0
        assert entry["codex_score"] is None

    def test_aggregate_stats(self):
        """Aggregate must compute per-agent averages."""
        agent_results = {
            "hermes": [
                {"task_id": "t1", "score": 1.0, "status": "success"},
                {"task_id": "t2", "score": 0.5, "status": "success"},
            ],
        }
        result = compare_agents(agent_results)

        assert result["aggregate"]["hermes"]["average_score"] == 0.75
        assert result["aggregate"]["hermes"]["total_tasks"] == 2
        assert result["aggregate"]["hermes"]["successful_tasks"] == 2
