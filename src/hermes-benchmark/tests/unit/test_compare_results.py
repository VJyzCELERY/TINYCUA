"""Unit tests for side-by-side comparison logic."""

from hermes_benchmark.compare_results import compare_results


class TestCompareResults:
    """Tests for compare_results function."""

    def test_returns_expected_structure(self):
        """compare_results must return dict with expected top-level keys."""
        tinycua = {"summary": {}, "tasks": []}
        hermes = {"summary": {}, "tasks": []}
        result = compare_results(tinycua, hermes)

        assert "agent_a" in result
        assert "agent_b" in result
        assert "per_task_comparison" in result
        assert "aggregate_delta" in result
        assert "category_deltas" in result

    def test_agent_names_are_correct(self):
        """agent_a must be named tinycua, agent_b must be named hermes."""
        tinycua = {"summary": {}, "tasks": []}
        hermes = {"summary": {}, "tasks": []}
        result = compare_results(tinycua, hermes)

        assert result["agent_a"]["name"] == "tinycua"
        assert result["agent_b"]["name"] == "hermes"

    def test_compares_single_task(self):
        """Per-task comparison must include both scores and delta."""
        tinycua = {
            "summary": {"average_score": 1.0, "successful_tasks": 1, "total_tasks": 1},
            "tasks": [{"task_id": "task_001", "score": 1.0, "status": "success", "elapsed_time": 10.0}],
        }
        hermes = {
            "summary": {"average_score": 0.0, "successful_tasks": 0, "total_tasks": 1},
            "tasks": [{"task_id": "task_001", "score": 0.0, "status": "failed", "elapsed_time": 5.0}],
        }
        result = compare_results(tinycua, hermes)

        assert len(result["per_task_comparison"]) == 1
        entry = result["per_task_comparison"][0]
        assert entry["task_id"] == "task_001"
        assert entry["tinycua_score"] == 1.0
        assert entry["hermes_score"] == 0.0
        assert entry["delta"] == -1.0

    def test_compares_multiple_tasks(self):
        """Multiple tasks must all appear in per_task_comparison."""
        tinycua = {
            "summary": {},
            "tasks": [
                {"task_id": "task_001", "score": 1.0, "status": "success"},
                {"task_id": "task_002", "score": 0.0, "status": "failed"},
            ],
        }
        hermes = {
            "summary": {},
            "tasks": [
                {"task_id": "task_001", "score": 1.0, "status": "success"},
                {"task_id": "task_002", "score": 1.0, "status": "success"},
            ],
        }
        result = compare_results(tinycua, hermes)

        assert len(result["per_task_comparison"]) == 2
        deltas = {e["task_id"]: e["delta"] for e in result["per_task_comparison"]}
        assert deltas["task_001"] == 0.0
        assert deltas["task_002"] == 1.0

    def test_handles_missing_tasks(self):
        """Tasks missing in one result set must still appear with nulls."""
        tinycua = {
            "summary": {},
            "tasks": [{"task_id": "task_001", "score": 1.0, "status": "success"}],
        }
        hermes = {
            "summary": {},
            "tasks": [],
        }
        result = compare_results(tinycua, hermes)

        assert len(result["per_task_comparison"]) == 1
        entry = result["per_task_comparison"][0]
        assert entry["task_id"] == "task_001"
        assert entry["tinycua_score"] == 1.0
        assert entry["hermes_score"] is None
        assert entry["delta"] is None

    def test_computes_aggregate_delta(self):
        """aggregate_delta must be hermes average minus tinycua average."""
        tinycua = {
            "summary": {"average_score": 0.75, "successful_tasks": 45},
            "tasks": [
                {"task_id": "task_001", "score": 1.0, "status": "success"},
                {"task_id": "task_002", "score": 0.5, "status": "success"},
            ],
        }
        hermes = {
            "summary": {"average_score": 0.50, "successful_tasks": 30},
            "tasks": [
                {"task_id": "task_001", "score": 1.0, "status": "success"},
                {"task_id": "task_002", "score": 0.0, "status": "failed"},
            ],
        }
        result = compare_results(tinycua, hermes)

        # tinycua avg: (1.0 + 0.5) / 2 = 0.75
        # hermes avg: (1.0 + 0.0) / 2 = 0.50
        # delta: 0.50 - 0.75 = -0.25
        assert result["aggregate_delta"] == -0.25

    def test_computes_category_deltas(self):
        """Category deltas must group tasks by category."""
        tinycua = {
            "summary": {},
            "tasks": [
                {"task_id": "task_001", "score": 1.0, "status": "success", "task_category": "Productivity Flow"},
                {"task_id": "task_016", "score": 0.0, "status": "failed", "task_category": "Code Intelligence"},
            ],
        }
        hermes = {
            "summary": {},
            "tasks": [
                {"task_id": "task_001", "score": 0.5, "status": "success", "task_category": "Productivity Flow"},
                {"task_id": "task_016", "score": 0.5, "status": "success", "task_category": "Code Intelligence"},
            ],
        }
        result = compare_results(tinycua, hermes)

        cats = result["category_deltas"]
        assert "Productivity Flow" in cats
        assert "Code Intelligence" in cats
        assert cats["Productivity Flow"]["delta"] == -0.5
        assert cats["Code Intelligence"]["delta"] == 0.5

    def test_aggregate_delta_none_for_no_scores(self):
        """aggregate_delta must be None when no tasks have scores."""
        tinycua = {
            "summary": {},
            "tasks": [{"task_id": "task_001", "score": None, "status": "error"}],
        }
        hermes = {
            "summary": {},
            "tasks": [],
        }
        result = compare_results(tinycua, hermes)
        assert result["aggregate_delta"] is None

    def test_empty_task_lists(self):
        """compare_results must handle empty task lists gracefully."""
        tinycua = {"summary": {}, "tasks": []}
        hermes = {"summary": {}, "tasks": []}
        result = compare_results(tinycua, hermes)

        assert result["per_task_comparison"] == []
        assert result["aggregate_delta"] is None
        assert result["category_deltas"] == {}

    def test_agent_summary_metadata(self):
        """Agent summary metadata must include name, avg score, successful tasks, total."""
        tinycua = {
            "summary": {"average_score": 0.8, "successful_tasks": 48, "total_tasks": 60},
            "tasks": [],
        }
        hermes = {
            "summary": {"average_score": 0.6, "successful_tasks": 36, "total_tasks": 60},
            "tasks": [],
        }
        result = compare_results(tinycua, hermes)

        assert result["agent_a"]["average_score"] == 0.8
        assert result["agent_a"]["successful_tasks"] == 48
        assert result["agent_a"]["total_tasks"] == 60
        assert result["agent_b"]["average_score"] == 0.6
        assert result["agent_b"]["successful_tasks"] == 36
        assert result["agent_b"]["total_tasks"] == 60
