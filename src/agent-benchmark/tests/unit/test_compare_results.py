"""Unit tests for side-by-side comparison logic."""

from agent_benchmark.compare_results import compare_results


class TestCompareResults:
    def test_returns_expected_structure(self):
        result = compare_results({"summary": {}, "tasks": []}, {"summary": {}, "tasks": []})
        assert "agent_a" in result
        assert "agent_b" in result
        assert "per_task_comparison" in result
        assert "aggregate_delta" in result
        assert "category_deltas" in result

    def test_custom_names(self):
        result = compare_results(
            {"summary": {}, "tasks": []},
            {"summary": {}, "tasks": []},
            name_a="openclaw",
            name_b="hermesagent",
        )
        assert "openclaw" in result
        assert "hermesagent" in result

    def test_compares_single_task(self):
        data_a = {
            "summary": {"average_score": 1.0, "successful_tasks": 1, "total_tasks": 1},
            "tasks": [{"task_id": "task_001", "score": 1.0, "status": "success", "elapsed_time": 10.0}],
        }
        data_b = {
            "summary": {"average_score": 0.0, "successful_tasks": 0, "total_tasks": 1},
            "tasks": [{"task_id": "task_001", "score": 0.0, "status": "failed", "elapsed_time": 5.0}],
        }
        result = compare_results(data_a, data_b, "tinycua", "hermes")
        assert len(result["per_task_comparison"]) == 1
        assert result["per_task_comparison"][0]["delta"] == -1.0

    def test_handles_missing_tasks(self):
        data_a = {"summary": {}, "tasks": [{"task_id": "task_001", "score": 1.0, "status": "success"}]}
        data_b = {"summary": {}, "tasks": []}
        result = compare_results(data_a, data_b)
        assert result["per_task_comparison"][0]["delta"] is None

    def test_computes_aggregate_delta(self):
        data_a = {
            "summary": {},
            "tasks": [
                {"task_id": "task_001", "score": 1.0, "status": "success"},
                {"task_id": "task_002", "score": 0.5, "status": "success"},
            ],
        }
        data_b = {
            "summary": {},
            "tasks": [
                {"task_id": "task_001", "score": 1.0, "status": "success"},
                {"task_id": "task_002", "score": 0.0, "status": "failed"},
            ],
        }
        result = compare_results(data_a, data_b)
        assert result["aggregate_delta"] == -0.25

    def test_empty_task_lists(self):
        result = compare_results({"summary": {}, "tasks": []}, {"summary": {}, "tasks": []})
        assert result["per_task_comparison"] == []
        assert result["aggregate_delta"] is None
        assert result["category_deltas"] == {}
