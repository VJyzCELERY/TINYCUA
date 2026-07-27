"""Score Experiment 4 through its public browser behavior."""

import http.client
import json
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TextIO

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


PASS_THRESHOLD = 9
CRITICAL_CATEGORIES = (
    "start_script",
    "application_starts",
    "python_backend",
    "block_create",
    "block_edit",
    "block_delete",
    "reload_persistence",
    "sqlite_persistence",
    "restart_persistence",
)
STARTUP_TIMEOUT_SECONDS = 300
SQLITE_HEADER = b"SQLite format 3\x00"
ADD_BLOCK = re.compile(r"(add|create|new).*?(block|text|note)", re.IGNORECASE)
EDIT_BLOCK = re.compile(r"(edit|update).*?(block|text|note)", re.IGNORECASE)
DELETE_BLOCK = re.compile(r"(delete|remove).*?(block|text|note)", re.IGNORECASE)
SAVE_CHANGES = re.compile(r"(save|update|confirm)", re.IGNORECASE)


@dataclass
class Server:
    """One evaluator-owned application process group."""

    process: subprocess.Popen[bytes]
    stdout: TextIO
    stderr: TextIO
    port: int


def require(condition: bool, message: str) -> str:
    """Return evidence or fail one binary check."""
    if not condition:
        raise ValueError(message)
    return message


def free_port() -> int:
    """Reserve an available loopback port long enough to obtain its number."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def request(port: int) -> tuple[int, bytes]:
    """Fetch the public root without assuming application routes."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
    connection.request("GET", "/")
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, body


def wait_for_page(server: Server) -> str:
    """Wait for the public page while failing promptly on a dead entrypoint."""
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if server.process.poll() is not None:
            raise ValueError(f"start.sh exited with code {server.process.returncode}")
        try:
            status, body = request(server.port)
        except OSError:
            time.sleep(0.25)
            continue
        if 200 <= status < 400 and body.strip():
            return "root page responded"
        time.sleep(0.25)
    raise ValueError("start.sh did not expose a usable root page")


def launch(workspace: Path, result: Path, attempt: int) -> Server:
    """Start the candidate in an evaluator-owned process group."""
    require((workspace / "start.sh").is_file(), "root start.sh exists")
    stdout = (result / f"app-{attempt}.stdout.log").open("w")
    stderr = (result / f"app-{attempt}.stderr.log").open("w")
    port = free_port()
    try:
        return Server(
            subprocess.Popen(
                ["sh", "start.sh"],
                cwd=workspace,
                env=os.environ | {"PORT": str(port)},
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            ),
            stdout,
            stderr,
            port,
        )
    except OSError:
        stdout.close()
        stderr.close()
        raise


def stop(server: Server) -> None:
    """Terminate the evaluator-owned process group without trusting the app."""
    try:
        if server.process.poll() is None:
            os.killpg(server.process.pid, signal.SIGTERM)
            try:
                server.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(server.process.pid, signal.SIGKILL)
                server.process.wait(timeout=5)
    finally:
        server.stdout.close()
        server.stderr.close()


def group_has_python(server: Server) -> str:
    """Confirm the public app is backed by a Python process in its group."""
    completed = subprocess.run(
        ["ps", "-eo", "pgid=,args="], capture_output=True, check=True, text=True
    )
    group = str(server.process.pid)
    matches = [
        line
        for line in completed.stdout.splitlines()
        if line.strip().split(maxsplit=1)[0] == group and "python" in line.lower()
    ]
    return require(bool(matches), "start.sh process group includes a Python backend")


def text_field(page):
    """Return the visible text field used for block input."""
    fields = page.get_by_role("textbox")
    require(fields.count() > 0, "a visible accessible text field exists")
    return fields.first


def action(page, pattern: re.Pattern[str], description: str):
    """Return the first clearly labelled block action."""
    controls = page.get_by_role("button", name=pattern)
    require(controls.count() > 0, f"a clearly labelled {description} control exists")
    return controls.first


def edit_field(page, original: str):
    """Prefer the editor prefilled with the selected block's current text."""
    fields = page.get_by_role("textbox")
    for index in range(fields.count()):
        field = fields.nth(index)
        try:
            if field.input_value() == original:
                return field
        except PlaywrightError:
            continue
    return fields.last


