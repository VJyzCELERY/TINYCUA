"""Run arbitrary agent argv in a validated worktree without a shell."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SCHEMA_VERSION = 4
LEGACY_SCHEMA_VERSIONS = (2, 3)
TERMINATION_GRACE_SECONDS = 1
POLL_INTERVAL_SECONDS = 0.25
POLL_HEARTBEAT_SECONDS = 30
MONITOR_HEARTBEAT_SECONDS = 1
SESSION_CAPTURE_CHUNK_SIZE = 4096
SESSION_CAPTURE_LINE_LIMIT = 8192
STATE_READ_ATTEMPTS = 3
STATE_READ_RETRY_SECONDS = 0.01
ACTIVE = ("pending", "running", "stopping")
TERMINAL = ("succeeded", "failed", "cancelled")
SESSION_CAPTURE_STATES = ("unavailable", "captured", "provided", "conflicting")
RUN_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
CONTEXT_KEYS = ("goal", "role", "phase", "harness", "model", "session")
CONTEXT_RE = re.compile(r"[\x00-\x1f\x7f]")
SECRET_RE = re.compile(
    r"(?i)(?:\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|secret|"
    r"password|credential|authorization|bearer)\b|\bgh[pousr]_[A-Za-z0-9_]{12,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{12,}|\bsk-[A-Za-z0-9_-]{12,})"
)


class RunError(ValueError):
    """A runner input or local state record is unsafe."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_path(root: Path, path: Path, field: str) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise RunError(f"{field} escapes the repository") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise RunError(f"{field} is a symlink")
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise RunError(f"{field} escapes the repository") from exc


def _worktree(root: Path, value: object) -> Path:
    if not isinstance(value, str):
        raise RunError("worktree must be a path")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    _safe_path(root, candidate, "worktree")
    try:
        path = candidate.resolve(strict=True)
    except OSError as exc:
        raise RunError("worktree is missing or unsafe") from exc
    _safe_path(root, path, "worktree")
    if not path.is_dir() or path.is_symlink():
        raise RunError("worktree is missing or unsafe")
    return path


def _run_id(value: object) -> str:
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise RunError("run_id is invalid")
    return value


