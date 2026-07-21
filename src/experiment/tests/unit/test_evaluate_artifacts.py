"""Unit tests for the deterministic artifact evaluator."""

import json
import math
import sys
import time
from pathlib import Path

import pytest

from evaluate_artifacts import (
    Adapter,
    CheckResult,
    DiagnosticCheck,
    artifact_digest,
    classify_task_verdict,
    clock_face_is_conventional,
    clock_is_time_accurate,
    clock_moves_clockwise,
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
    """Reports serialize task verdicts separately from diagnostics."""
    verdict = classify_task_verdict(
        3,
        {
            "browser-load": "pass",
            "face": "pass",
            "hands": "pass",
            "clockwise": "pass",
            "time-accurate": "pass",
            "reload": "pass",
        },
    )
    diagnostics = [DiagnosticCheck("browser", "blocked", "no browser")]

    result_path = write_report(
        tmp_path,
        agent="opencode",
        experiment=3,
        source=tmp_path / "artifact",
        digest_before="before",
        digest_after="after",
        adapter="clock:analog-clock.html",
        task_verdict=verdict,
        diagnostics=diagnostics,
    )

    payload = json.loads(result_path.read_text())
    assert payload["task_verdict"]["status"] == "pass"
    assert payload["diagnostic_summary"] == {
        "pass": 0,
        "fail": 0,
        "blocked": 1,
        "total": 1,
    }
    assert payload["functional_correctness"]["status"] == "pass"
    assert "Pass@1" not in json.dumps(payload)
    summary = result_path.with_name("summary.md").read_text()
    assert "## Functional Correctness" in summary
    assert "Pass@1" not in summary


def test_task_verdict_requires_complete_task_observations_not_diagnostics() -> None:
    """Passing prerequisites cannot establish Functional Correctness."""
    diagnostics = [DiagnosticCheck("startup", "pass", "application started")]

    verdict = classify_task_verdict(3, {"face": "pass"})

    assert verdict.status == "fail"
    assert diagnostics[0].status == "pass"


def test_clock_contract_rejects_wrong_face_direction_and_time() -> None:
    """Clock semantics require conventional labels and accurate clockwise motion."""
    labels = {
        str(number): (
            100 + 80 * math.sin(number * math.tau / 12),
            100 - 80 * math.cos(number * math.tau / 12),
        )
        for number in range(1, 13)
    }

    assert clock_face_is_conventional(labels, (100, 100))
    timestamp = 12_930.0
    wall_time = time.localtime(timestamp)
    assert clock_is_time_accurate(
        {
            "hour": (wall_time.tm_hour % 12) * 30
            + wall_time.tm_min / 2
            + wall_time.tm_sec / 120,
            "minute": wall_time.tm_min * 6 + wall_time.tm_sec / 10,
            "second": wall_time.tm_sec * 6,
        },
        timestamp,
    )
    assert clock_moves_clockwise(180.0, 186.6, 1.1, "second")
    assert not clock_moves_clockwise(180.0, 173.4, 1.1, "second")
    assert not clock_is_time_accurate(
        {"hour": 0.0, "minute": 0.0, "second": 0.0}, 3_900.0
    )


def test_declared_dependencies_do_not_receive_evaluator_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The evaluator never appends its runtime to a submitted dependency install."""
    workspace = tmp_path / "artifact"
    workspace.mkdir()
    manifest = workspace / "requirements.txt"
    manifest.write_text("flask==3.0.0\n")
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
    evaluator._prepare_environment(workspace, tmp_path / "evidence", manifest)

    assert all("uvicorn" not in command for command in commands)


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

    assert report["task_verdict"]["status"] == "fail"
    assert set(report["task_verdict"]["observations"].values()) == {"fail"}


def test_known_good_fixtures_pass_complete_black_box_contracts(tmp_path: Path) -> None:
    """Known-good fixtures pass every required task observation without repair."""
    clock = FIXTURES / "good" / "experiment-3"
    app = FIXTURES / "good" / "experiment-4"

    assert resolve_adapter("opencode", 3, clock).entrypoint.name == "analog-clock.html"
    assert resolve_adapter("opencode", 4, app).entrypoint.name == "app.py"
    clock_report = json.loads(
        evaluate_artifact("opencode", 3, clock, tmp_path / "clock").read_text()
    )
    app_report = json.loads(
        evaluate_artifact("opencode", 4, app, tmp_path / "app").read_text()
    )

    assert clock_report["task_verdict"]["status"] == "pass"
    assert app_report["task_verdict"]["status"] == "pass"
    assert clock_report["digest_before"] == clock_report["digest_after"]
    assert app_report["digest_before"] == app_report["digest_after"]


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


def test_experiment_four_prepares_its_declared_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Experiment 4 prepares the copied submitted manifest before evaluation."""
    prepared: list[Path] = []

    def fake_prepare(
        workspace: Path, _evidence: Path, manifest: Path
    ) -> tuple[Path, CheckResult]:
        prepared.append(manifest)
        return workspace / ".evaluator-venv" / "bin" / "python", CheckResult(
            "dependency-install", "pass", "installed"
        )

    monkeypatch.setattr(evaluator, "_prepare_environment", fake_prepare)
    monkeypatch.setattr(
        evaluator,
        "_experiment_four",
        lambda _adapter, _evidence, _interpreter: (
            classify_task_verdict(4, {name: "pass" for name in evaluator.TASKS[4]}),
            [],
        ),
    )

    evaluate_artifact("opencode", 4, FIXTURES / "good" / "experiment-4", tmp_path)

    assert prepared == [
        tmp_path / "workspace" / "experiment-4" / "backend" / "requirements.txt"
    ]


@pytest.mark.parametrize(
    ("agent", "port"),
    (("opencode", 5000), ("hermes", 5001), ("openclaw", 8000), ("tinycua", 8000)),
)
def test_registered_adapter_uses_submitted_listener_url(
    tmp_path: Path, agent: str, port: int
) -> None:
    """Each adapter probes its submitted listener rather than a shared port."""
    submitted, relative_root, startup, _url = evaluator.BACKENDS[agent]
    artifact = tmp_path / agent
    root = artifact / relative_root
    entrypoint = artifact / submitted
    root.mkdir(parents=True)
    entrypoint.parent.mkdir(parents=True, exist_ok=True)
    entrypoint.touch()
    (root / startup).touch()
    (root / "requirements.txt").touch()

    assert resolve_adapter(agent, 4, artifact).url == f"http://127.0.0.1:{port}/"


def test_clock_runtime_error_fails_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Submitted JavaScript errors fail the required browser-load observation."""
    class Message:
        type = "error"
        text = "submitted error"

    class Page:
        def __init__(self) -> None:
            self.handlers: dict[str, object] = {}

        def on(self, name: str, handler: object) -> None:
            self.handlers[name] = handler

        def goto(self, *_: object, **__: object) -> None:
            self.handlers["console"](Message())
            self.handlers["pageerror"](RuntimeError("submitted error"))

        def screenshot(self, **_: object) -> None:
            return None

        def reload(self, **_: object) -> None:
            return None

    class Browser:
        def new_page(self) -> Page:
            return Page()

        def close(self) -> None:
            return None

    class Playwright:
        def stop(self) -> None:
            return None

    monkeypatch.setattr(
        evaluator,
        "_browser_prerequisite",
        lambda _evidence: (Playwright(), Browser(), None),
    )
    monkeypatch.setattr(evaluator, "_clock_snapshot", lambda _page: ({}, (0, 0), {}))
    monkeypatch.setattr(evaluator, "clock_face_is_conventional", lambda *_: True)
    monkeypatch.setattr(evaluator, "clock_is_time_accurate", lambda *_: True)
    monkeypatch.setattr(evaluator, "clock_moves_clockwise", lambda *_: True)
    monkeypatch.setattr(evaluator.time, "sleep", lambda _: None)

    verdict, diagnostics = evaluator._clock_contract(
        Adapter("clock", tmp_path, tmp_path / "clock.html"), tmp_path
    )

    assert verdict.status == "fail"
    assert diagnostics[0].status == "fail"
    assert "submitted error" in (tmp_path / "browser-console.log").read_text()


def test_unrelated_sqlite_file_does_not_satisfy_persistence_contract(
    tmp_path: Path,
) -> None:
    """A readable database without the submitted task state is insufficient."""
    database = tmp_path / "unrelated.sqlite"
    with evaluator.sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
        connection.execute("INSERT INTO unrelated VALUES ('unrelated')")

    before = evaluator._sqlite_snapshots(tmp_path)

    assert not evaluator._sqlite_persists(
        before, evaluator._sqlite_snapshots(tmp_path), "Evaluator page", "Evaluator block"
    )


def test_inert_creation_controls_fail_experiment_four_contract() -> None:
    """Unchanged submitted state cannot satisfy a page or block creation action."""
    existing = (1, ("Existing",))

    assert not evaluator._creation_observed(existing, existing)


def test_adapter_uses_only_a_submitted_start_script(tmp_path: Path) -> None:
    """Application adapters never manufacture a framework launch command."""
    artifact = tmp_path / "artifact"
    backend = artifact / "backend"
    backend.mkdir(parents=True)
    (backend / "app.py").touch()
    (backend / "start.sh").touch()
    (backend / "requirements.txt").touch()

    adapter = resolve_adapter("opencode", 4, artifact)

    assert adapter.startup == ("sh", "start.sh")


def test_report_evidence_paths_resolve_from_report_directory(tmp_path: Path) -> None:
    """Command evidence paths resolve relative to their result report."""
    result = evaluator.run_command(
        "command", (sys.executable, "-c", ""), tmp_path, tmp_path / "evidence"
    )

    assert result.evidence == ("evidence/commands/command.log",)
    assert (tmp_path / result.evidence[0]).is_file()
