"""Evaluate frozen coding artifacts without changing their source trees."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from threading import Thread
from typing import Final


AGENTS: Final = ("opencode", "hermes", "openclaw", "tinycua")
STATUSES: Final = ("pass", "fail", "blocked")
CONTRACTS: Final = {
    3: ("load", "runtime-errors", "visible-clock", "time-update", "reload"),
    4: (
        "dependency-install",
        "python-compile",
        "backend-startup",
        "sqlite-initialization",
        "frontend-build",
        "page-block",
        "browser-e2e",
    ),
}
CLOCK_FILES: Final = {
    "opencode": "analog-clock.html",
    "hermes": "analog-clock.html",
    "openclaw": "clock.html",
    "tinycua": "clock.html",
}
BACKENDS: Final = {
    "opencode": ("backend/app.py", "app:app", "backend"),
    "hermes": ("notion-app/run.py", "run:app", "notion-app"),
    "openclaw": ("app/main.py", "app.main:app", "."),
    "tinycua": ("src/main.py", "src.main:app", "."),
}


@dataclass(frozen=True)
class CheckResult:
    """One mandatory acceptance-contract result."""

    name: str
    status: str
    message: str
    command: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject status values outside the pre-registered contract."""
        if self.status not in STATUSES:
            msg = f"unknown result status: {self.status}"
            raise ValueError(msg)


@dataclass(frozen=True)
class Adapter:
    """Explicit mapping to submitted files and interfaces."""

    name: str
    root: Path
    entrypoint: Path
    url: str = "http://127.0.0.1:8765/"


@dataclass
class ArtifactReport:
    """Serializable evaluation record for one frozen artifact."""

    agent: str
    experiment: int
    source: str
    digest_before: str
    digest_after: str
    adapter: str
    checks: list[CheckResult] = field(default_factory=list)


def parse_agents(raw: str | None) -> tuple[str, ...]:
    """Validate an optional comma-separated harness filter."""
    if raw is None:
        return AGENTS
    agents = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not agents:
        msg = "agents must not be empty"
        raise ValueError(msg)
    unknown = [agent for agent in agents if agent not in AGENTS]
    if unknown:
        msg = f"unknown agent(s): {', '.join(unknown)}"
        raise ValueError(msg)
    if len(set(agents)) != len(agents):
        msg = "duplicate agents are not allowed"
        raise ValueError(msg)
    return agents


def artifact_digest(source: Path) -> str:
    """Return a deterministic digest of every path and file byte in source."""
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
    """Copy source into an evaluator-owned workspace."""
    destination = copy_root / source.name
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=True)
    return destination


def summarize_checks(checks: list[CheckResult]) -> dict[str, int]:
    """Count all mandatory contract statuses, including blocked checks."""
    summary = {status: 0 for status in STATUSES}
    for check in checks:
        summary[check.status] += 1
    return {**summary, "total": len(checks)}


def resolve_adapter(agent: str, experiment: int, source: Path) -> Adapter:
    """Select one explicit supported layout without repairing it."""
    if experiment == 3:
        filename = CLOCK_FILES[agent]
        entrypoint = source / filename
        if entrypoint.is_file():
            return Adapter(
                f"clock:{filename}",
                source,
                entrypoint,
                f"http://127.0.0.1:8765/{filename}",
            )
    elif experiment == 4:
        submitted, module, relative_root = BACKENDS[agent]
        entrypoint = source / submitted
        if entrypoint.is_file():
            return Adapter(
                f"notion:{agent}",
                source / relative_root,
                entrypoint,
                "http://127.0.0.1:8765/",
            )
    msg = f"unsupported {agent} experiment-{experiment} layout"
    raise ValueError(msg)


