"""Unit tests for the deterministic artifact evaluator."""

import json
import sys
from pathlib import Path
from threading import Thread
from types import ModuleType, SimpleNamespace

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
import evaluate_artifacts as evaluator


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


def test_experiment_four_uses_declared_dependency_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Artifact commands use the interpreter that installed requirements."""
    workspace = tmp_path / "artifact"
    workspace.mkdir()
    manifest = workspace / "requirements.txt"
    manifest.write_text("example-dependency\n")
    commands: list[tuple[str, ...]] = []

    def fake_run(
        name: str,
        command: tuple[str, ...],
        _workspace: Path,
        _evidence: Path,
        timeout: int = 90,
    ) -> CheckResult:
        del timeout
        commands.append(command)
        return CheckResult(name, "pass", "installed")

    monkeypatch.setattr(evaluator, "run_command", fake_run)

    interpreter, dependency = evaluator._prepare_environment(
        workspace, tmp_path / "evidence", manifest
    )

    assert dependency.status == "pass"
    assert interpreter == workspace / ".evaluator-venv" / "bin" / "python"
    assert commands == [
        (sys.executable, "-m", "venv", str(interpreter.parent.parent)),
        (
            str(interpreter),
            "-m",
            "pip",
            "install",
            "uvicorn",
            "-r",
            str(manifest),
        ),
    ]


def test_flask_adapter_starts_with_its_registered_server(tmp_path: Path) -> None:
    """Flask artifacts use the WSGI launcher rather than Uvicorn."""
    artifact = tmp_path / "artifact"
    backend = artifact / "backend"
    backend.mkdir(parents=True)
    (backend / "app.py").touch()

    command = evaluator._server_command(
        resolve_adapter("opencode", 4, artifact), Path("/venv/bin/python"), 8765
    )

    assert command == (
        "/venv/bin/python",
        "-m",
        "flask",
        "--app",
        "app:app",
        "run",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
    )


def test_experiment_four_serves_submitted_frontend_and_exercises_block_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registered frontend is served instead of browsing a backend root."""
    artifact = tmp_path / "artifact"
    backend = artifact / "backend"
    frontend = artifact / "frontend"
    backend.mkdir(parents=True)
    frontend.mkdir()
    (backend / "app.py").touch()
    (frontend / "index.html").write_text("<button>add block</button>")
    (artifact / "requirements.txt").touch()
    adapter = resolve_adapter("opencode", 4, artifact)
    served: list[Path] = []

    def fake_prepare(
        _workspace: Path, _evidence: Path, _manifest: Path
    ) -> tuple[Path, CheckResult]:
        return Path("/venv/bin/python"), CheckResult("dependency-install", "pass", "")

    def fake_command(
        name: str,
        command: tuple[str, ...],
        workspace: Path,
        evidence: Path,
        timeout: int = 90,
    ) -> CheckResult:
        del command, workspace, evidence, timeout
        return CheckResult(name, "pass", "")

    def fake_server(
        _adapter: evaluator.Adapter, _evidence: Path, _interpreter: Path
    ) -> CheckResult:
        return CheckResult("backend-startup", "pass", "")

    def fake_frontend(
        served_adapter: evaluator.Adapter,
    ) -> tuple[object, Thread, evaluator.Adapter]:
        served.append(served_adapter.frontend)
        return SimpleNamespace(shutdown=lambda: None), Thread(), served_adapter

    monkeypatch.setattr(evaluator, "_prepare_environment", fake_prepare)
    monkeypatch.setattr(evaluator, "run_command", fake_command)
    monkeypatch.setattr(evaluator, "_run_server", fake_server)
    monkeypatch.setattr(evaluator, "_start_server", lambda *_: (object(), (), adapter))
    monkeypatch.setattr(evaluator, "_stop_server", lambda _: "")
    monkeypatch.setattr(evaluator, "_serve_frontend", fake_frontend)
    monkeypatch.setattr(
        evaluator,
        "_browser_checks",
        lambda *_: [
            CheckResult("page-block", "pass", ""),
            CheckResult("browser-e2e", "pass", ""),
        ],
    )

    results = evaluator._experiment_four(adapter, artifact, tmp_path / "evidence")

    assert served == [frontend]
    assert results[-2].name == "page-block"


def test_submitted_browser_failure_is_not_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Page failures are artifact failures once Chromium has launched."""
    browser = SimpleNamespace(close=lambda: None)
    playwright = SimpleNamespace(chromium=SimpleNamespace(launch=lambda: browser))

    class PlaywrightContext:
        def __enter__(self) -> SimpleNamespace:
            return playwright

        def __exit__(self, *_: object) -> None:
            return None

    sync_api = ModuleType("playwright.sync_api")
    sync_api.sync_playwright = PlaywrightContext
    monkeypatch.setitem(sys.modules, "playwright", ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    adapter = evaluator.Adapter("test", tmp_path, tmp_path / "index.html")
    results = evaluator._browser_checks(adapter, tmp_path / "evidence", 4)

    assert {result.status for result in results} == {"fail"}
    assert all(
        "browser runtime unavailable" not in result.message for result in results
    )


def test_report_evidence_paths_resolve_from_report_directory(tmp_path: Path) -> None:
    """Command evidence paths resolve relative to their result report."""
    result = evaluator.run_command(
        "command", (sys.executable, "-c", ""), tmp_path, tmp_path / "evidence"
    )

    assert result.evidence == ("evidence/commands/command.log",)
    assert (tmp_path / result.evidence[0]).is_file()