def browser_flow(port: int, state: dict[str, object]) -> tuple[str, ...]:
    """Exercise create, edit, delete, and reload through the rendered UI."""
    retained = "retained-block-8e7c5b"
    edited = "edited-block-8e7c5b"
    deleted = "deleted-block-8e7c5b"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path="/usr/bin/chromium")
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")
        field = text_field(page)
        add = action(page, ADD_BLOCK, "add block")
        field.fill(retained)
        add.click()
        page.get_by_text(retained, exact=True).wait_for()
        page.get_by_text(retained, exact=True).click()
        action(page, EDIT_BLOCK, "edit block").click()
        edit_field(page, retained).fill(edited)
        action(page, SAVE_CHANGES, "save changes").click()
        page.get_by_text(edited, exact=True).wait_for()
        text_field(page).fill(deleted)
        add.click()
        page.get_by_text(deleted, exact=True).wait_for()
        page.get_by_text(deleted, exact=True).click()
        action(page, DELETE_BLOCK, "delete block").click()
        page.get_by_text(deleted, exact=True).wait_for(state="hidden")
        page.reload(wait_until="domcontentloaded")
        page.get_by_text(edited, exact=True).wait_for()
        browser.close()
    state["retained_text"] = edited
    state["deleted_text"] = deleted
    return (
        "browser created a block",
        "browser edited the selected block",
        "browser deleted the selected block",
        "browser reload retained the edited block",
    )


def sqlite_contains(workspace: Path, marker: str) -> str:
    """Find a SQLite database containing the retained browser-created value."""
    for path in workspace.rglob("*"):
        if {".venv", "node_modules"}.intersection(path.parts) or not path.is_file():
            continue
        try:
            with path.open("rb") as candidate:
                if candidate.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                    continue
            with sqlite3.connect(path) as database:
                tables = database.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
                for (table,) in tables:
                    quoted = '"' + str(table).replace('"', '""') + '"'
                    rows = database.execute(f"SELECT * FROM {quoted}").fetchall()
                    if any(marker in str(value) for row in rows for value in row):
                        return f"SQLite database {path.relative_to(workspace)} retained data"
        except (OSError, sqlite3.DatabaseError):
            continue
    raise ValueError("no SQLite database retained the browser-created block")


def evaluate(checks: dict[str, Callable[[], str]], result: Path) -> int:
    """Run binary checks and write category evidence."""
    outcomes: dict[str, bool] = {}
    categories: dict[str, dict[str, object]] = {}
    for name, check in checks.items():
        try:
            evidence = check()
            outcomes[name] = True
        except Exception as error:
            evidence = f"failed: {error}"
            outcomes[name] = False
            print(f"{name}: {error}", file=sys.stderr)
        categories[name] = {
            "points": int(outcomes[name]),
            "max_points": 1,
            "evidence": [evidence],
        }
    score = {
        "categories": categories,
        "total": sum(outcomes.values()),
        "pass_threshold": PASS_THRESHOLD,
        "critical_categories": list(CRITICAL_CATEGORIES),
    }
    (result / "score.json").write_text(json.dumps(score, indent=2) + "\n")
    return int(
        sum(outcomes.values()) < PASS_THRESHOLD
        or any(not outcomes[name] for name in CRITICAL_CATEGORIES)
    )


def main() -> int:
    """Launch the app, exercise its public workflow, and verify persistence."""
    submission = Path(sys.argv[1])
    result = Path(sys.argv[2])
    workspace = result / "submission"
    shutil.copytree(
        submission,
        workspace,
        ignore=shutil.ignore_patterns(".agent_scripts", ".venv", "node_modules", "__pycache__"),
    )
    state: dict[str, object] = {}

    def server() -> Server:
        current = state.get("server")
        if isinstance(current, Server):
            return current
        current = launch(workspace, result, 1)
        state["server"] = current
        state["page_ready"] = wait_for_page(current)
        return current

    def application_starts() -> str:
        server()
        return str(state["page_ready"])

    def browser_result(index: int) -> str:
        if "browser" not in state:
            active = server()
            state["browser"] = browser_flow(active.port, state)
        browser = state["browser"]
        assert isinstance(browser, tuple)
        return browser[index]

    def sqlite_persistence() -> str:
        browser_result(3)
        return sqlite_contains(workspace, str(state["retained_text"]))

    def restart_persistence() -> str:
        previous = server()
        stop(previous)
        state.pop("server")
        restarted = launch(workspace, result, 2)
        state["server"] = restarted
        wait_for_page(restarted)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path="/usr/bin/chromium")
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{restarted.port}/", wait_until="domcontentloaded")
            page.get_by_text(str(state["retained_text"]), exact=True).wait_for()
            require(
                page.get_by_text(str(state["deleted_text"]), exact=True).count() == 0,
                "deleted block remains absent after restart",
            )
            browser.close()
        return "restart retained the edited block"

    try:
        checks: dict[str, Callable[[], str]] = {
            "start_script": lambda: require(
                (workspace / "start.sh").is_file(), "root start.sh exists"
            ),
            "application_starts": application_starts,
            "python_backend": lambda: group_has_python(server()),
            "block_create": lambda: browser_result(0),
            "block_edit": lambda: browser_result(1),
            "block_delete": lambda: browser_result(2),
            "reload_persistence": lambda: browser_result(3),
            "sqlite_persistence": sqlite_persistence,
            "restart_persistence": restart_persistence,
        }
        return evaluate(checks, result)
    finally:
        active = state.get("server")
        if isinstance(active, Server):
            stop(active)
        shutil.rmtree(workspace)


if __name__ == "__main__":
    raise SystemExit(main())
