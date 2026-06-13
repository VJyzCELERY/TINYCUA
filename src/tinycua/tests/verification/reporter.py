"""Result collection and reporting for the verification gate.

Generates JSON and human-readable summary reports from path execution results.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class PathResult:
    """Result of running a single architecture path.

    Attributes:
        path_name: Name of the path.
        status: "pass", "fail", "timeout", or "error".
        duration_seconds: Execution time in seconds.
        llm_interactions: Full LLM interaction log.
        node_outputs: Output from each node.
        session_state: Final session state snapshot.
        error: Error message if failed.
        error_traceback: Full traceback if exception.
    """

    path_name: str
    status: str = "error"
    duration_seconds: float = 0.0
    llm_interactions: list[dict[str, Any]] = field(default_factory=list)
    node_outputs: dict[str, Any] = field(default_factory=dict)
    session_state: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_traceback: str | None = None


@dataclass
class VerificationReport:
    """Aggregated results of all architecture paths.

    Attributes:
        overall_status: "pass" or "fail".
        total_paths: Total number of paths.
        passed: Count of passing paths.
        failed: Count of failing paths.
        timed_out: Count of timed-out paths.
        path_results: Per-path results.
        summary: Human-readable summary.
        timestamp: ISO 8601 timestamp.
        llm_model: Model used for verification.
    """

    overall_status: str = "fail"
    total_paths: int = 0
    passed: int = 0
    failed: int = 0
    timed_out: int = 0
    errored: int = 0
    path_results: list[PathResult] = field(default_factory=list)
    summary: str = ""
    timestamp: str = ""
    llm_model: str = ""


class ReportGenerator:
    """Generates human-readable and machine-readable reports."""

    def generate_json(self, report: VerificationReport) -> str:
        """Generate JSON output from a VerificationReport.

        Args:
            report: The verification report to serialize.

        Returns:
            JSON string with all report fields.
        """
        data = {
            "overall_status": report.overall_status,
            "total_paths": report.total_paths,
            "passed": report.passed,
            "failed": report.failed,
            "timed_out": report.timed_out,
            "errored": report.errored,
            "timestamp": report.timestamp,
            "llm_model": report.llm_model,
            "path_results": [
                {
                    "path_name": pr.path_name,
                    "status": pr.status,
                    "duration_seconds": round(pr.duration_seconds, 3),
                    "error": pr.error,
                    "node_outputs": {
                        k: str(v) for k, v in pr.node_outputs.items()
                    },
                    "llm_interaction_count": len(pr.llm_interactions),
                }
                for pr in report.path_results
            ],
        }
        return json.dumps(data, indent=2)

    def generate_summary(self, report: VerificationReport) -> str:
        """Generate human-readable summary from a VerificationReport.

        Args:
            report: The verification report to summarize.

        Returns:
            Multi-line summary string.
        """
        lines = [
            "=" * 60,
            "ARCHITECTURE VERIFICATION GATE REPORT",
            "=" * 60,
            f"Timestamp: {report.timestamp}",
            f"Model: {report.llm_model}",
            f"Overall Status: {report.overall_status.upper()}",
            "",
            f"Total: {report.total_paths}  |  "
            f"Passed: {report.passed}  |  "
            f"Failed: {report.failed}  |  "
            f"Timed Out: {report.timed_out}  |  "
            f"Errored: {report.errored}",
            "",
            "-" * 60,
            "PER-PATH RESULTS",
            "-" * 60,
        ]

        for pr in report.path_results:
            status_icon = {
                "pass": "PASS",
                "fail": "FAIL",
                "timeout": "TIMEOUT",
                "error": "ERROR",
            }.get(pr.status, "UNKNOWN")

            lines.append(
                f"  [{status_icon}] {pr.path_name} "
                f"({pr.duration_seconds:.1f}s)"
            )
            if pr.error:
                lines.append(f"         Error: {pr.error}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


def create_error_result(path_name: str, error: Exception) -> PathResult:
    """Create a PathResult for a path that raised an exception.

    Args:
        path_name: Name of the failed path.
        error: The exception that occurred.

    Returns:
        PathResult with error status and traceback.
    """
    return PathResult(
        path_name=path_name,
        status="error",
        error=str(error),
        error_traceback=traceback.format_exc(),
    )


def create_timeout_result(path_name: str, timeout: float) -> PathResult:
    """Create a PathResult for a path that timed out.

    Args:
        path_name: Name of the timed-out path.
        timeout: The timeout value in seconds.

    Returns:
        PathResult with timeout status.
    """
    return PathResult(
        path_name=path_name,
        status="timeout",
        error=f"Path exceeded timeout of {timeout}s",
    )


def build_report(
    path_results: list[PathResult],
    llm_model: str,
) -> VerificationReport:
    """Build a VerificationReport from a list of PathResults.

    Args:
        path_results: Results from all path executions.
        llm_model: The model used for verification.

    Returns:
        Aggregated VerificationReport.
    """
    passed = sum(1 for pr in path_results if pr.status == "pass")
    failed = sum(1 for pr in path_results if pr.status == "fail")
    timed_out = sum(1 for pr in path_results if pr.status == "timeout")
    errored = sum(1 for pr in path_results if pr.status == "error")
    total = len(path_results)
    overall = "pass" if failed == 0 and errored == 0 and timed_out == 0 else "fail"

    report = VerificationReport(
        overall_status=overall,
        total_paths=total,
        passed=passed,
        failed=failed,
        timed_out=timed_out,
        errored=errored,
        path_results=path_results,
        llm_model=llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    report.summary = ReportGenerator().generate_summary(report)
    return report
