"""Unit tests for the deterministic artifact evaluator."""

import json
from pathlib import Path

import pytest

from evaluate_artifacts import (
    CheckResult,
    artifact_digest,
    copy_artifact,
    evaluate_artifact,
    parse_agents,
    resolve_adapter,
    summarize_checks,
    write_report,
)


FIXTURES = Path(__file__).parents[1] / "fixtures" / "evaluate_artifacts"


def test_artifact_digest_is_stable_and_copy_isolated(tmp_path: Path) -> None:
    """Copy-side changes never alter the source digest."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "clock.html").write_text("<main>clock</main>")
    before = artifact_digest(source)

    copied = copy_artifact(source, tmp_path / "copies")
    (copied / "clock.html").write_text("changed only in copy")

    assert artifact_digest(source) == before
    assert artifact_digest(copied) != before


def test_summarize_checks_counts_blocked_in_mandatory_total() -> None:
    """Blocked mandatory checks remain visible in the denominator."""
    checks = [
        CheckResult("load", "pass", "loaded"),
        CheckResult("runtime", "fail", "error"),
        CheckResult("reload", "blocked", "browser unavailable"),
    ]

    assert summarize_checks(checks) == {
        "pass": 1,
        "fail": 1,
        "blocked": 1,
        "total": 3,
    }


def test_check_result_rejects_unknown_status() -> None:
    """Result serialization accepts only registered outcome names."""
    with pytest.raises(ValueError, match="status"):
        CheckResult("load", "skipped", "not allowed")


def test_write_report_serializes_all_checks(tmp_path: Path) -> None:
    """Reports retain every mandatory result and evidence reference."""
    checks = [
        CheckResult("load", "pass", "loaded", evidence=("evidence/load.txt",)),
        CheckResult("reload", "blocked", "no browser"),
    ]

    result_path = write_report(
        tmp_path,
        agent="opencode",
        experiment=3,
        source=tmp_path / "artifact",
        digest_before="before",
        digest_after="after",
        adapter="clock:analog-clock.html",
        checks=checks,
    )

    payload = json.loads(result_path.read_text())
    assert payload["summary"] == {"pass": 1, "fail": 0, "blocked": 1, "total": 2}
    assert payload["checks"][0]["evidence"] == ["evidence/load.txt"]
    assert "blocked" in result_path.with_name("summary.md").read_text()


def test_parse_agents_and_explicit_clock_adapter(tmp_path: Path) -> None:
    """Filters reject ambiguity and adapters select only known submitted files."""
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "analog-clock.html").write_text("<main></main>")

    assert parse_agents("opencode,tinycua") == ("opencode", "tinycua")
    assert resolve_adapter("opencode", 3, artifact).name == "clock:analog-clock.html"
    with pytest.raises(ValueError, match="duplicate"):
        parse_agents("opencode,opencode")
    with pytest.raises(ValueError, match="unsupported"):
        resolve_adapter("tinycua", 3, artifact)


def test_broken_fixture_records_each_contract_check(tmp_path: Path) -> None:
    """An unsupported submitted layout fails every required check visibly."""
    source = FIXTURES / "broken" / "experiment-3"

    report = json.loads(
        evaluate_artifact("opencode", 3, source, tmp_path / "output").read_text()
    )

    assert [check["name"] for check in report["checks"]] == [
        "load",
        "runtime-errors",
        "visible-clock",
        "time-update",
        "reload",
    ]
    assert {check["status"] for check in report["checks"]} == {"fail"}


def test_known_good_fixtures_match_registered_layouts() -> None:
    """Known-good clock and application fixtures use only supported mappings."""
    clock = FIXTURES / "good" / "experiment-3"
    app = FIXTURES / "good" / "experiment-4"

    assert resolve_adapter("opencode", 3, clock).entrypoint.name == "analog-clock.html"
    assert resolve_adapter("opencode", 4, app).entrypoint.name == "app.py"