def _context_value(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > 256:
        raise RunError(f"{field} is invalid")
    if CONTEXT_RE.search(value) or SECRET_RE.search(value):
        raise RunError(f"{field} contains unsafe data")
    return value


def _context(value: dict[str, object]) -> dict[str, str | None]:
    if set(value) != set(CONTEXT_KEYS):
        raise RunError("agent context is invalid")
    context = {field: _context_value(value[field], field) for field in CONTEXT_KEYS}
    if context["role"] is not None and context["role"] not in {"planner", "worker", "reviewer"}:
        raise RunError("role is invalid")
    if context["harness"] is not None and context["harness"] not in {
        "current",
        "opencode",
        "codex",
        "claude",
    }:
        raise RunError("harness is invalid")
    return context


class _SessionCapture:
    """Extract one opaque session ID from supported structured provider output."""

    def __init__(self, harness: str | None, session: str | None) -> None:
        self._harness = harness
        self._session = session
        self._state = "provided" if session is not None else "unavailable"
        self._buffer = bytearray()
        self._discarding = False
        self._last_provider_output_at: str | None = None
        self._lock = threading.Lock()

    def _candidate(self, value: object) -> str | None:
        if not isinstance(value, dict):
            return None
        candidate = None
        if self._harness == "opencode":
            candidate = value.get("sessionID")
        elif self._harness == "codex" and value.get("type") == "thread.started":
            candidate = value.get("thread_id")
        elif self._harness == "claude" and (
            (value.get("type") == "system" and value.get("subtype") == "init")
            or value.get("type") == "result"
        ):
            candidate = value.get("session_id")
        try:
            return _context_value(candidate, "session")
        except RunError:
            return None

    def _observe(self, line: bytes) -> None:
        try:
            candidate = self._candidate(json.loads(line.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if candidate is None:
            return
        with self._lock:
            if self._state == "conflicting":
                return
            if self._session is None:
                self._session = candidate
                self._state = "captured"
            elif self._session != candidate:
                self._session = None
                self._state = "conflicting"

    def feed(self, chunk: bytes) -> None:
        """Consume output without retaining raw provider records."""
        with self._lock:
            self._last_provider_output_at = _now()
        for part in chunk.splitlines(keepends=True):
            if self._discarding:
                if part.endswith(b"\n"):
                    self._discarding = False
                continue
            if len(self._buffer) + len(part) > SESSION_CAPTURE_LINE_LIMIT:
                self._buffer.clear()
                self._discarding = not part.endswith(b"\n")
                continue
            self._buffer.extend(part)
            if part.endswith(b"\n"):
                self._observe(bytes(self._buffer).strip())
                self._buffer.clear()

    def finish(self) -> None:
        """Process a final bounded record after the provider exits."""
        if not self._discarding and self._buffer:
            self._observe(bytes(self._buffer).strip())
        self._buffer.clear()

    def result(self) -> tuple[str | None, str, str | None]:
        """Return the safe session value and capture state."""
        with self._lock:
            return self._session, self._state, self._last_provider_output_at


def _drain_stdout(stream: object, capture: _SessionCapture) -> None:
    """Drain provider output while retaining only recognized session metadata."""
    if stream is None or not hasattr(stream, "read"):
        return
    while chunk := stream.read(SESSION_CAPTURE_CHUNK_SIZE):
        capture.feed(chunk)
    capture.finish()


def _apply_capture(record: dict, capture: _SessionCapture, include_activity: bool = False) -> bool:
    session, state, activity = capture.result()
    changed = False
    if record["session"] == session and record["session_capture"] == state:
        changed = False
    else:
        record["session"] = session
        record["session_capture"] = state
        changed = True
    if include_activity and record["last_provider_output_at"] != activity:
        record["last_provider_output_at"] = activity
        changed = True
    return changed


def _state_root(root: Path) -> Path:
    path = root / ".agents/local/state/agent-runs"
    _safe_path(root, path, "agent run directory")
    path.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIRECTORY_MODE)
    if not path.is_dir() or path.is_symlink():
        raise RunError("agent run directory is unsafe")
    path.chmod(PRIVATE_DIRECTORY_MODE)
    return path


def _run_directory(root: Path, run_id: str, create: bool = False) -> Path:
    directory = _state_root(root) / _run_id(run_id)
    _safe_path(root, directory, "agent run")
    if create:
        directory.mkdir(mode=PRIVATE_DIRECTORY_MODE)
    if not directory.is_dir() or directory.is_symlink():
        raise RunError("agent run is missing or unsafe")
    directory.chmod(PRIVATE_DIRECTORY_MODE)
    return directory


def _active_path(root: Path, worktree: Path) -> Path:
    """Return the private, canonical-worktree run index path."""
    directory = _state_root(root) / "active"
    _safe_path(root, directory, "active agent run directory")
    directory.mkdir(exist_ok=True, mode=PRIVATE_DIRECTORY_MODE)
    if not directory.is_dir() or directory.is_symlink():
        raise RunError("active agent run directory is unsafe")
    directory.chmod(PRIVATE_DIRECTORY_MODE)
    path = directory / f"{uuid.uuid5(uuid.NAMESPACE_URL, str(worktree)).hex}.json"
    _safe_path(root, path, "active agent run")
    return path


def _active_record(root: Path, worktree: Path) -> tuple[Path, str, dict]:
    path = _active_path(root, worktree)
    if path.is_symlink() or not path.is_file():
        raise RunError("no agent run is recorded for worktree")
    path.chmod(PRIVATE_FILE_MODE)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunError("active agent run is malformed") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "run_id", "worktree"}
        or value["schema_version"] not in {*LEGACY_SCHEMA_VERSIONS, SCHEMA_VERSION}
        or isinstance(value["schema_version"], bool)
        or value["worktree"] != str(worktree)
    ):
        raise RunError("active agent run is invalid")
    run_id = _run_id(value["run_id"])
    _, _, record = _load(root, run_id)
    if record["worktree"] != str(worktree):
        raise RunError("active agent run worktree is invalid")
    return path, run_id, record