def _write_evidence(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return str(path.relative_to(path.parents[1]))


def _safe_environment(workspace: Path) -> dict[str, str]:
    """Run copied artifacts without inherited home-directory credentials."""
    home = workspace / ".evaluator-home"
    home.mkdir(exist_ok=True)
    return {"HOME": str(home), "PATH": os.environ.get("PATH", "")}


def run_command(
    name: str,
    command: tuple[str, ...],
    workspace: Path,
    evidence_root: Path,
    timeout: int = 90,
) -> CheckResult:
    """Run one declared command in a copied workspace and capture its output."""
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
        evidence = _write_evidence(log, str(error))
        return CheckResult(name, "blocked", str(error), command, (evidence,))
    except subprocess.TimeoutExpired as error:
        evidence = _write_evidence(log, (error.stdout or "") + (error.stderr or ""))
        return CheckResult(
            name, "fail", f"timed out after {timeout}s", command, (evidence,)
        )
    evidence = _write_evidence(log, completed.stdout + completed.stderr)
    status = "pass" if completed.returncode == 0 else "fail"
    return CheckResult(
        name, status, f"exit code {completed.returncode}", command, (evidence,)
    )


def _browser_checks(
    adapter: Adapter, evidence_root: Path, experiment: int
) -> list[CheckResult]:
    """Collect browser observations from the submitted page, or block explicitly."""
    console = evidence_root / "browser-console.log"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        evidence = _write_evidence(console, "playwright is not installed")
        return [
            CheckResult(
                name, "blocked", "browser dependency unavailable", evidence=(evidence,)
            )
            for name in CONTRACTS[experiment][-2:]
        ]
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            messages: list[str] = []
            page.on(
                "console",
                lambda message: messages.append(f"{message.type}: {message.text}"),
            )
            page.goto(adapter.url, wait_until="networkidle", timeout=15_000)
            first = evidence_root / "browser-before.png"
            second = evidence_root / "browser-after.png"
            page.screenshot(path=str(first))
            if experiment == 3:
                visible = (
                    page.locator("canvas, svg, #clock, .clock, [class*=clock]").count()
                    > 0
                )
                errors = [
                    message for message in messages if message.startswith("error:")
                ]
                time.sleep(1.1)
                page.screenshot(path=str(second))
                page.reload(wait_until="networkidle", timeout=15_000)
                browser.close()
                evidence = _write_evidence(console, "\n".join(messages))
                return [
                    CheckResult(
                        "load",
                        "pass",
                        "page loaded",
                        evidence=(evidence, "browser-before.png"),
                    ),
                    CheckResult(
                        "runtime-errors",
                        "fail" if errors else "pass",
                        "; ".join(errors) or "none",
                        evidence=(evidence,),
                    ),
                    CheckResult(
                        "visible-clock",
                        "pass" if visible else "fail",
                        "clock selector visible" if visible else "no clock selector",
                        evidence=("browser-before.png",),
                    ),
                    CheckResult(
                        "time-update",
                        "pass" if first.read_bytes() != second.read_bytes() else "fail",
                        "screenshots differ"
                        if first.read_bytes() != second.read_bytes()
                        else "no visual update",
                        evidence=("browser-before.png", "browser-after.png"),
                    ),
                    CheckResult(
                        "reload", "pass", "page reloaded", evidence=(evidence,)
                    ),
                ]
            body = page.locator("body").inner_text().strip()
            interactive = page.locator("a, button, input, textarea").count() > 0
            browser.close()
            evidence = _write_evidence(console, "\n".join(messages))
            return [
                CheckResult(
                    "page-block",
                    "pass" if body and interactive else "fail",
                    "submitted page has content and controls"
                    if body and interactive
                    else "page or controls missing",
                    evidence=(evidence, "browser-before.png"),
                ),
                CheckResult(
                    "browser-e2e", "pass", "submitted page loaded", evidence=(evidence,)
                ),
            ]
    except (
        Exception
    ) as error:  # Browser runtime availability is an evaluator prerequisite.
        evidence = _write_evidence(console, str(error))
        return [
            CheckResult(
                name, "blocked", "browser runtime unavailable", evidence=(evidence,)
            )
            for name in CONTRACTS[experiment][-2:]
        ]


def _serve_static(adapter: Adapter) -> tuple[object, Thread, Adapter]:
    """Serve a copied clock artifact on the adapter's fixed local address."""
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    def handler(*args: object, **kwargs: object) -> SimpleHTTPRequestHandler:
        return SimpleHTTPRequestHandler(*args, directory=str(adapter.root), **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    runtime_adapter = replace(
        adapter,
        url=f"http://127.0.0.1:{server.server_port}/{adapter.entrypoint.name}",
    )
    return server, thread, runtime_adapter


def _server_command(adapter: Adapter, port: int) -> tuple[str, ...]:
    """Build the fixed submitted-backend command for a registered adapter."""
    _, module, _ = BACKENDS[
        next(
            agent
            for agent, spec in BACKENDS.items()
            if spec[0] in str(adapter.entrypoint)
        )
    ]
    return (
        sys.executable,
        "-m",
        "uvicorn",
        module,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    )


def _start_server(
    adapter: Adapter,
) -> tuple[subprocess.Popen[str], tuple[str, ...], Adapter]:
    """Start a submitted backend in an evaluator-owned process group."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    command = _server_command(adapter, port)
    runtime_adapter = replace(adapter, url=f"http://127.0.0.1:{port}/")
    return (
        subprocess.Popen(
            command,
            cwd=adapter.root,
            env=_safe_environment(adapter.root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        ),
        command,
        runtime_adapter,
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


def _run_server(adapter: Adapter, evidence_root: Path) -> CheckResult:
    """Start a submitted ASGI app, probe its submitted root, and clean it up."""
    log = evidence_root / "commands" / "backend-startup.log"
    process, command, runtime_adapter = _start_server(adapter)
    status = "fail"
    message = "submitted root did not start"
    try:
        for _ in range(20):
            if process.poll() is not None:
                break
            try:
                with urllib.request.urlopen(runtime_adapter.url, timeout=1) as response:
                    if response.status < 500:
                        status = "pass"
                        message = "submitted root responded"
                        break
            except OSError:
                time.sleep(0.25)
    finally:
        output = _stop_server(process)
    evidence = _write_evidence(log, output)
    return CheckResult("backend-startup", status, message, command, (evidence,))


def _experiment_three(adapter: Adapter, evidence_root: Path) -> list[CheckResult]:
    """Evaluate the fixed Experiment 3 browser contract."""
    try:
        server, _, runtime_adapter = _serve_static(adapter)
    except OSError as error:
        return [CheckResult(name, "blocked", str(error)) for name in CONTRACTS[3]]
    try:
        return _browser_checks(runtime_adapter, evidence_root, 3)
    finally:
        server.shutdown()


def _experiment_four(
    adapter: Adapter, workspace: Path, evidence_root: Path
) -> list[CheckResult]:
    """Evaluate declared Experiment 4 dependencies, backend, and submitted UI."""
    manifests = [path for path in workspace.rglob("requirements.txt")]
    if manifests:
        dependency = run_command(
            "dependency-install",
            (
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                str(evidence_root / "dependencies"),
                "-r",
                str(manifests[0]),
            ),
            workspace,
            evidence_root,
        )
    else:
        dependency = CheckResult(
            "dependency-install", "fail", "no declared requirements.txt"
        )
    compile_check = run_command(
        "python-compile",
        (sys.executable, "-m", "compileall", "-q", "."),
        workspace,
        evidence_root,
    )
    backend = _run_server(adapter, evidence_root)
    sqlite_files = list(workspace.rglob("*.db")) + list(workspace.rglob("*.sqlite"))
    sqlite = CheckResult(
        "sqlite-initialization",
        "pass" if sqlite_files else "fail",
        "SQLite database initialized"
        if sqlite_files
        else "no SQLite database initialized",
    )
    packages = list(workspace.rglob("package.json"))
    frontend = (
        run_command(
            "frontend-build", ("npm", "run", "build"), packages[0].parent, evidence_root
        )
        if packages
        else CheckResult("frontend-build", "pass", "no declared frontend build")
    )
    if backend.status == "pass":
        process, _, runtime_adapter = _start_server(adapter)
        try:
            browser = _browser_checks(runtime_adapter, evidence_root, 4)
        finally:
            _stop_server(process)
    else:
        browser = [
            CheckResult(
                name,
                "blocked",
                "submitted backend unavailable",
                evidence=backend.evidence,
            )
            for name in CONTRACTS[4][-2:]
        ]
    return [dependency, compile_check, backend, sqlite, frontend, *browser]


def write_report(
    output: Path,
    *,
    agent: str,
    experiment: int,
    source: Path,
    digest_before: str,
    digest_after: str,
    adapter: str,
    checks: list[CheckResult],
) -> Path:
    """Write machine-readable and Markdown reports for one evaluation."""
    output.mkdir(parents=True, exist_ok=True)
    report = ArtifactReport(
        agent, experiment, str(source), digest_before, digest_after, adapter, checks
    )
    payload = asdict(report) | {"summary": summarize_checks(checks)}
    result = output / "result.json"
    result.write_text(json.dumps(payload, indent=2) + "\n")
    rows = [
        "# Artifact Evaluation",
        "",
        f"Source digest: `{digest_before}`",
        "",
        "| Check | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    rows.extend(
        f"| {check.name} | {check.status} | {', '.join(check.evidence)} |"
        for check in checks
    )
    rows.extend(
        ["", f"Summary: `{json.dumps(payload['summary'], sort_keys=True)}`", ""]
    )
    result.with_name("summary.md").write_text("\n".join(rows))
    return result


def evaluate_artifact(agent: str, experiment: int, source: Path, output: Path) -> Path:
    """Evaluate one source artifact through its complete fixed contract."""
    digest_before = artifact_digest(source)
    workspace = copy_artifact(source, output / "workspace")
    evidence = output / "evidence"
    try:
        adapter = resolve_adapter(agent, experiment, workspace)
        checks = (
            _experiment_three(adapter, evidence)
            if experiment == 3
            else _experiment_four(adapter, workspace, evidence)
        )
    except ValueError as error:
        checks = [
            CheckResult(name, "fail", str(error)) for name in CONTRACTS[experiment]
        ]
        adapter = Adapter("unsupported", workspace, workspace)
    digest_after = artifact_digest(source)
    if digest_after != digest_before:
        checks.append(
            CheckResult("source-immutability", "fail", "source digest changed")
        )
    return write_report(
        output,
        agent=agent,
        experiment=experiment,
        source=source,
        digest_before=digest_before,
        digest_after=digest_after,
        adapter=adapter.name,
        checks=checks,
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
    """Evaluate selected frozen artifacts and return nonzero for any non-pass."""
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
                reports.append(json.loads(report_path.read_text()))
            else:
                checks = [
                    CheckResult(name, "fail", f"missing artifact: {source}")
                    for name in CONTRACTS[experiment]
                ]
                report_path = write_report(
                    output,
                    agent=agent,
                    experiment=experiment,
                    source=source,
                    digest_before="",
                    digest_after="",
                    adapter="missing",
                    checks=checks,
                )
                reports.append(json.loads(report_path.read_text()))
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "summary.json").write_text(json.dumps(reports, indent=2) + "\n")
    return (
        0
        if all(
            check["status"] == "pass"
            for report in reports
            for check in report["checks"]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
