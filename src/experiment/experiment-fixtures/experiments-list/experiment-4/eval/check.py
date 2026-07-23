"""Deterministically score the Experiment 4 integrated web app."""

import ast
import http.client
import json
import os
import re
import selectors
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from playwright.sync_api import sync_playwright


PASS_THRESHOLD = 15
CRITICAL_CATEGORIES = (
    "run_entrypoint",
    "pid_output",
    "uv_environment",
    "python_compiles",
    "health_endpoint",
    "post_blocks",
    "get_blocks",
    "sqlite_schema",
    "sqlite_persistence",
    "invalid_request",
    "page_structure",
    "visible_controls",
    "browser_submit",
    "frontend_api_transport",
    "browser_reload",
)
BYPASS_DIRECTIVES = ("# noqa", "# type: ignore", "pragma: no cover")
VIRTUAL_ENV = ".venv"


def require(condition: bool, message: str) -> str:
    """Return evidence or fail one binary check."""
    if not condition:
        raise ValueError(message)
    return message


def request(method: str, path: str, body: str | None = None) -> tuple[int, object]:
    """Send one local HTTP request and decode its JSON response."""
    connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=2)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    connection.request(method, path, body, headers)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    try:
        payload = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        payload = raw.decode(errors="replace")
    return response.status, payload


def wait_for_health() -> tuple[int, object]:
    """Wait briefly for run.sh to start the integrated app."""
    for _ in range(240):
        try:
            response = request("GET", "/health")
            if response[0] == 200:
                return response
        except OSError:
            time.sleep(0.25)
    raise AssertionError("run.sh did not start a healthy server")


def evaluate(checks: dict[str, Callable[[], str]], result: Path) -> int:
    """Run binary checks and write category evidence."""
    outcomes: dict[str, bool] = {}
    evidence: dict[str, list[str]] = {}
    for name, check in checks.items():
        try:
            evidence[name] = [check()]
            outcomes[name] = True
        except Exception as error:
            evidence[name] = [f"failed: {error}"]
            outcomes[name] = False
            print(f"{name}: {error}", file=sys.stderr)
    total = sum(outcomes.values())
    score = {
        "categories": {
            name: {
                "points": int(outcomes[name]),
                "max_points": 1,
                "evidence": evidence[name],
            }
            for name in checks
        },
        "total": total,
        "pass_threshold": PASS_THRESHOLD,
        "critical_categories": list(CRITICAL_CATEGORIES),
    }
    (result / "score.json").write_text(json.dumps(score, indent=2) + "\n")
    return int(
        total < PASS_THRESHOLD
        or any(not outcomes[name] for name in CRITICAL_CATEGORIES)
    )


