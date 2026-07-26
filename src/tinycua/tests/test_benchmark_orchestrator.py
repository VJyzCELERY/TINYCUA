"""Integration tests for the full benchmark orchestrator.

Tests cover RunMetadata, TaskResult, SummaryAggregate, summary_all.json
output, and preflight_check validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_run_metadata_schema_valid():
    """RunMetadata serialises to a valid JSON structure with all required fields."""
    from tinycua.scripts.benchmark_config import BenchmarkConfig
    from tinycua.scripts.collect_metadata import collect_run_metadata

    config = BenchmarkConfig(
        model_name="test-model", base_url="http://localhost:9999/v1"
    )
    metadata = collect_run_metadata(config)

    assert metadata.run_id  # non-empty string
    assert metadata.local_model_name == "test-model"
    assert metadata.endpoint_url == "http://localhost:9999/v1"
    assert metadata.total_duration_seconds >= 0
    assert isinstance(metadata.cpu_info, str) and len(metadata.cpu_info) > 0
    assert isinstance(metadata.gpu_info, list)
    assert metadata.ram_total_gb > 0
    assert metadata.runtime_version  # non-empty
    assert metadata.python_version  # non-empty


def test_run_metadata_serialises_to_dict():
    """RunMetadata dataclass serialises cleanly to a dict for JSON output."""
    from tinycua.scripts.benchmark_config import BenchmarkConfig
    from tinycua.scripts.collect_metadata import collect_run_metadata

    config = BenchmarkConfig(
        model_name="test-model", base_url="http://localhost:9999/v1"
    )
    metadata = collect_run_metadata(config)

    # Should be convertible to a dict via dataclasses.asdict or manual
    from dataclasses import asdict

    d = asdict(metadata)
    assert isinstance(d, dict)
    assert "run_id" in d
    assert "local_model_name" in d
    assert "endpoint_url" in d
    assert "cpu_info" in d
    assert "gpu_info" in d
    assert "ram_total_gb" in d
    assert "python_version" in d


def test_task_result_schema_valid():
    """TaskResult serialises to the expected JSON shape."""
    from tinycua.scripts.run_benchmark import TaskResult

    result = TaskResult(
        task_id="task_001",
        task_category="Productivity Flow",
        score=0.85,
        status="success",
        elapsed_time=42.5,
        error=None,
        transcript_path="results/task_001/transcript.jsonl",
        usage_path="results/task_001/usage.json",
        log_path="results/task_001/agent.log",
        output_path="results/task_001/output/",
        requests=10,
        total_tokens=5000,
        cost=0.0,
    )

    assert result.task_id == "task_001"
    assert result.status == "success"
    assert result.score == 0.85
    assert result.elapsed_time == 42.5
    assert result.error is None
    assert result.requests == 10
    assert result.total_tokens == 5000
    assert result.cost == 0.0


def test_task_result_serialises_to_dict():
    """TaskResult serialises cleanly to a dict for JSON output."""
    from dataclasses import asdict

    from tinycua.scripts.run_benchmark import TaskResult

    result = TaskResult(
        task_id="task_001",
        task_category="Productivity Flow",
        score=0.85,
        status="success",
        elapsed_time=42.5,
        error=None,
        transcript_path="results/task_001/transcript.jsonl",
        usage_path="results/task_001/usage.json",
        log_path="results/task_001/agent.log",
        output_path="results/task_001/output/",
        requests=10,
        total_tokens=5000,
        cost=0.0,
    )

    d = asdict(result)
    assert isinstance(d, dict)
    assert d["task_id"] == "task_001"
    assert d["score"] == 0.85


def test_summary_aggregate_calculation():
    """SummaryAggregate computes correct statistics from a list of TaskResults."""
    from tinycua.scripts.run_benchmark import SummaryAggregate, TaskResult

    results = [
        TaskResult(
            "t1", "Cat", 0.9, "success", 10.0, None, "", "", "", "", 5, 1000, 0.0
        ),
        TaskResult(
            "t2", "Cat", 0.7, "success", 20.0, None, "", "", "", "", 8, 2000, 0.0
        ),
        TaskResult(
            "t3", "Cat", None, "failed", 30.0, "error", "", "", "", "", 0, None, 0.0
        ),
    ]

    agg = SummaryAggregate.from_task_results(results)

    assert agg.total_tasks == 3
    assert agg.successful_tasks == 2
    assert agg.failed_tasks == 1
    assert agg.skipped_tasks == 0
    assert agg.average_score is not None
    assert abs(agg.average_score - 0.8) < 0.01


def test_summary_aggregate_all_pass():
    """SummaryAggregate handles case where all tasks pass."""
    from tinycua.scripts.run_benchmark import SummaryAggregate, TaskResult

    results = [
        TaskResult(
            "t1", "Cat", 1.0, "success", 10.0, None, "", "", "", "", 5, 1000, 0.0
        ),
        TaskResult(
            "t2", "Cat", 0.9, "success", 15.0, None, "", "", "", "", 6, 1500, 0.0
        ),
    ]

    agg = SummaryAggregate.from_task_results(results)

    assert agg.total_tasks == 2
    assert agg.successful_tasks == 2
    assert agg.failed_tasks == 0
    assert agg.average_score is not None
    assert abs(agg.average_score - 0.95) < 0.01


def test_summary_aggregate_all_fail():
    """SummaryAggregate handles case where all tasks fail."""
    from tinycua.scripts.run_benchmark import SummaryAggregate, TaskResult

    results = [
        TaskResult(
            "t1", "Cat", None, "failed", 10.0, "error1", "", "", "", "", 0, None, 0.0
        ),
        TaskResult(
            "t2", "Cat", None, "timeout", 20.0, "error2", "", "", "", "", 0, None, 0.0
        ),
    ]

    agg = SummaryAggregate.from_task_results(results)

    assert agg.total_tasks == 2
    assert agg.successful_tasks == 0
    assert agg.failed_tasks == 2
    assert agg.average_score is None


def test_summary_aggregate_empty():
    """SummaryAggregate handles empty task list."""
    from tinycua.scripts.run_benchmark import SummaryAggregate

    agg = SummaryAggregate.from_task_results([])

    assert agg.total_tasks == 0
    assert agg.successful_tasks == 0
    assert agg.failed_tasks == 0
    assert agg.average_score is None


def test_summary_all_json_written(tmp_path):
    """run_full_benchmark writes a valid summary_all.json to output_dir."""
    from unittest.mock import MagicMock, patch

    from tinycua.scripts.benchmark_config import BenchmarkConfig
    from tinycua.scripts.run_benchmark import run_full_benchmark

    config = BenchmarkConfig(
        model_name="test-model",
        base_url="http://localhost:9999/v1",
        timeout_seconds=5,
    )

    # Mock TinyCUAAgent to avoid requiring a real LLM endpoint
    mock_agent_class = MagicMock()
    mock_execution = MagicMock()
    mock_execution.elapsed_time = 1.0
    mock_execution.error = None
    mock_agent_class.return_value.run_task.return_value = mock_execution
    mock_agent_class.return_value.collect_usage.return_value = {
        "requests": 1,
        "total_tokens": 100,
        "cost": 0.0,
    }

    with patch("tinycua.scripts.run_benchmark.TinyCUAAgent", mock_agent_class):
        # Run with just 2 tasks to keep it fast
        run_full_benchmark(config, tmp_path, tasks=["t1", "t2"])

    summary_path = tmp_path / "summary_all.json"
    assert summary_path.exists(), "summary_all.json was not written"

    with open(summary_path) as f:
        data = json.load(f)

    assert "metadata" in data, "summary_all.json missing 'metadata' section"
    assert "summary" in data, "summary_all.json missing 'summary' section"
    assert "tasks" in data, "summary_all.json missing 'tasks' section"
    assert isinstance(data["tasks"], list)
    assert len(data["tasks"]) == 2


def test_preflight_check_fails_on_readonly_dir(tmp_path):
    """preflight_check raises PermissionError for a read-only output directory."""
    from tinycua.scripts.collect_metadata import preflight_check

    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(0o444)

    try:
        with pytest.raises(PermissionError):
            preflight_check(readonly)
    finally:
        readonly.chmod(0o755)  # restore for cleanup


def test_preflight_check_passes_on_writable_dir(tmp_path):
    """preflight_check succeeds for a writable output directory."""
    from tinycua.scripts.collect_metadata import preflight_check

    writable = tmp_path / "writable"
    writable.mkdir()
    # Should not raise
    preflight_check(writable)


def test_task_artifacts_preserved(tmp_path):
    """After a task run, transcript.jsonl and usage.json exist in task output dir."""
    from unittest.mock import MagicMock, patch

    from tinycua.scripts.benchmark_config import BenchmarkConfig
    from tinycua.scripts.run_benchmark import run_full_benchmark

    config = BenchmarkConfig(
        model_name="test-model",
        base_url="http://localhost:9999/v1",
        timeout_seconds=5,
    )

    # Mock agent that creates dummy transcript and usage files
    def mock_run_task(spec):
        output_dir = Path(spec.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write dummy transcript
        transcript_path = output_dir / "transcript.jsonl"
        with open(transcript_path, "w") as f:
            f.write('{"type": "llm_request", "usage": {"total_tokens": 100}}\n')

        # Write dummy usage
        usage_path = output_dir / "usage.json"
        with open(usage_path, "w") as f:
            json.dump({"requests": 1, "total_tokens": 100}, f)

        execution = MagicMock()
        execution.elapsed_time = 1.0
        execution.error = None
        return execution

    mock_agent_class = MagicMock()
    mock_agent_class.return_value.run_task.side_effect = mock_run_task
    mock_agent_class.return_value.collect_usage.return_value = {
        "requests": 1,
        "total_tokens": 100,
        "cost": 0.0,
    }

    with patch("tinycua.scripts.run_benchmark.TinyCUAAgent", mock_agent_class):
        run_full_benchmark(config, tmp_path, tasks=["t1"])

    # Check task output dir exists with artifacts
    task_output = tmp_path / "t1"
    assert task_output.exists(), "Task output directory was not created"
    assert (task_output / "transcript.jsonl").exists(), "transcript.jsonl not found"
    assert (task_output / "usage.json").exists(), "usage.json not found"


def test_parse_args_defaults():
    """Default CLI arguments match expected BenchmarkConfig defaults."""
    from tinycua.scripts.benchmark_config import parse_args

    args = parse_args([])
    assert args.model_name == "llama3"
    assert args.base_url == "http://localhost:8000/v1"
    assert args.timeout_seconds == 600
    assert args.tasks is None
    assert args.concurrent_tasks == 1
    assert args.verbose is False


def test_parse_args_overrides():
    """CLI argument overrides are parsed correctly."""
    from tinycua.scripts.benchmark_config import parse_args

    args = parse_args(
        [
            "--model-name",
            "mistral",
            "--base-url",
            "http://10.0.0.1:8080/v1",
            "--timeout-seconds",
            "300",
            "--tasks",
            "task_001,task_002,task_003",
            "--verbose",
        ]
    )
    assert args.model_name == "mistral"
    assert args.base_url == "http://10.0.0.1:8080/v1"
    assert args.timeout_seconds == 300
    assert args.tasks == "task_001,task_002,task_003"
    assert args.verbose is True


def test_categorize_task_known_tasks():
    """All 60 task IDs map to expected WildClawBench categories."""
    from tinycua.scripts.run_benchmark import _categorize_task

    expected_categories = {
        "Productivity Flow",
        "Code Intelligence",
        "Web Navigation",
        "File Operations",
    }

    for i in range(1, 61):
        task_id = f"task_{i:03d}"
        category = _categorize_task(task_id)
        assert category in expected_categories, (
            f"Task {task_id} mapped to unexpected category: {category}"
        )

    # Spot-check boundary tasks
    assert _categorize_task("task_001") == "Productivity Flow"
    assert _categorize_task("task_015") == "Productivity Flow"
    assert _categorize_task("task_016") == "Code Intelligence"
    assert _categorize_task("task_030") == "Code Intelligence"
    assert _categorize_task("task_031") == "Web Navigation"
    assert _categorize_task("task_045") == "Web Navigation"
    assert _categorize_task("task_046") == "File Operations"
    assert _categorize_task("task_060") == "File Operations"


def test_categorize_task_unknown():
    """Unknown task IDs return 'Uncategorized'."""
    from tinycua.scripts.run_benchmark import _categorize_task

    assert _categorize_task("unknown_task") == "Uncategorized"
    assert _categorize_task("task_061") == "Uncategorized"
    assert _categorize_task("") == "Uncategorized"


def test_main_calls_run_full_benchmark():
    """main() parses args and calls run_full_benchmark with correct config."""
    from unittest.mock import MagicMock, patch

    from tinycua.scripts.run_benchmark import main

    mock_run = MagicMock()
    with (
        patch("tinycua.scripts.run_benchmark.run_full_benchmark", mock_run),
        patch(
            "tinycua.scripts.run_benchmark.parse_args",
            return_value=MagicMock(
                model_name="test-model",
                base_url="http://localhost:9999/v1",
                api_key="",
                timeout_seconds=60,
                preserve_artifacts=True,
                verbose=False,
                concurrent_tasks=1,
                output_dir=None,
                tasks="task_001,task_002",
            ),
        ),
    ):
        main()

    mock_run.assert_called_once()
    call_args = mock_run.call_args
    config = call_args[0][0]
    assert config.model_name == "test-model"
    assert call_args[0][2] == ["task_001", "task_002"]
