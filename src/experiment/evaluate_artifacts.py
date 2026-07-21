"""Evaluate frozen coding artifacts through submitted browser interfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Final


AGENTS: Final = ("opencode", "hermes", "openclaw", "tinycua")
STATUSES: Final = ("pass", "fail", "blocked")
FUNCTIONAL_CORRECTNESS_LABEL: Final = "Functional Correctness (deterministic)"
CONTRACT_VERSION: Final = "3"
TASKS: Final = {
    3: ("browser-load", "face", "hands", "clockwise", "time-accurate", "reload"),
    4: (
        "page-create",
        "block-create",
        "page-edit",
        "block-edit",
        "reload-persistence",
        "restart-persistence",
        "sqlite-persistence",
    ),
}
CLOCK_FILES: Final = {
    "opencode": "analog-clock.html",
    "hermes": "analog-clock.html",
    "openclaw": "clock.html",
    "tinycua": "clock.html",
}
BACKENDS: Final = {
    "opencode": (
        "backend/app.py",
        "backend",
        "start.sh",
        "http://127.0.0.1:5000/",
        ".block-container",
    ),
    "hermes": (
        "notion-app/run.py",
        "notion-app",
        "start.sh",
        "http://127.0.0.1:5001/",
        ".block",
    ),
    "openclaw": (
        "app/main.py",
        ".",
        "start.sh",
        "http://127.0.0.1:8000/",
        ".page-block",
    ),
    "tinycua": (
        "src/main.py",
        ".",
        "start.sh",
        "http://127.0.0.1:8000/",
        ".noteion-block",
    ),
}
CLOCK_TOLERANCES: Final = {"hour": 4.0, "minute": 4.0, "second": 12.0}
CLOCK_RATES: Final = {"hour": 1 / 120, "minute": 1 / 10, "second": 6.0}


@dataclass(frozen=True)
class CheckResult:
    """One observable task-contract result."""

    name: str
    status: str
    message: str
    command: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject statuses outside the registered vocabulary."""
        if self.status not in STATUSES:
            msg = f"unknown result status: {self.status}"
            raise ValueError(msg)


@dataclass(frozen=True)
class DiagnosticCheck(CheckResult):
    """An auditable prerequisite or runtime observation, never a task step."""


@dataclass(frozen=True)
class TaskVerdict:
    """The single Functional Correctness verdict for a complete task contract."""

    experiment: int
    status: str
    observations: dict[str, str]
    rationale: str
    evidence: tuple[str, ...] = ()
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        """Reject invalid verdict statuses."""
        if self.status not in STATUSES:
            msg = f"unknown verdict status: {self.status}"
            raise ValueError(msg)


@dataclass(frozen=True)
class Adapter:
    """Explicit mapping to submitted files, startup command, and UI controls."""

    name: str
    root: Path
    entrypoint: Path
    url: str = "http://127.0.0.1:18765/"
    startup: tuple[str, ...] = ()
    page_create_selector: str = "button.btn-new-page"
    page_title_selector: str = "#pageTitleInput"
    block_create_selector: str = "button.btn-block-action"
    block_created_selector: str = "#blockCount"
    block_editor_selector: str = "[contenteditable='true'], #blockEditor"


@dataclass
class ArtifactReport:
    """Serializable evaluation record for one frozen artifact."""

    agent: str
    experiment: int
    source: str
    digest_before: str
    digest_after: str
    adapter: str
    task_verdict: TaskVerdict
    diagnostics: list[DiagnosticCheck] = field(default_factory=list)


def parse_agents(raw: str | None) -> tuple[str, ...]:
    """Validate an optional comma-separated harness filter."""
    if raw is None:
        return AGENTS
    agents = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not agents:
        raise ValueError("agents must not be empty")
    unknown = [agent for agent in agents if agent not in AGENTS]
    if unknown:
        raise ValueError(f"unknown agent(s): {', '.join(unknown)}")
    if len(set(agents)) != len(agents):
        raise ValueError("duplicate agents are not allowed")
    return agents


def artifact_digest(source: Path) -> str:
    """Return a deterministic digest of every source path and file byte."""
    digest = hashlib.sha256()
    for path in sorted(
        source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()
    ):
        relative = path.relative_to(source).as_posix().encode()
        if path.is_symlink():
            kind, content = b"link", os.readlink(path).encode()
        elif path.is_dir():
            kind, content = b"dir", b""
        else:
            kind, content = b"file", path.read_bytes()
        digest.update(kind + b"\0" + relative + b"\0" + content + b"\0")
    return digest.hexdigest()


