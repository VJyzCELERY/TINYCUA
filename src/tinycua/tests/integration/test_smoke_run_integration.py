"""Integration tests for WildClawBench smoke-run orchestration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tinycua.cli.smoke_run import (
    SmokeReport,
    SmokeRunOrchestrator,
)


@pytest.fixture
def output_base(tmp_path: Path) -> Path:
    """Provide a temporary output base directory."""
    return tmp_path / "smoke-output"


@pytest.fixture
def mock_run_success():
    """Fixture that mocks subprocess.run to simulate successful execution.

    Creates transcript.jsonl, agent.log, and usage.json in the task output
    directory to simulate what tinycua run would produce.
    """

    def _mock_run(cmd, **kwargs):
        # Simulate tinycua writing output files
        output_dir = _extract_output_dir(cmd)
        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            transcript = out / "transcript.jsonl"
            log = out / "agent.log"
            usage = out / "usage.json"
            transcript.write_text(
                json.dumps({"type": "llm.request", "usage": {"total_tokens": 10}})
                + "\n"
            )
            log.write_text("task completed\n")
            usage.write_text(
                json.dumps(
                    {
                        "input_tokens": 5,
                        "output_tokens": 5,
                        "total_tokens": 10,
                        "cost_usd": 0.0,
                        "request_count": 1,
                        "elapsed_time": 0.5,
                    }
                )
            )

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="",
            stderr="",
        )

    return _mock_run


@pytest.fixture
def mock_run_fail():
    """Fixture that mocks subprocess.run to simulate task failure."""

    def _mock_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr="error output",
        )

    return _mock_run


def _extract_output_dir(cmd):
    """Extract --output-dir value from command."""
    try:
        idx = cmd.index("--output-dir")
        return cmd[idx + 1]
    except (ValueError, IndexError):
        return None


class TestSmokeRunProducesReport:
    """Integration tests for end-to-end smoke run producing a report."""

    def test_smoke_run_produces_report_with_all_categories(
        self, output_base: Path, mock_run_success
    ):
        """Smoke run with mock agent produces a report covering all categories."""
        with patch("subprocess.run", mock_run_success):
            orchestrator = SmokeRunOrchestrator(
                model="test-model",
                base_url="http://localhost:8000",
                api_key="test-key",
                output_base=output_base,
                timeout=5,
                mode="local",
                available_capabilities={"browser", "email", "filesystem", "code"},
            )
            report = orchestrator.run()

        assert isinstance(report, SmokeReport)
        assert report.total_tasks >= 6  # one per category minimum
        assert len(report.category_summary) >= 6
        for category in report.category_summary:
            assert report.category_summary[category]["total"] >= 1

    def test_smoke_run_collects_artifacts_per_task(
        self, output_base: Path, mock_run_success
    ):
        """Each attempted smoke task produces agent.log, transcript.jsonl, usage.json."""
        with patch("subprocess.run", mock_run_success):
            orchestrator = SmokeRunOrchestrator(
                model="test-model",
                base_url="http://localhost:8000",
                api_key="test-key",
                output_base=output_base,
                timeout=5,
                mode="local",
                available_capabilities={"browser", "email", "filesystem", "code"},
            )
            report = orchestrator.run()

        for result in report.results:
            if result.status in ("pass", "fail", "timeout"):
                assert result.artifact_paths.get("log") is not None
                assert result.artifact_paths.get("transcript") is not None
                assert result.artifact_paths.get("usage") is not None
                assert result.usage is not None

    def test_smoke_run_skips_unavailable_dependencies(
        self, output_base: Path, mock_run_success
    ):
        """Tasks with missing dependencies are excluded from selection."""
        with patch("subprocess.run", mock_run_success):
            # With no capabilities, the Search & Retrieval task (needs filesystem) is excluded
            orchestrator_no_caps = SmokeRunOrchestrator(
                model="test-model",
                base_url="http://localhost:8000",
                api_key="test-key",
                output_base=output_base / "no-caps",
                timeout=5,
                mode="local",
                available_capabilities=set(),
            )
            report_no_caps = orchestrator_no_caps.run()

            # With all capabilities, all 6 categories are covered
            orchestrator_all_caps = SmokeRunOrchestrator(
                model="test-model",
                base_url="http://localhost:8000",
                api_key="test-key",
                output_base=output_base / "all-caps",
                timeout=5,
                mode="local",
                available_capabilities={"browser", "email", "filesystem", "code"},
            )
            report_all_caps = orchestrator_all_caps.run()

        # Fewer tasks selected when capabilities are unavailable
        assert report_no_caps.total_tasks < report_all_caps.total_tasks
        # Search & Retrieval task should be missing from no-caps run
        no_caps_categories = {r.category for r in report_no_caps.results}
        all_caps_categories = {r.category for r in report_all_caps.results}
        assert "Search & Retrieval" not in no_caps_categories
        assert "Search & Retrieval" in all_caps_categories

    def test_smoke_run_report_json_and_markdown(
        self, output_base: Path, mock_run_success
    ):
        """Smoke run produces both JSON and Markdown summary reports."""
        with patch("subprocess.run", mock_run_success):
            orchestrator = SmokeRunOrchestrator(
                model="test-model",
                base_url="http://localhost:8000",
                api_key="test-key",
                output_base=output_base,
                timeout=5,
                mode="local",
                available_capabilities={"browser", "email", "filesystem", "code"},
            )
            orchestrator.run()

        json_path = output_base / "smoke-report.json"
        md_path = output_base / "smoke-report.md"
        assert json_path.exists()
        assert md_path.exists()

        # Verify JSON report content
        with open(json_path) as f:
            json_data = json.load(f)
        assert "total_tasks" in json_data
        assert "passed" in json_data
        assert "failed" in json_data
        assert "results" in json_data
        assert "category_summary" in json_data
        assert "failure_taxonomy" in json_data

        # Verify Markdown report content
        md_content = md_path.read_text()
        assert "# Smoke Run Report" in md_content
        assert "Category Summary" in md_content

    def test_smoke_run_handles_task_failure(self, output_base: Path, mock_run_fail):
        """Smoke run handles individual task failures without aborting."""
        with patch("subprocess.run", mock_run_fail):
            orchestrator = SmokeRunOrchestrator(
                model="test-model",
                base_url="http://localhost:8000",
                api_key="test-key",
                output_base=output_base,
                timeout=5,
                mode="local",
                available_capabilities={"browser", "email", "filesystem", "code"},
            )
            report = orchestrator.run()

        # All tasks should complete (some may fail), not abort
        assert report.total_tasks >= 6
        failed = [r for r in report.results if r.status == "fail"]
        assert len(failed) > 0
        for result in failed:
            assert result.failure_reason is not None

    def test_transcript_jsonl_format_is_valid(
        self, output_base: Path, mock_run_success
    ):
        """transcript.jsonl must be valid JSONL with parseable JSON per line."""
        with patch("subprocess.run", mock_run_success):
            orchestrator = SmokeRunOrchestrator(
                model="test-model",
                base_url="http://localhost:8000",
                api_key="test-key",
                output_base=output_base,
                timeout=5,
                mode="local",
                available_capabilities={"browser", "email", "filesystem", "code"},
            )
            report = orchestrator.run()

        for result in report.results:
            if result.status in ("pass", "fail", "timeout"):
                transcript_path = result.artifact_paths.get("transcript")
                if transcript_path:
                    path = Path(transcript_path)
                    assert path.exists(), (
                        f"transcript.jsonl missing for {result.task_id}"
                    )
                    lines = path.read_text().strip().splitlines()
                    assert len(lines) > 0, (
                        f"transcript.jsonl empty for {result.task_id}"
                    )
                    for i, line in enumerate(lines):
                        parsed = json.loads(line)
                        assert isinstance(parsed, dict), (
                            f"transcript.jsonl line {i} is not a JSON object for {result.task_id}"
                        )
