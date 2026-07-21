"""Unit tests for the deterministic artifact evaluator."""

import json
import sys
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def test_report_labels_deterministic_functional_correctness(tmp_path: Path) -> None:
    """Reports label the aggregate without implying a sampling metric."""
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
    assert payload["functional_correctness"] == {
        "label": "Functional Correctness (deterministic single-run)",
        "pass": 1,
        "fail": 0,
        "blocked": 1,
        "total": 2,
    }
    assert "Pass@1" not in json.dumps(payload)
    assert payload["checks"][0]["evidence"] == ["evidence/load.txt"]
    summary = result_path.with_name("summary.md").read_text()
    assert "Functional Correctness (deterministic single-run)" in summary
    assert "Pass@1" not in summary


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
        (sys.executable, "-m", "venv", str(interpreter.parent.parent.resolve())),
        (
            str(interpreter),
            "-m",
            "pip",
            "install",
            "uvicorn",
            "-r",
            str(manifest.resolve()),
        ),
    ]


def test_relative_output_root_uses_existing_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dependency installation receives an absolute copied-manifest path."""
    monkeypatch.chdir(tmp_path)
    workspace = Path("artifact")
    workspace.mkdir()
    manifest = workspace / "requirements.txt"
    manifest.touch()
    commands: list[tuple[str, ...]] = []

    def fake_run(
        name: str,
        command: tuple[str, ...],
        _workspace: Path,
        _evidence: Path,
        timeout: int = 90,
    ) -> CheckResult:
        del name, _workspace, _evidence, timeout
        commands.append(command)
        return CheckResult("command", "pass", "")

    monkeypatch.setattr(evaluator, "run_command", fake_run)

    evaluator._prepare_environment(workspace, Path("evidence"), manifest)

    assert Path(commands[-1][-1]).is_file()
    assert Path(commands[-1][-1]).is_absolute()


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


def test_frontend_block_action_reaches_registered_backend(tmp_path: Path) -> None:
    """A static frontend forwards relative API calls to its submitted backend."""
    artifact = tmp_path / "artifact"
    backend = artifact / "backend"
    frontend = artifact / "frontend"
    backend.mkdir(parents=True)
    frontend.mkdir()
    (backend / "app.py").touch()
    (frontend / "index.html").write_text("<button>add block</button>")
    (artifact / "requirements.txt").touch()
    adapter = resolve_adapter("opencode", 4, artifact)

    class BackendHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"submitted backend")

        def log_message(self, *_: object) -> None:
            return None

    backend_server = ThreadingHTTPServer(("127.0.0.1", 0), BackendHandler)
    Thread(target=backend_server.serve_forever, daemon=True).start()
    backend_adapter = evaluator.replace(
        adapter, url=f"http://127.0.0.1:{backend_server.server_port}/"
    )
    try:
        frontend_server, _, frontend_adapter = evaluator._serve_frontend(
            adapter, backend_adapter
        )
        try:
            with urllib.request.urlopen(
                urllib.parse.urljoin(frontend_adapter.url, "/api/blocks")
            ) as response:
                assert response.read() == b"submitted backend"
        finally:
            frontend_server.shutdown()
    finally:
        backend_server.shutdown()


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