def copy_artifact(source: Path, copy_root: Path) -> Path:
    """Copy a source artifact into an evaluator-owned workspace."""
    destination = copy_root / source.name
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=True)
    return destination


def summarize_checks(checks: list[CheckResult]) -> dict[str, int]:
    """Count diagnostic statuses without deriving a task verdict from them."""
    summary = {status: 0 for status in STATUSES}
    for check in checks:
        summary[check.status] += 1
    return {**summary, "total": len(checks)}


def classify_task_verdict(
    experiment: int, observations: dict[str, str], evidence: tuple[str, ...] = ()
) -> TaskVerdict:
    """Classify only complete registered task observations."""
    required = TASKS[experiment]
    missing = [name for name in required if name not in observations]
    invalid = [status for status in observations.values() if status not in STATUSES]
    if invalid:
        raise ValueError(f"unknown observation status: {invalid[0]}")
    if missing:
        return TaskVerdict(
            experiment,
            "fail",
            observations,
            f"incomplete task contract: missing {', '.join(missing)}",
            evidence,
        )
    statuses = tuple(observations[name] for name in required)
    if all(status == "pass" for status in statuses):
        return TaskVerdict(
            experiment, "pass", observations, "complete task contract", evidence
        )
    status = "blocked" if "blocked" in statuses else "fail"
    return TaskVerdict(
        experiment, status, observations, "task contract not satisfied", evidence
    )


def _failed_verdict(experiment: int, message: str) -> TaskVerdict:
    """Create a visible failed verdict for an unsupported submitted layout."""
    return classify_task_verdict(
        experiment, {name: "fail" for name in TASKS[experiment]}
    )


def resolve_adapter(agent: str, experiment: int, source: Path) -> Adapter:
    """Select one explicit submitted layout without repairing or augmenting it."""
    if experiment == 3:
        entrypoint = source / CLOCK_FILES[agent]
        if entrypoint.is_file():
            return Adapter(f"clock:{entrypoint.name}", source, entrypoint)
    else:
        submitted, relative_root, startup, url, block_created_selector = BACKENDS[agent]
        entrypoint = source / submitted
        root = source / relative_root
        startup_path = root / startup
        manifest = root / "requirements.txt"
        if entrypoint.is_file() and startup_path.is_file() and manifest.is_file():
            return Adapter(
                f"notion:{agent}",
                root,
                entrypoint,
                url=url,
                startup=("sh", startup),
                block_created_selector=block_created_selector,
            )
    raise ValueError(f"unsupported {agent} experiment-{experiment} layout")


def _evidence_path(path: Path, evidence_root: Path) -> str:
    """Return an evidence path that resolves from the report directory."""
    return str(path.relative_to(evidence_root.parent))