def _reserve_active_run(root: Path, worktree: Path, run_id: str) -> None:
    path = _active_path(root, worktree)
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            PRIVATE_FILE_MODE,
        )
    except FileExistsError as exc:
        _, active_run_id, _ = _active_record(root, worktree)
        raise RunError(
            f"agent run {active_run_id} is recorded for worktree; fetch it before starting another"
        ) from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), PRIVATE_FILE_MODE)
        handle.write(
            json.dumps(
                {"schema_version": SCHEMA_VERSION, "run_id": run_id, "worktree": str(worktree)},
                sort_keys=True,
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())


def _clear_active_run(root: Path, run_id: str) -> None:
    _, _, record = _load(root, run_id)
    if record["status"] not in TERMINAL:
        raise RunError("active agent run is not terminal")
    worktree = _worktree(root, record["worktree"])
    index = _active_path(root, worktree)
    if index.is_symlink():
        raise RunError("active agent run is unsafe")
    if not index.exists():
        return
    path, active_run_id, _ = _active_record(root, worktree)
    if active_run_id != record["run_id"]:
        raise RunError("active agent run does not match collected run")
    path.unlink()


def _atomic_write(root: Path, path: Path, value: object) -> None:
    _safe_path(root, path.parent, "agent run directory")
    if path.is_symlink() or not path.parent.is_dir():
        raise RunError("agent run destination is unsafe")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), PRIVATE_FILE_MODE)
            handle.write(json.dumps(value, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(PRIVATE_FILE_MODE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _process_start(pid: int) -> int | None:
    try:
        return int(Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[21])
    except (OSError, ValueError, IndexError):
        return None


def _process_matches(pid: object, start: object) -> bool:
    if isinstance(pid, bool) or not isinstance(pid, int):
        return False
    if isinstance(start, bool) or not isinstance(start, int):
        return False
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
        return fields[2] != "Z" and int(fields[21]) == start
    except (OSError, ValueError, IndexError):
        return False


def _liveness(record: dict) -> dict[str, bool]:
    """Return safe lifecycle diagnostics without exposing process identities."""
    return {
        "monitor_alive": _process_matches(record["monitor_pid"], record["monitor_start"]),
        "agent_alive": _process_matches(record["child_pid"], record["child_start"]),
    }


def _record(root: Path, directory: Path) -> tuple[Path, dict]:
    path = directory / "state.json"
    _safe_path(root, path, "agent run state")
    if path.is_symlink():
        raise RunError("agent run state is missing or unsafe")
    value = None
    for _ in range(STATE_READ_ATTEMPTS):
        try:
            if not path.is_file():
                raise FileNotFoundError
            path.chmod(PRIVATE_FILE_MODE)
            value = json.loads(path.read_text(encoding="utf-8"))
            break
        except FileNotFoundError:
            time.sleep(STATE_READ_RETRY_SECONDS)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunError("agent run state is malformed") from exc
    if value is None:
        raise RunError("agent run state is missing or unsafe")
    version_two_keys = {
        "schema_version", "run_id", "worktree", "created_at", "updated_at", "status",
        "monitor_pid", "monitor_start", "child_pid", "child_start", "exit_code",
        "finished_at", *CONTEXT_KEYS,
    }
    version_three_keys = {"session_capture", "resumed_from", *version_two_keys}
    keys = {"last_provider_output_at", *version_three_keys}
    if not isinstance(value, dict):
        raise RunError("agent run state has unknown or missing fields")
    schema_version = value.get("schema_version")
    if isinstance(schema_version, bool) or schema_version not in {
        *LEGACY_SCHEMA_VERSIONS,
        SCHEMA_VERSION,
    }:
        raise RunError("agent run state schema_version is invalid")
    if schema_version == 2:
        if set(value) != version_two_keys:
            raise RunError("agent run state has unknown or missing fields")
        value = {
            **value,
            "schema_version": 3,
            "session_capture": "provided" if value["session"] is not None else "unavailable",
            "resumed_from": None,
        }
    if value["schema_version"] == 3:
        if set(value) != version_three_keys:
            raise RunError("agent run state has unknown or missing fields")
        value = {**value, "schema_version": SCHEMA_VERSION, "last_provider_output_at": None}
    elif set(value) != keys:
        raise RunError("agent run state has unknown or missing fields")
    if value["run_id"] != directory.name or not RUN_ID_RE.fullmatch(value["run_id"]):
        raise RunError("agent run state run_id is invalid")
    _worktree(root, value["worktree"])
    if value["status"] not in (*ACTIVE, *TERMINAL):
        raise RunError("agent run state status is invalid")
    for field in ("monitor_pid", "monitor_start", "child_pid", "child_start", "exit_code"):
        if value[field] is not None and (
            isinstance(value[field], bool) or not isinstance(value[field], int)
        ):
            raise RunError(f"agent run state {field} is invalid")
    for field in ("created_at", "updated_at"):
        if not isinstance(value[field], str) or len(value[field]) > 64:
            raise RunError(f"agent run state {field} is invalid")
    if value["finished_at"] is not None and not isinstance(value["finished_at"], str):
        raise RunError("agent run state finished_at is invalid")
    if value["status"] in TERMINAL and value["finished_at"] is None:
        raise RunError("terminal agent run is missing finished_at")
    _context({field: value[field] for field in CONTEXT_KEYS})
    if value["session_capture"] not in SESSION_CAPTURE_STATES:
        raise RunError("agent run session_capture is invalid")
    if value["session_capture"] in {"captured", "provided"} and value["session"] is None:
        raise RunError("agent run session_capture is invalid")
    if value["session_capture"] in {"unavailable", "conflicting"} and value["session"] is not None:
        raise RunError("agent run session_capture is invalid")
    if value["resumed_from"] is not None:
        _run_id(value["resumed_from"])
    if value["last_provider_output_at"] is not None and (
        not isinstance(value["last_provider_output_at"], str)
        or len(value["last_provider_output_at"]) > 64
    ):
        raise RunError("agent run last_provider_output_at is invalid")
    return path, value


def _load(root: Path, run_id: str) -> tuple[Path, Path, dict]:
    directory = _run_directory(root, run_id)
    path, record = _record(root, directory)
    return directory, path, record


def _collection(record: dict) -> dict:
    return {
        "run_id": record["run_id"],
        "status": record["status"],
        "exit_code": record["exit_code"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "finished_at": record["finished_at"],
        "last_provider_output_at": record["last_provider_output_at"],
        "session_capture": record["session_capture"],
        "resumed_from": record["resumed_from"],
        **{field: record[field] for field in ("goal", "role", "phase", "harness", "session")},
        **_liveness(record),
    }


def _finish(root: Path, path: Path, record: dict, status: str, exit_code: int | None) -> None:
    record["status"] = status
    record["exit_code"] = exit_code
    record["finished_at"] = _now()
    record["updated_at"] = _now()
    _atomic_write(root, path, record)


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    return True


def _recorded_group_matches(pgid: object, start: object) -> bool:
    """Verify a recorded group without targeting a reused leader PID."""
    if isinstance(pgid, bool) or not isinstance(pgid, int):
        return False
    if isinstance(start, bool) or not isinstance(start, int):
        return False
    current_start = _process_start(pgid)
    if current_start is None:
        return _group_exists(pgid)
    try:
        return current_start == start and os.getpgid(pgid) == pgid
    except OSError:
        return False


def _terminate_group(pgid: int, child: subprocess.Popen | None = None) -> bool:
    if child is not None and child.poll() is not None:
        child.wait()
    if not _group_exists(pgid):
        return True
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + TERMINATION_GRACE_SECONDS
    while _group_exists(pgid) and time.monotonic() < deadline:
        if child is not None and child.poll() is not None:
            child.wait()
        time.sleep(0.05)
    if not _group_exists(pgid):
        return True
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + TERMINATION_GRACE_SECONDS
    while _group_exists(pgid) and time.monotonic() < deadline:
        if child is not None and child.poll() is not None:
            child.wait()
        time.sleep(0.05)
    return not _group_exists(pgid)


def _monitor(root: Path, run_id: str) -> None:
    directory, path, _ = _load(root, run_id)
    try:
        payload = sys.stdin.buffer.read(65537)
        if len(payload) > 65536:
            raise RunError("agent argv is too large")
        command = json.loads(payload.decode("utf-8"))
        if not isinstance(command, list) or not 1 <= len(command) <= 64:
            raise RunError("agent argv must be a non-empty bounded array")
        if any(not isinstance(item, str) or not item or len(item) > 4096 or "\0" in item for item in command):
            raise RunError("agent argv contains an unsafe argument")
        _, record = _record(root, directory)
        if record["status"] == "stopping":
            _finish(root, path, record, "cancelled", None)
            return
        if record["status"] in TERMINAL:
            return
        worktree = _worktree(root, record["worktree"])
        with subprocess.Popen(
            command,
            cwd=worktree,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        ) as child:
            capture = _SessionCapture(record["harness"], record["session"])
            reader = threading.Thread(
                target=_drain_stdout, args=(child.stdout, capture), daemon=True
            )
            reader.start()
            record["child_pid"] = child.pid
            record["child_start"] = _process_start(child.pid)
            record["status"] = "running"
            record["updated_at"] = _now()
            _atomic_write(root, path, record)
            next_heartbeat = time.monotonic() + MONITOR_HEARTBEAT_SECONDS
            while child.poll() is None:
                _, current = _record(root, directory)
                if current["status"] == "stopping":
                    stopped = _terminate_group(child.pid, child)
                    child.wait()
                    reader.join(TERMINATION_GRACE_SECONDS)
                    _apply_capture(current, capture, include_activity=True)
                    _finish(root, path, current, "cancelled" if stopped else "failed", child.returncode)
                    break
                changed = _apply_capture(current, capture)
                if time.monotonic() >= next_heartbeat:
                    changed = _apply_capture(current, capture, include_activity=True) or changed
                    current["updated_at"] = _now()
                    changed = True
                    next_heartbeat = time.monotonic() + MONITOR_HEARTBEAT_SECONDS
                if changed:
                    _atomic_write(root, path, current)
                time.sleep(0.05)
            else:
                code = child.wait()
                stopped = _terminate_group(child.pid, child)
                reader.join(TERMINATION_GRACE_SECONDS)
                _, current = _record(root, directory)
                _apply_capture(current, capture, include_activity=True)
                _finish(
                    root,
                    path,
                    current,
                    "cancelled"
                    if current["status"] == "stopping" and stopped
                    else "succeeded"
                    if code == 0 and stopped
                    else "failed",
                    code,
                )
    except (OSError, RunError, UnicodeDecodeError, json.JSONDecodeError):
        try:
            _, current = _record(root, directory)
            if current["status"] in ACTIVE:
                _finish(root, path, current, "failed", 127)
        except (OSError, RunError):
            pass


def _start(
    root: Path,
    worktree_value: str,
    command: list[str],
    context: dict[str, str | None],
    resumed_from: str | None = None,
) -> dict:
    worktree = _worktree(root, worktree_value)
    if not command:
        raise RunError("agent argv is required after --")
    if resumed_from is not None:
        _run_id(resumed_from)
    run_id = uuid.uuid4().hex
    _reserve_active_run(root, worktree, run_id)
    try:
        directory = _run_directory(root, run_id, create=True)
    except OSError:
        _active_path(root, worktree).unlink(missing_ok=True)
        raise
    record = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "worktree": str(worktree),
        "created_at": _now(),
        "updated_at": _now(),
        "status": "pending",
        "monitor_pid": None,
        "monitor_start": None,
        "child_pid": None,
        "child_start": None,
        "exit_code": None,
        "finished_at": None,
        "last_provider_output_at": None,
        "session_capture": "provided" if context["session"] is not None else "unavailable",
        "resumed_from": resumed_from,
        **context,
    }
    path = directory / "state.json"
    _atomic_write(root, path, record)
    try:
        monitor = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--root", str(root), "_monitor", run_id],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        record["monitor_pid"] = monitor.pid
        record["monitor_start"] = _process_start(monitor.pid)
        record["updated_at"] = _now()
        _atomic_write(root, path, record)
        if monitor.stdin is None:
            raise RunError("agent monitor could not receive argv")
        monitor.stdin.write(json.dumps(command).encode("utf-8"))
        monitor.stdin.close()
    except (OSError, RunError):
        _finish(root, path, record, "failed", 127)
        raise
    result = {"run_id": run_id, "status": "pending"}
    if resumed_from is not None:
        result["resumed_from"] = resumed_from
    return result


def _resume(root: Path, source_run_id: str, command: list[str]) -> dict:
    """Start a linked run with the failed run's validated session context."""
    _, _, source = _load(root, source_run_id)
    if source["status"] != "failed":
        raise RunError("agent run is not resumable")
    if source["session"] is None or source["session_capture"] not in {"captured", "provided"}:
        raise RunError("agent run is not resumable")
    _clear_active_run(root, source_run_id)
    context = {field: source[field] for field in CONTEXT_KEYS}
    return _start(root, source["worktree"], command, context, resumed_from=source_run_id)


def _wait_for_terminal(root: Path, run_id: str) -> tuple[Path, dict]:
    deadline = time.monotonic() + (TERMINATION_GRACE_SECONDS * 3)
    while time.monotonic() < deadline:
        directory, path, record = _load(root, run_id)
        if record["status"] in TERMINAL:
            return directory, record
        if record["status"] == "stopping" and not _process_matches(
            record["monitor_pid"], record["monitor_start"]
        ):
            pid = record["child_pid"]
            stopped = False
            if _recorded_group_matches(pid, record["child_start"]):
                stopped = _terminate_group(pid)
            _finish(root, path, record, "cancelled" if stopped else "failed", None)
            return directory, record
        time.sleep(0.05)
    raise RunError("agent run did not reach a terminal state")


def _stop(root: Path, run_id: str) -> dict:
    directory, path, record = _load(root, run_id)
    if record["status"] in TERMINAL:
        return _collection(record)
    if record["status"] == "running":
        pid = record["child_pid"]
        if not _recorded_group_matches(pid, record["child_start"]):
            raise RunError("agent process identity cannot be verified")
        record["status"] = "stopping"
        record["updated_at"] = _now()
        _atomic_write(root, path, record)
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif record["status"] == "pending":
        record["status"] = "stopping"
        record["updated_at"] = _now()
        _atomic_write(root, path, record)
    directory, record = _wait_for_terminal(root, run_id)
    return _collection(record)


def _poll_heartbeat(record: dict, elapsed: float) -> str:
    """Format safe progress metadata without provider output."""
    liveness = _liveness(record)
    activity = record["last_provider_output_at"] or "none"
    return (
        f"waiting for agent run {record['run_id']}: elapsed={int(elapsed)}s "
        f"status={record['status']} monitor_alive={liveness['monitor_alive']} "
        f"agent_alive={liveness['agent_alive']} session_capture={record['session_capture']} "
        f"last_provider_output_at={activity}"
    )


def _stderr_progress(message: str) -> None:
    """Render one poll heartbeat without contaminating terminal JSON stdout."""
    if sys.stderr.isatty():
        print(f"\r\033[2K{message}", end="", file=sys.stderr, flush=True)
    else:
        print(message, file=sys.stderr, flush=True)


def _poll(root: Path, run_id: str, progress: Callable[[str], None]) -> dict:
    """Wait for a detached run without affecting its process lifecycle."""
    started_at = time.monotonic()
    next_heartbeat = started_at + POLL_HEARTBEAT_SECONDS
    while True:
        _, _, record = _load(root, run_id)
        if record["status"] in TERMINAL:
            return _collection(record)
        if record["monitor_pid"] is not None and record["monitor_start"] is not None and not _process_matches(
            record["monitor_pid"], record["monitor_start"]
        ):
            time.sleep(0.05)
            _, _, record = _load(root, run_id)
            if record["status"] in TERMINAL:
                return _collection(record)
            if _process_matches(record["monitor_pid"], record["monitor_start"]):
                continue
            raise RunError("agent monitor is no longer running")
        now = time.monotonic()
        if now >= next_heartbeat:
            progress(_poll_heartbeat(record, now - started_at))
            next_heartbeat = now + POLL_HEARTBEAT_SECONDS
        time.sleep(POLL_INTERVAL_SECONDS)


def _active(root: Path, worktree_value: str) -> dict:
    worktree = _worktree(root, worktree_value)
    _, run_id, record = _active_record(root, worktree)
    return {
        "run_id": run_id,
        "status": record["status"],
        "last_provider_output_at": record["last_provider_output_at"],
        "session_capture": record["session_capture"],
        "resumed_from": record["resumed_from"],
        **{field: record[field] for field in ("goal", "role", "phase", "harness", "session")},
        **_liveness(record),
    }


def _start_arguments(argv: list[str]) -> tuple[str, list[str], dict[str, str | None]]:
    if "--" not in argv:
        raise RunError("agent argv is required after --")
    delimiter = argv.index("--")
    if delimiter < 1 or delimiter == len(argv) - 1:
        raise RunError("agent argv is required after --")
    options = argv[1:delimiter]
    if len(options) % 2:
        raise RunError("agent context is invalid")
    context: dict[str, object] = dict.fromkeys(CONTEXT_KEYS)
    for index in range(0, len(options), 2):
        key = options[index].removeprefix("--")
        if options[index] != f"--{key}" or key not in CONTEXT_KEYS or context[key] is not None:
            raise RunError("agent context is invalid")
        context[key] = options[index + 1]
    return argv[0], argv[delimiter + 1 :], _context(context)


def _resume_arguments(argv: list[str]) -> tuple[str, list[str]]:
    if len(argv) < 3 or argv[1] != "--":
        raise RunError("agent argv is required after --")
    return _run_id(argv[0]), argv[2:]


def _arguments(argv: list[str]) -> tuple[str, list[str]]:
    if argv[:1] == ["resume"]:
        return "resume", argv[1:]
    if len(argv) == 2 and argv[0] in {"fetch", "poll", "stop", "active", "_monitor"}:
        return argv[0], argv[1:]
    return "start", argv


def main(
    argv: list[str] | None = None,
    *,
    root: Path | None = None,
    output: Callable[[str], None] = print,
    error: Callable[[str], None] = print,
    progress: Callable[[str], None] | None = None,
) -> int:
    """Start, resume, fetch, poll, or stop a generic detached agent run."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments[:1] == ["--root"] and len(arguments) >= 3:
            root = Path(arguments[1])
            arguments = arguments[2:]
        repository_path = root or Path(__file__).resolve().parents[2]
        if repository_path.is_symlink():
            raise RunError("repository root is missing or unsafe")
        repository = repository_path.resolve()
        if not repository.is_dir():
            raise RunError("repository root is missing or unsafe")
        action, values = _arguments(arguments)
        if action == "_monitor":
            _monitor(repository, _run_id(values[0]))
            return 0
        if action == "start":
            worktree, command, context = _start_arguments(values)
            result = _start(repository, worktree, command, context)
        elif action == "resume":
            source_run_id, command = _resume_arguments(values)
            result = _resume(repository, source_run_id, command)
        elif action == "fetch":
            directory, _, record = _load(repository, _run_id(values[0]))
            result = _collection(record)
        elif action == "poll":
            result = _poll(repository, _run_id(values[0]), progress or _stderr_progress)
        elif action == "active":
            result = _active(repository, values[0])
        else:
            result = _stop(repository, _run_id(values[0]))
        if action in {"fetch", "poll", "stop"} and result["status"] in TERMINAL:
            _clear_active_run(repository, _run_id(values[0]))
        output(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, RunError) as exc:
        error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
