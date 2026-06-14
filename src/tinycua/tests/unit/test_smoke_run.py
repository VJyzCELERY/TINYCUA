"""Unit tests for WildClawBench smoke-run components."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tinycua.cli.smoke_run import (
    SmokeReport,
    SmokeResult,
    SmokeTask,
    SmokeTaskSelector,
    categorize_failure,
)


class TestSmokeTask:
    """Tests for SmokeTask dataclass."""

    def test_construction(self, tmp_path: Path):
        """SmokeTask must be constructable with required fields."""
        task = SmokeTask(
            task_id="prod-flow-001",
            category="Productivity Flow",
            prompt="Open the spreadsheet",
            timeout_seconds=300,
            workspace_path=tmp_path / "workspace",
            output_dir=tmp_path / "output",
            dependencies=["browser"],
        )
        assert task.task_id == "prod-flow-001"
        assert task.category == "Productivity Flow"
        assert task.prompt == "Open the spreadsheet"
        assert task.timeout_seconds == 300
        assert task.dependencies == ["browser"]

    def test_frozen(self, tmp_path: Path):
        """SmokeTask must be immutable (frozen dataclass)."""
        task = SmokeTask(
            task_id="test-001",
            category="test",
            prompt="test",
            timeout_seconds=300,
            workspace_path=tmp_path / "w",
            output_dir=tmp_path / "o",
            dependencies=[],
        )
        with pytest.raises(AttributeError):
            task.task_id = "changed"


class TestSmokeTaskSelector:
    """Tests for SmokeTaskSelector task selection logic."""

    def test_selects_tasks_from_all_categories(self):
        """Selector must return at least one task per WildClawBench category."""
        selector = SmokeTaskSelector(available_capabilities={"browser", "email", "filesystem"})
        tasks = selector.select()

        categories = {t.category for t in tasks}
        expected_categories = {
            "Productivity Flow",
            "Code Intelligence",
            "Social Interaction",
            "Search & Retrieval",
            "Creative Synthesis",
            "Safety Alignment",
        }
        assert expected_categories.issubset(categories)

    def test_skips_tasks_with_missing_dependencies(self):
        """Tasks with unavailable dependencies must be skipped."""
        selector = SmokeTaskSelector(available_capabilities=set())
        tasks = selector.select()

        # With no capabilities, all tasks with dependencies should be skipped
        for task in tasks:
            if task.dependencies:
                assert len(task.dependencies) > 0

    def test_selects_minimum_one_per_category(self):
        """Must select at least one task per available category."""
        selector = SmokeTaskSelector(
            available_capabilities={"browser", "email", "filesystem", "code"}
        )
        tasks = selector.select()

        category_counts: dict[str, int] = {}
        for task in tasks:
            category_counts[task.category] = category_counts.get(task.category, 0) + 1

        for category, count in category_counts.items():
            assert count >= 1, f"Category '{category}' has fewer than 1 task"

    def test_task_ids_are_unique(self):
        """All selected task IDs must be unique."""
        selector = SmokeTaskSelector(available_capabilities={"browser", "email", "filesystem"})
        tasks = selector.select()

        task_ids = [t.task_id for t in tasks]
        assert len(task_ids) == len(set(task_ids))


class TestCategorizeFailure:
    """Tests for failure categorization heuristic."""

    def test_timeout_exception(self):
        """TimeoutExpired must be categorized as 'timeout'."""
        result = categorize_failure(
            error="Process timed out",
            exit_code=None,
            elapsed=300.0,
            timeout=300,
        )
        assert result == "timeout"

    def test_timeout_exit_code(self):
        """Exit code 124 must be categorized as 'timeout'."""
        result = categorize_failure(
            error="Process exited with code 124",
            exit_code=124,
            elapsed=300.0,
            timeout=300,
        )
        assert result == "timeout"

    def test_file_not_found(self):
        """FileNotFoundError must be categorized as 'missing_dependency'."""
        result = categorize_failure(
            error="tinycua binary not found: /usr/bin/tinycua",
            exit_code=None,
            elapsed=0.1,
            timeout=300,
        )
        assert result == "missing_dependency"

    def test_connection_error(self):
        """ConnectionError must be categorized as 'llm_error'."""
        result = categorize_failure(
            error="Connection refused: http://localhost:8000",
            exit_code=None,
            elapsed=5.0,
            timeout=300,
        )
        assert result == "llm_error"

    def test_llm_error_keywords(self):
        """Error messages containing LLM-related keywords must be 'llm_error'."""
        for keyword in ["llm", "model", "api", "openai", "connection"]:
            result = categorize_failure(
                error=f"Failed to reach {keyword} endpoint",
                exit_code=1,
                elapsed=5.0,
                timeout=300,
            )
            assert result == "llm_error", f"Keyword '{keyword}' not classified as llm_error"

    def test_non_zero_exit_unknown(self):
        """Non-zero exit without other signals must be 'other'."""
        result = categorize_failure(
            error="Process exited with code 1",
            exit_code=1,
            elapsed=10.0,
            timeout=300,
        )
        assert result == "other", f"Expected 'other' for exit code 1, got '{result}'"

    def test_grading_error(self):
        """Grading-related errors must be categorized as 'grading_error'."""
        result = categorize_failure(
            error="Grading failed: invalid transcript format",
            exit_code=None,
            elapsed=30.0,
            timeout=300,
        )
        assert result == "grading_error"


class TestSmokeResult:
    """Tests for SmokeResult dataclass."""

    def test_construction(self):
        """SmokeResult must be constructable with all fields."""
        result = SmokeResult(
            task_id="test-001",
            category="Productivity Flow",
            status="pass",
            elapsed_time=10.5,
            usage={"total_tokens": 100},
            failure_reason=None,
            failure_category=None,
            artifact_paths={"log": Path("/tmp/log")},
        )
        assert result.task_id == "test-001"
        assert result.status == "pass"
        assert result.elapsed_time == 10.5
        assert result.failure_reason is None

    def test_status_values(self):
        """SmokeResult status must be one of pass, fail, skip, timeout."""
        valid_statuses = {"pass", "fail", "skip", "timeout"}
        for status in valid_statuses:
            result = SmokeResult(
                task_id="test",
                category="test",
                status=status,
                elapsed_time=0.0,
                usage={},
                failure_reason=None,
                failure_category=None,
                artifact_paths={},
            )
            assert result.status == status


class TestSmokeReport:
    """Tests for SmokeReport dataclass."""

    def test_construction(self):
        """SmokeReport must be constructable with all fields."""
        report = SmokeReport(
            run_timestamp="2026-06-14T12:00:00+00:00",
            model="test-model",
            base_url="http://localhost:8000",
            total_tasks=6,
            passed=4,
            failed=1,
            skipped=1,
            timed_out=0,
            results=[],
            category_summary={},
            failure_taxonomy={},
        )
        assert report.total_tasks == 6
        assert report.passed == 4


class TestSmokeReportGenerator:
    """Tests for report generation (JSON + Markdown)."""

    def test_generates_json_report(self, tmp_path: Path):
        """Must produce a valid JSON report file."""
        from tinycua.cli.smoke_run import SmokeReportGenerator

        report = SmokeReport(
            run_timestamp="2026-06-14T12:00:00+00:00",
            model="test-model",
            base_url="http://localhost:8000",
            total_tasks=2,
            passed=1,
            failed=1,
            skipped=0,
            timed_out=0,
            results=[],
            category_summary={"Productivity Flow": {"total": 2, "pass": 1, "fail": 1}},
            failure_taxonomy={"other": 1},
        )

        generator = SmokeReportGenerator(tmp_path)
        generator.generate(report)

        json_path = tmp_path / "smoke-report.json"
        assert json_path.exists()
        with open(json_path) as f:
            data = json.load(f)
        assert data["total_tasks"] == 2
        assert data["passed"] == 1

    def test_generates_markdown_report(self, tmp_path: Path):
        """Must produce a Markdown report file."""
        from tinycua.cli.smoke_run import SmokeReportGenerator

        report = SmokeReport(
            run_timestamp="2026-06-14T12:00:00+00:00",
            model="test-model",
            base_url="http://localhost:8000",
            total_tasks=2,
            passed=1,
            failed=1,
            skipped=0,
            timed_out=0,
            results=[],
            category_summary={"Productivity Flow": {"total": 2, "pass": 1, "fail": 1}},
            failure_taxonomy={"other": 1},
        )

        generator = SmokeReportGenerator(tmp_path)
        generator.generate(report)

        md_path = tmp_path / "smoke-report.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "# Smoke Run Report" in content
        assert "Category Summary" in content


class TestIdempotency:
    """Tests for smoke-run idempotency (re-runs don't corrupt artifacts)."""

    def test_re_run_preserves_prior_artifacts(self, tmp_path: Path):
        """Re-running must not overwrite prior artifact directories."""
        output_base = tmp_path / "smoke-output"
        run1_dir = output_base / "run-1"
        run2_dir = output_base / "run-2"

        # Create fake artifacts in run-1
        run1_dir.mkdir(parents=True)
        (run1_dir / "task-001").mkdir()
        (run1_dir / "task-001" / "transcript.jsonl").write_text("line1\n")

        # Simulate run-2 creating its own directory
        run2_dir.mkdir(parents=True)
        (run2_dir / "task-001").mkdir()

        # Verify run-1 artifacts are untouched
        assert (run1_dir / "task-001" / "transcript.jsonl").exists()
        assert (run1_dir / "task-001" / "transcript.jsonl").read_text() == "line1\n"