def _write_evidence(path: Path, text: str, evidence_root: Path) -> str:
    """Write evaluator-owned evidence and return its report-relative path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return _evidence_path(path, evidence_root)


def _safe_environment(workspace: Path, interpreter: Path | None = None) -> dict[str, str]:
    """Run copied artifacts without inherited home-directory credentials."""
    home = workspace / ".evaluator-home"
    home.mkdir(exist_ok=True)
    path = os.environ.get("PATH", "")
    if interpreter:
        path = f"{interpreter.parent}{os.pathsep}{path}"
    return {"HOME": str(home), "PATH": path}


def run_command(
    name: str,
    command: tuple[str, ...],
    workspace: Path,
    evidence_root: Path,
    timeout: int = 90,
) -> CheckResult:
    """Run a submitted declared command in the copied workspace."""
    log = evidence_root / "commands" / f"{name}.log"
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=_safe_environment(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        evidence = _write_evidence(log, str(error), evidence_root)
        return CheckResult(name, "blocked", str(error), command, (evidence,))
    except subprocess.TimeoutExpired as error:
        evidence = _write_evidence(
            log, (error.stdout or "") + (error.stderr or ""), evidence_root
        )
        return CheckResult(
            name, "fail", f"timed out after {timeout}s", command, (evidence,)
        )
    evidence = _write_evidence(log, completed.stdout + completed.stderr, evidence_root)
    return CheckResult(
        name,
        "pass" if completed.returncode == 0 else "fail",
        f"exit code {completed.returncode}",
        command,
        (evidence,),
    )


def _prepare_environment(
    workspace: Path, evidence_root: Path, manifest: Path
) -> tuple[Path, CheckResult]:
    """Install only dependencies explicitly listed by a submitted manifest."""
    workspace = workspace.resolve()
    manifest = manifest.resolve()
    environment = workspace / ".evaluator-venv"
    interpreter = environment / "bin" / "python"
    created = run_command(
        "environment-create",
        (sys.executable, "-m", "venv", str(environment)),
        workspace,
        evidence_root,
    )
    if created.status != "pass":
        return interpreter, CheckResult(
            "dependency-install", created.status, created.message
        )
    return interpreter, run_command(
        "dependency-install",
        (str(interpreter), "-m", "pip", "install", "-r", str(manifest)),
        workspace,
        evidence_root,
    )


def _angle_difference(actual: float, expected: float) -> float:
    """Return the smallest distance between two clockwise angles."""
    return abs((actual - expected + 180) % 360 - 180)


def clock_face_is_conventional(
    labels: dict[str, tuple[float, float]], center: tuple[float, float]
) -> bool:
    """Check that visible labels 1 through 12 occupy conventional clock positions."""
    if set(labels) != {str(number) for number in range(1, 13)}:
        return False
    center_x, center_y = center
    for label, (x, y) in labels.items():
        angle = math.degrees(math.atan2(x - center_x, center_y - y)) % 360
        expected = (int(label) % 12) * 30
        if _angle_difference(angle, expected) > 25:
            return False
    return True


def clock_is_time_accurate(angles: dict[str, float], timestamp: float) -> bool:
    """Check hour, minute, and second hands against local wall-clock time."""
    wall_time = time.localtime(timestamp)
    expected = {
        "hour": (wall_time.tm_hour % 12) * 30
        + wall_time.tm_min / 2
        + wall_time.tm_sec / 120,
        "minute": wall_time.tm_min * 6 + wall_time.tm_sec / 10,
        "second": wall_time.tm_sec * 6,
    }
    return all(
        hand in angles
        and _angle_difference(angles[hand], expected[hand]) <= CLOCK_TOLERANCES[hand]
        for hand in expected
    )


def clock_moves_clockwise(
    before: float, after: float, elapsed: float, hand: str
) -> bool:
    """Check that one hand advanced clockwise by its elapsed-time distance."""
    expected = CLOCK_RATES[hand] * elapsed
    observed = (after - before) % 360
    tolerance = max(0.1, expected * 0.5)
    return expected > 0 and abs(observed - expected) <= tolerance


def _clock_snapshot(
    page: object,
) -> tuple[dict[str, tuple[float, float]], tuple[float, float], dict[str, float]]:
    """Read visible clock geometry without changing the submitted page."""
    observation = page.evaluate(
        """() => {
            const face = document.querySelector('[data-clock-face], #clock, .clock');
            const faceBox = face?.getBoundingClientRect();
            const labels = [...document.querySelectorAll('[data-clock-label]')].map(node => {
                const box = node.getBoundingClientRect();
                return [node.dataset.clockLabel || node.textContent.trim(), box.x + box.width / 2, box.y + box.height / 2];
            });
            const hands = [...document.querySelectorAll('[data-clock-hand]')].map(node => {
                const transform = getComputedStyle(node).transform;
                return [node.dataset.clockHand, transform];
            });
            return { labels, hands, center: faceBox ? [faceBox.x + faceBox.width / 2, faceBox.y + faceBox.height / 2] : null };
        }"""
    )
    labels = {label: (x, y) for label, x, y in observation["labels"]}
    if observation["center"] is None:
        center = (
            sum(x for x, _ in labels.values()) / len(labels),
            sum(y for _, y in labels.values()) / len(labels),
        )
    else:
        center = tuple(observation["center"])
    hands = {
        hand: _transform_angle(transform) for hand, transform in observation["hands"]
    }
    return labels, center, hands


def _transform_angle(transform: str) -> float:
    """Convert a computed CSS matrix transform to a clockwise clock angle."""
    if transform == "none":
        return 0.0
    values = transform.removeprefix("matrix(").removesuffix(")").split(",")
    if len(values) < 2:
        return float("nan")
    return math.degrees(math.atan2(float(values[1]), float(values[0]))) % 360


def _browser_prerequisite(
    evidence_root: Path,
) -> tuple[object | None, object | None, DiagnosticCheck | None]:
    """Launch the evaluator browser or return a separate blocked prerequisite."""
    console = evidence_root / "browser-console.log"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        evidence = _write_evidence(
            console, "playwright is not installed", evidence_root
        )
        return (
            None,
            None,
            DiagnosticCheck(
                "browser",
                "blocked",
                "browser dependency unavailable",
                evidence=(evidence,),
            ),
        )
    playwright = None
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch()
    except Exception as error:
        if playwright:
            playwright.stop()
        evidence = _write_evidence(console, str(error), evidence_root)
        return (
            None,
            None,
            DiagnosticCheck(
                "browser",
                "blocked",
                "browser runtime unavailable",
                evidence=(evidence,),
            ),
        )
    return playwright, browser, None


def _clock_contract(
    adapter: Adapter, evidence_root: Path
) -> tuple[TaskVerdict, list[DiagnosticCheck]]:
    """Evaluate conventional, accurate, active clock behavior through its page."""
    playwright, browser, prerequisite = _browser_prerequisite(evidence_root)
    if prerequisite:
        return (
            classify_task_verdict(3, {name: "blocked" for name in TASKS[3]}),
            [prerequisite],
        )
    assert playwright is not None
    messages: list[str] = []
    errors: list[str] = []

    def record_console(message: object) -> None:
        line = f"{message.type}: {message.text}"
        messages.append(line)
        if message.type == "error":
            errors.append(line)

    def record_page_error(error: object) -> None:
        line = f"pageerror: {error}"
        messages.append(line)
        errors.append(line)

    try:
        page = browser.new_page()
        page.on("console", record_console)
        page.on("pageerror", record_page_error)
        page.goto(adapter.url, wait_until="networkidle", timeout=15_000)
        before_path = evidence_root / "clock-before.png"
        after_path = evidence_root / "clock-after.png"
        page.screenshot(path=str(before_path))
        before_time = time.time()
        labels, center, before = _clock_snapshot(page)
        time.sleep(2.1)
        after_time = time.time()
        _, _, after = _clock_snapshot(page)
        page.screenshot(path=str(after_path))
        page.reload(wait_until="networkidle", timeout=15_000)
        reload_time = time.time()
        reload_labels, reload_center, reload_hands = _clock_snapshot(page)
        evidence = (
            _evidence_path(before_path, evidence_root),
            _evidence_path(after_path, evidence_root),
        )
        observations = {
            "browser-load": "pass" if not errors else "fail",
            "face": "pass" if clock_face_is_conventional(labels, center) else "fail",
            "hands": "pass" if set(before) == set(CLOCK_RATES) else "fail",
            "clockwise": "pass"
            if set(before) == set(after) == set(CLOCK_RATES)
            and all(
                clock_moves_clockwise(
                    before[hand], after[hand], after_time - before_time, hand
                )
                for hand in CLOCK_RATES
            )
            else "fail",
            "time-accurate": "pass"
            if clock_is_time_accurate(before, before_time)
            else "fail",
            "reload": "pass"
            if clock_face_is_conventional(reload_labels, reload_center)
            and clock_is_time_accurate(reload_hands, reload_time)
            else "fail",
        }
        console = _write_evidence(
            evidence_root / "browser-console.log", "\n".join(messages), evidence_root
        )
        diagnostics = [
            DiagnosticCheck(
                "browser-load",
                "pass" if not errors else "fail",
                "submitted page loaded" if not errors else "submitted JavaScript error",
                evidence=(console,),
            )
        ]
        return classify_task_verdict(3, observations, evidence), diagnostics
    except Exception as error:
        evidence = _write_evidence(
            evidence_root / "browser-console.log", str(error), evidence_root
        )
        return classify_task_verdict(
            3, {name: "fail" for name in TASKS[3]}, (evidence,)
        ), [DiagnosticCheck("browser-load", "fail", str(error), evidence=(evidence,))]
    finally:
        assert browser is not None
        browser.close()
        playwright.stop()


def _serve_static(adapter: Adapter) -> tuple[ThreadingHTTPServer, Thread, Adapter]:
    """Serve a copied static clock artifact at an evaluator-owned local address."""

    def handler(*args: object, **kwargs: object) -> SimpleHTTPRequestHandler:
        return SimpleHTTPRequestHandler(*args, directory=str(adapter.root), **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return (
        server,
        thread,
        Adapter(
            **(
                asdict(adapter)
                | {
                    "url": f"http://127.0.0.1:{server.server_port}/{adapter.entrypoint.name}"
                }
            )
        ),
    )


def _start_server(adapter: Adapter, interpreter: Path) -> subprocess.Popen[str]:
    """Start only the copied artifact's submitted startup command."""
    if not adapter.startup:
        raise ValueError("no submitted startup command")
    return subprocess.Popen(
        adapter.startup,
        cwd=adapter.root,
        env=_safe_environment(adapter.root, interpreter),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def _stop_server(process: subprocess.Popen[str]) -> str:
    """Stop an evaluator-started process and collect its output."""
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        return process.communicate(timeout=5)[0]
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        return process.communicate()[0]


def _wait_for_server(adapter: Adapter, process: subprocess.Popen[str]) -> bool:
    """Wait for the submitted root to respond without probing invented endpoints."""
    for _ in range(40):
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(adapter.url, timeout=1) as response:
                return response.status < 500
        except OSError:
            time.sleep(0.25)
    return False


def _input_value(locator: object) -> str:
    """Read text from a submitted input or editable block."""
    return (
        locator.input_value()
        if locator.evaluate(
            "node => node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement"
        )
        else locator.inner_text()
    )


def _ui_contract(
    adapter: Adapter, evidence_root: Path, interpreter: Path
) -> tuple[TaskVerdict, list[DiagnosticCheck]]:
    """Create and edit a page and block exclusively through the submitted UI."""
    process = _start_server(adapter, interpreter)
    startup_log = evidence_root / "commands" / "submitted-startup.log"
    if not _wait_for_server(adapter, process):
        output = _stop_server(process)
        evidence = _write_evidence(startup_log, output, evidence_root)
        return classify_task_verdict(4, {name: "fail" for name in TASKS[4]}), [
            DiagnosticCheck(
                "startup", "fail", "submitted root did not start", evidence=(evidence,)
            )
        ]
    playwright, browser, prerequisite = _browser_prerequisite(evidence_root)
    if prerequisite:
        output = _stop_server(process)
        evidence = _write_evidence(startup_log, output, evidence_root)
        return classify_task_verdict(4, {name: "blocked" for name in TASKS[4]}), [
            DiagnosticCheck(
                "startup", "pass", "submitted root responded", evidence=(evidence,)
            ),
            prerequisite,
        ]
    assert playwright is not None
    page_title = f"Evaluator page {time.time_ns()}"
    block_text = f"Evaluator block {time.time_ns()}"
    try:
        page = browser.new_page()
        page.goto(adapter.url, wait_until="networkidle", timeout=15_000)
        page_before = _creation_state(page, adapter.page_title_selector)
        sqlite_before = _sqlite_snapshots(adapter.root)
        page.locator(adapter.page_create_selector).first.click()
        title = page.locator(adapter.page_title_selector).first
        page.wait_for_timeout(600)
        page_created = _creation_observed(
            page_before, _creation_state(page, adapter.page_title_selector)
        )
        title.fill(page_title)
        title.press("Tab")
        page.wait_for_timeout(600)
        block_before = _creation_state(page, adapter.block_created_selector)
        page.locator(adapter.block_create_selector).first.click()
        editor = page.locator(adapter.block_editor_selector).first
        page.wait_for_timeout(600)
        block_created = _creation_observed(
            block_before, _creation_state(page, adapter.block_created_selector)
        )
        editor.fill(block_text)
        editor.press("Tab")
        page.wait_for_timeout(600)
        first = evidence_root / "ui-before-reload.png"
        page.screenshot(path=str(first))
        edited = _input_value(title) == page_title and block_text in _input_value(
            editor
        )
        page.reload(wait_until="networkidle", timeout=15_000)
        title = page.locator(adapter.page_title_selector).first
        editor = page.locator(adapter.block_editor_selector).first
        reloaded = _input_value(title) == page_title and block_text in _input_value(
            editor
        )
        output = _stop_server(process)
        start_evidence = _write_evidence(startup_log, output, evidence_root)
        process = _start_server(adapter, interpreter)
        restarted = _wait_for_server(adapter, process)
        if restarted:
            page.goto(adapter.url, wait_until="networkidle", timeout=15_000)
            title = page.locator(adapter.page_title_selector).first
            editor = page.locator(adapter.block_editor_selector).first
            restarted = _input_value(
                title
            ) == page_title and block_text in _input_value(editor)
        second = evidence_root / "ui-after-restart.png"
        page.screenshot(path=str(second))
        sqlite = _sqlite_persists(
            sqlite_before, _sqlite_snapshots(adapter.root), page_title, block_text
        )
        evidence = (
            _evidence_path(first, evidence_root),
            _evidence_path(second, evidence_root),
        )
        observations = {
            "page-create": "pass" if page_created else "fail",
            "block-create": "pass" if block_created else "fail",
            "page-edit": "pass" if edited else "fail",
            "block-edit": "pass" if edited else "fail",
            "reload-persistence": "pass" if reloaded else "fail",
            "restart-persistence": "pass" if restarted else "fail",
            "sqlite-persistence": "pass" if sqlite and restarted else "fail",
        }
        diagnostics = [
            DiagnosticCheck(
                "startup",
                "pass",
                "submitted root responded",
                evidence=(start_evidence,),
            )
        ]
        return classify_task_verdict(4, observations, evidence), diagnostics
    except Exception as error:
        evidence = _write_evidence(
            evidence_root / "browser-console.log", str(error), evidence_root
        )
        return classify_task_verdict(4, {name: "fail" for name in TASKS[4]}), [
            DiagnosticCheck("browser-ui", "fail", str(error), evidence=(evidence,))
        ]
    finally:
        assert browser is not None
        browser.close()
        playwright.stop()
        _write_evidence(startup_log, _stop_server(process), evidence_root)


def _creation_state(page: object, selector: str) -> tuple[int, tuple[str, ...]]:
    """Capture submitted controls and visible state before a creation action."""
    controls = page.locator(selector)
    return (
        controls.count(),
        tuple(_input_value(controls.nth(index)) for index in range(controls.count())),
    )


def _creation_observed(
    before: tuple[int, tuple[str, ...]], after: tuple[int, tuple[str, ...]]
) -> bool:
    """Require the submitted page to visibly change immediately after creation."""
    return before != after


def _sqlite_snapshots(root: Path) -> dict[Path, str]:
    """Read submitted SQLite state without writing to the copied artifact."""
    snapshots: dict[Path, str] = {}
    for path in [*root.rglob("*.sqlite"), *root.rglob("*.db")]:
        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
                snapshots[path] = "\n".join(connection.iterdump())
        except sqlite3.Error:
            continue
    return snapshots


def _sqlite_persists(
    before: dict[Path, str], after: dict[Path, str], page_title: str, block_text: str
) -> bool:
    """Require changed submitted SQLite state to contain the created page and block."""
    return any(
        before.get(path) != state and page_title in state and block_text in state
        for path, state in after.items()
    )


def _experiment_three(
    adapter: Adapter, evidence_root: Path
) -> tuple[TaskVerdict, list[DiagnosticCheck]]:
    """Evaluate the fixed Experiment 3 browser contract."""
    try:
        server, _, runtime_adapter = _serve_static(adapter)
    except OSError as error:
        return classify_task_verdict(3, {name: "blocked" for name in TASKS[3]}), [
            DiagnosticCheck("static-server", "blocked", str(error))
        ]
    try:
        return _clock_contract(runtime_adapter, evidence_root)
    finally:
        server.shutdown()
        server.server_close()


def _experiment_four(
    adapter: Adapter, evidence_root: Path, interpreter: Path
) -> tuple[TaskVerdict, list[DiagnosticCheck]]:
    """Evaluate the submitted Experiment 4 application and UI contract."""
    return _ui_contract(adapter, evidence_root, interpreter)


def write_report(
    output: Path,
    *,
    agent: str,
    experiment: int,
    source: Path,
    digest_before: str,
    digest_after: str,
    adapter: str,
    task_verdict: TaskVerdict,
    diagnostics: list[DiagnosticCheck],
) -> Path:
    """Write separate machine-readable task and diagnostic evidence reports."""
    output.mkdir(parents=True, exist_ok=True)
    report = ArtifactReport(
        agent,
        experiment,
        str(source),
        digest_before,
        digest_after,
        adapter,
        task_verdict,
        diagnostics,
    )
    payload = asdict(report) | {
        "functional_correctness": {
            "label": FUNCTIONAL_CORRECTNESS_LABEL,
            **asdict(task_verdict),
        },
        "diagnostic_summary": summarize_checks(diagnostics),
    }
    result = output / "result.json"
    result.write_text(json.dumps(payload, indent=2) + "\n")
    rows = [
        "# Artifact Evaluation",
        "",
        f"Source digest before: `{digest_before}`",
        f"Source digest after: `{digest_after}`",
        "",
        "## Functional Correctness",
        "",
        f"Status: `{task_verdict.status}`",
        f"Rationale: {task_verdict.rationale}",
        "",
        "| Task observation | Status |",
        "| --- | --- |",
    ]
    rows.extend(
        f"| {name} | {status} |" for name, status in task_verdict.observations.items()
    )
    rows.extend(
        [
            "",
            "## Diagnostics",
            "",
            "| Check | Status | Evidence |",
            "| --- | --- | --- |",
        ]
    )
    rows.extend(
        f"| {check.name} | {check.status} | {', '.join(check.evidence)} |"
        for check in diagnostics
    )
    result.with_name("summary.md").write_text("\n".join(rows) + "\n")
    return result


def evaluate_artifact(agent: str, experiment: int, source: Path, output: Path) -> Path:
    """Evaluate one immutable source artifact through its complete task contract."""
    digest_before = artifact_digest(source)
    workspace = copy_artifact(source, output / "workspace")
    evidence = output / "evidence"
    diagnostics: list[DiagnosticCheck] = [
        DiagnosticCheck("artifact-discovery", "pass", "artifact copied")
    ]
    try:
        adapter = resolve_adapter(agent, experiment, workspace)
        if experiment == 3:
            verdict, runtime_diagnostics = _experiment_three(adapter, evidence)
        else:
            interpreter, dependency = _prepare_environment(
                adapter.root, evidence, adapter.root / "requirements.txt"
            )
            diagnostics.append(
                DiagnosticCheck(
                    dependency.name,
                    dependency.status,
                    dependency.message,
                    dependency.command,
                    dependency.evidence,
                )
            )
            if dependency.status == "pass":
                verdict, runtime_diagnostics = _experiment_four(
                    adapter, evidence, interpreter
                )
            else:
                verdict = classify_task_verdict(
                    4, {name: dependency.status for name in TASKS[4]}
                )
                runtime_diagnostics = []
        diagnostics.extend(runtime_diagnostics)
    except ValueError as error:
        adapter = Adapter("unsupported", workspace, workspace)
        verdict = _failed_verdict(experiment, str(error))
        diagnostics.append(DiagnosticCheck("adapter", "fail", str(error)))
    digest_after = artifact_digest(source)
    diagnostics.append(
        DiagnosticCheck(
            "source-immutability",
            "pass" if digest_after == digest_before else "fail",
            "source digest unchanged"
            if digest_after == digest_before
            else "source digest changed",
        )
    )
    return write_report(
        output,
        agent=agent,
        experiment=experiment,
        source=source,
        digest_before=digest_before,
        digest_after=digest_after,
        adapter=adapter.name,
        task_verdict=verdict,
        diagnostics=diagnostics,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the evaluator command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agents", help="comma-separated subset of opencode,hermes,openclaw,tinycua"
    )
    parser.add_argument(
        "--artifact-root", type=Path, default=Path("evaluation-results")
    )
    parser.add_argument("--output-root", type=Path, default=Path("evaluator-output"))
    return parser


def main(argv: list[str] | None = None) -> int:
    """Evaluate selected frozen artifacts and fail for any non-passing verdict."""
    args = build_parser().parse_args(argv)
    try:
        agents = parse_agents(args.agents)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    reports: list[dict[str, object]] = []
    for agent in agents:
        for experiment in (3, 4):
            source = args.artifact_root / agent / f"experiment-{experiment}" / "workdir"
            output = args.output_root / agent / f"experiment-{experiment}"
            if source.is_dir():
                report_path = evaluate_artifact(agent, experiment, source, output)
            else:
                verdict = _failed_verdict(experiment, f"missing artifact: {source}")
                report_path = write_report(
                    output,
                    agent=agent,
                    experiment=experiment,
                    source=source,
                    digest_before="",
                    digest_after="",
                    adapter="missing",
                    task_verdict=verdict,
                    diagnostics=[
                        DiagnosticCheck(
                            "artifact-discovery", "fail", f"missing artifact: {source}"
                        )
                    ],
                )
            reports.append(json.loads(report_path.read_text()))
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "summary.json").write_text(json.dumps(reports, indent=2) + "\n")
    return (
        0
        if all(report["task_verdict"]["status"] == "pass" for report in reports)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