def main() -> int:
    """Launch run.sh and score build, API, storage, and browser behavior."""
    submission = Path(sys.argv[1])
    result = Path(sys.argv[2])
    workspace = result / "submission"
    shutil.copytree(
        submission,
        workspace,
        ignore=shutil.ignore_patterns(".agent_scripts", ".venv"),
    )
    state: dict[str, object] = {}

    def compile_python() -> str:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "-x",
                rf"(^|/){re.escape(VIRTUAL_ENV)}/",
                str(workspace),
            ],
            check=True,
        )
        return "Python compilation passed"

    def lint_python() -> str:
        subprocess.run(
            ["ruff", "check", "--exclude", VIRTUAL_ENV, str(workspace)], check=True
        )
        return "Ruff passed"

    def no_bypasses() -> str:
        bypasses = [
            f"{path.relative_to(workspace)}: {directive}"
            for path in workspace.rglob("*.py")
            if VIRTUAL_ENV not in path.parts
            for directive in BYPASS_DIRECTIVES
            if directive in path.read_text()
        ]
        return require(
            not bypasses, f"no bypass directives; found {', '.join(bypasses)}"
        )

    def modular_structure() -> str:
        sources = [
            path
            for path in workspace.rglob("*.py")
            if VIRTUAL_ENV not in path.parts
            and "tests" not in path.parts
            and not path.name.startswith("test_")
        ]

        def module_names(path: Path) -> set[str]:
            parts = list(path.relative_to(workspace).with_suffix("").parts)
            if parts[0] == "src":
                parts = parts[1:]
            if parts[-1] == "__init__":
                parts.pop()
            return {".".join(parts)} if parts else set()

        modules = {
            module: source
            for source in sources
            for module in module_names(source)
        }

        def imports(path: Path) -> list[str]:
            package = list(path.relative_to(workspace).with_suffix("").parts[:-1])
            if package[:1] == ["src"]:
                package = package[1:]
            names: list[str] = []
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    names.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        base = package[: len(package) - node.level + 1]
                        if node.module:
                            names.append(".".join(base + node.module.split(".")))
                        else:
                            names.extend(".".join(base + [alias.name]) for alias in node.names)
                    elif node.module:
                        names.append(node.module)
            return names

        for source in sources:
            for imported in imports(source):
                local = next(
                    (
                        module
                        for module, owner in modules.items()
                        if owner != source
                        and (
                            imported == module
                            or imported.startswith(f"{module}.")
                            or module.startswith(f"{imported}.")
                        )
                    ),
                    None,
                )
                if local:
                    return f"{source.relative_to(workspace)} imports local module {local}"
        return require(False, "production modules import one another")

    def project_documentation() -> str:
        docs = workspace / "docs"
        documents = [path for path in workspace.glob("README*") if path.is_file()]
        documents += [path for path in docs.rglob("*") if path.is_file()]
        return require(
            any(path.read_bytes().strip() for path in documents),
            "a non-empty root README or docs/ file documents the project",
        )

    def test_result() -> subprocess.CompletedProcess[str]:
        if "test_result" not in state:
            state["test_result"] = subprocess.run(
                ["uv", "run", "pytest", "-q"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        completed = state["test_result"]
        assert isinstance(completed, subprocess.CompletedProcess)
        return completed

    def tests_pass() -> str:
        completed = test_result()
        return require(
            completed.returncode == 0,
            "automated tests exist and all pass",
        )

    def integration_tests() -> str:
        files = [
            path
            for path in workspace.rglob("test_*.py")
            if VIRTUAL_ENV not in path.parts
            and "integration" in path.as_posix().lower()
        ]
        return require(
            bool(files) and test_result().returncode == 0,
            "integration tests exist and pass with the full test suite",
        )

    def coverage_80() -> str:
        report = workspace / ".coverage.json"
        completed = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "-q",
                "--cov=.",
                "--cov-config=/eval/coveragerc",
                f"--cov-report=json:{report}",
            ],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        coverage = json.loads(report.read_text())["totals"]["percent_covered"]
        return require(
            completed.returncode == 0 and coverage >= 80,
            f"passing tests cover {coverage:.2f}% of project code",
        )

    run_script = workspace / "run.sh"
    server: subprocess.Popen[bytes] | None = None
    try:
        if run_script.is_file():
            server = subprocess.Popen(
                ["sh", "run.sh"],
                cwd=workspace,
                env=os.environ | {"PORT": "8765"},
                stdout=subprocess.PIPE,
                bufsize=0,
                start_new_session=True,
            )

        def health() -> str:
            return require(
                wait_for_health() == (200, {"ok": True}),
                "/health returns exact JSON contract",
            )

        def pid_output() -> str:
            assert server is not None and server.stdout is not None
            selector = selectors.DefaultSelector()
            selector.register(server.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 15
            output = ""
            while selector.select(max(0, deadline - time.monotonic())):
                chunk = os.read(server.stdout.fileno(), 4096)
                if not chunk:
                    break
                output += chunk.decode(errors="replace")
                if match := re.search(r"(?:^|\n)(\d+)\r?\n", output):
                    pid = int(match.group(1))
                    os.kill(pid, 0)
                    threading.Thread(target=server.stdout.read, daemon=True).start()
                    return f"run.sh printed live app PID {pid}"
                if time.monotonic() >= deadline:
                    break
            raise ValueError("run.sh did not print a live numeric app PID")

        def post_block() -> str:
            status, block = request(
                "POST", "/blocks", json.dumps({"text": "HTTP block"})
            )
            state["http_block"] = block
            return require(
                status == 201
                and isinstance(block, dict)
                and isinstance(block.get("id"), int)
                and block.get("text") == "HTTP block",
                "POST /blocks returns 201 and the created block",
            )

        def get_blocks() -> str:
            status, blocks = request("GET", "/blocks")
            block = state["http_block"]
            return require(
                status == 200
                and isinstance(blocks, list)
                and isinstance(block, dict)
                and any(item.get("id") == block.get("id") for item in blocks),
                "GET /blocks returns the created block",
            )

        def sqlite_schema() -> str:
            database = workspace / "notion.db"
            with sqlite3.connect(database) as connection:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(blocks)"
                    ).fetchall()
                }
            return require(
                {"id", "text"}.issubset(columns),
                "SQLite blocks table has id and text columns",
            )

        def sqlite_persistence() -> str:
            block = state["http_block"]
            with sqlite3.connect(workspace / "notion.db") as connection:
                row = connection.execute(
                    "SELECT text FROM blocks WHERE id = ?", (block["id"],)
                ).fetchone()
            return require(
                row == ("HTTP block",), "HTTP-created block persists in SQLite"
            )

        def invalid_request() -> str:
            before = request("GET", "/blocks")[1]
            status, _ = request("POST", "/blocks", json.dumps({}))
            after = request("GET", "/blocks")[1]
            return require(
                status >= 400 and before == after,
                "invalid POST fails without corrupting stored blocks",
            )

        def browser_checks() -> tuple[str, str, str, str, str]:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path="/usr/bin/chromium"
                )
                page = browser.new_page()
                page.goto("http://127.0.0.1:8765/", wait_until="networkidle")
                structure = require(
                    page.title() == "Notion Blocks"
                    and page.locator("h1").inner_text() == "Notion Blocks",
                    "page title and H1 match",
                )
                controls = require(
                    page.locator("#block-text").is_visible()
                    and page.get_by_role("button", name="Add Block").is_visible(),
                    "input and Add Block button are visible",
                )
                page.locator("#block-text").fill("Browser block")
                page.get_by_role("button", name="Add Block").click()
                page.get_by_text("Browser block", exact=True).wait_for()
                submitted = "browser submission renders the block"
                _, blocks = request("GET", "/blocks")
                transported = require(
                    isinstance(blocks, list)
                    and any(item.get("text") == "Browser block" for item in blocks),
                    "browser-created block is available through the backend API",
                )
                page.reload(wait_until="networkidle")
                reloaded = require(
                    page.get_by_text("Browser block", exact=True).is_visible(),
                    "browser reload renders the persisted block",
                )
                browser.close()
            return structure, controls, submitted, transported, reloaded

        def browser_result(index: int) -> str:
            if "browser" not in state:
                state["browser"] = browser_checks()
            browser = state["browser"]
            assert isinstance(browser, tuple)
            return browser[index]

        checks: dict[str, Callable[[], str]] = {
            "run_entrypoint": lambda: require(
                run_script.is_file(), "root run.sh entrypoint exists"
            ),
            "pid_output": pid_output,
            "uv_environment": lambda: require(
                (workspace / ".venv" / "bin" / "python").is_file(),
                "uv created the project virtual environment",
            ),
            "python_compiles": compile_python,
            "ruff_clean": lint_python,
            "no_bypass_directives": no_bypasses,
            "modular_structure": modular_structure,
            "project_documentation": project_documentation,
            "tests_pass": tests_pass,
            "integration_tests": integration_tests,
            "coverage_80": coverage_80,
            "health_endpoint": health,
            "post_blocks": post_block,
            "get_blocks": get_blocks,
            "sqlite_schema": sqlite_schema,
            "sqlite_persistence": sqlite_persistence,
            "invalid_request": invalid_request,
            "page_structure": lambda: browser_result(0),
            "visible_controls": lambda: browser_result(1),
            "browser_submit": lambda: browser_result(2),
            "frontend_api_transport": lambda: browser_result(3),
            "browser_reload": lambda: browser_result(4),
        }
        return evaluate(checks, result)
    finally:
        if server is not None and server.poll() is None:
            os.killpg(server.pid, signal.SIGTERM)
            server.wait(timeout=5)
        shutil.rmtree(workspace)


if __name__ == "__main__":
    raise SystemExit(main())
