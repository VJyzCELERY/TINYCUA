"""Integration tests for N-way comparison."""

from __future__ import annotations

from agents_benchmark.compare import compare_agents


def test_compare_agents_produces_per_task_deltas():
    """compare_agents must produce per-task deltas for N agents."""
    agent_results = {
        "hermes": [{"task_id": "t1", "score": 1.0, "status": "success"}],
        "claudecode": [{"task_id": "t1", "score": 0.5, "status": "success"}],
    }
    report = compare_agents(agent_results)

    assert len(report["per_task_comparison"]) == 1
    assert report["per_task_comparison"][0]["hermes_score"] == 1.0
    assert report["per_task_comparison"][0]["claudecode_score"] == 0.5


def test_compare_agents_empty_results():
    """compare_agents must handle empty results gracefully."""
    report = compare_agents({})
    assert report["per_task_comparison"] == []
    assert report["agents"] == []
