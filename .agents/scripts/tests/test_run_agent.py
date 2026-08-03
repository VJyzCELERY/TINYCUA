"""Behavior tests for the generic detached agent runner."""

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import run_agent


def run(root: Path, *args: str) -> tuple[int, dict | None, str]:
    """Run the generic runner against an isolated repository root."""
    output: list[str] = []
    errors: list[str] = []
    code = run_agent.main(list(args), root=root, output=output.append, error=errors.append)
    return code, json.loads(output[0]) if output else None, "\n".join(errors)


def wait_for_terminal(root: Path, run_id: str) -> dict:
    """Fetch a final collection without relying on a raw process identity."""
    for _ in range(200):
        code, result, error = run(root, "fetch", run_id)
        assert (code, error) == (0, "")
        assert result is not None
        if result["status"] not in {"pending", "running", "stopping"}:
            return result
        time.sleep(0.02)
    pytest.fail("agent run did not become terminal")


def test_runner_executes_opaque_argv_without_shell_and_returns_only_run_id(tmp_path):
    marker = tmp_path / "must-not-exist"

    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--",
        sys.executable,
        "-c",
        "import sys; print(sys.argv[1])",
        f"; touch {marker}",
    )

    assert (code, error) == (0, "")
    assert started is not None
    assert set(started) == {"run_id", "status"}
    assert not marker.exists()
    result = wait_for_terminal(tmp_path, started["run_id"])
    assert "stdout" not in result
    assert "stderr" not in result
    assert "pid" not in json.dumps(result).lower()
    code, collected, error = run(tmp_path, "stop", started["run_id"])
    assert (code, error) == (0, "")
    assert collected is not None
    assert collected["status"] == "succeeded"
    state = tmp_path / ".agents/local/state/agent-runs" / started["run_id"]
    assert "touch" not in (state / "state.json").read_text(encoding="utf-8")
    assert not (state / "stdout.log").exists()
    assert not (state / "stderr.log").exists()


def test_fetch_never_returns_or_persists_provider_output(tmp_path):
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--",
        sys.executable,
        "-c",
        "import sys; print('x' * 20000); print('y' * 20000, file=sys.stderr)",
    )

    assert (code, error) == (0, "")
    assert started is not None
    result = wait_for_terminal(tmp_path, started["run_id"])
    assert result["status"] == "succeeded"
    assert "stdout" not in result
    assert "stderr" not in result
    directory = tmp_path / ".agents/local/state/agent-runs" / started["run_id"]
    assert not (directory / "stdout.log").exists()
    assert not (directory / "stderr.log").exists()


def test_poll_waits_for_terminal_result_and_clears_active_run(tmp_path):
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--",
        sys.executable,
        "-c",
        "import time; time.sleep(0.1); raise SystemExit(7)",
    )

    assert (code, error) == (0, "")
    assert started is not None
    started_at = time.monotonic()
    code, result, error = run(tmp_path, "poll", started["run_id"])

    assert (code, error) == (0, "")
    assert time.monotonic() - started_at >= 0.05
    assert result is not None
    assert result["status"] == "failed"
    assert result["exit_code"] == 7
    assert "stdout" not in result
    assert "stderr" not in result
    code, active, error = run(tmp_path, "active", str(tmp_path))
    assert (code, active) == (1, None)
    assert "no agent run" in error


def test_fetch_reports_healthy_nested_agent_work(tmp_path):
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--",
        sys.executable,
        "-c",
        "import subprocess, sys; subprocess.run([sys.executable, '-c', "
        "'import time; time.sleep(0.3)'], check=True)",
    )

    assert (code, error) == (0, "")
    assert started is not None
    for _ in range(100):
        code, result, error = run(tmp_path, "fetch", started["run_id"])
        assert (code, error) == (0, "")
        assert result is not None
        if result["status"] == "running":
            assert result["monitor_alive"] is True
            assert result["agent_alive"] is True
            break
        time.sleep(0.01)
    else:
        pytest.fail("nested agent work did not become healthy")

    code, result, error = run(tmp_path, "poll", started["run_id"])
    assert (code, error) == (0, "")
    assert result is not None
    assert result["status"] == "succeeded"


def test_poll_reports_monitor_loss_without_stopping_agent(tmp_path):
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--",
        sys.executable,
        "-c",
        "import time; time.sleep(10)",
    )

    assert (code, error) == (0, "")
    assert started is not None
    state_path = tmp_path / ".agents/local/state/agent-runs" / started["run_id"] / "state.json"
    for _ in range(100):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            time.sleep(0.01)
            continue
        if state["status"] == "running" and state["monitor_pid"] and state["child_pid"]:
            break
        time.sleep(0.01)
    else:
        pytest.fail("monitor and agent did not start")
    os.kill(state["monitor_pid"], signal.SIGKILL)

    polled: list[tuple[int, dict | None, str]] = []
    waiter = threading.Thread(target=lambda: polled.append(run(tmp_path, "poll", started["run_id"])))
    waiter.start()
    try:
        waiter.join(1)
        assert not waiter.is_alive()
        assert polled == [(1, None, "agent monitor is no longer running")]
        assert run_agent._process_matches(state["child_pid"], state["child_start"])
    finally:
        run(tmp_path, "stop", started["run_id"])
        waiter.join(1)


def test_runner_captures_a_structured_session_and_resumes_failed_run(tmp_path):
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--harness",
        "codex",
        "--model",
        "configured-model",
        "--",
        sys.executable,
        "-c",
        "import json; print(json.dumps({'type': 'thread.started', 'thread_id': 'thread-42'})); raise SystemExit(7)",
    )

    assert (code, error) == (0, "")
    assert started is not None
    code, failed, error = run(tmp_path, "poll", started["run_id"])
    assert (code, error) == (0, "")
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["session"] == "thread-42"
    assert failed["session_capture"] == "captured"
    assert "stdout" not in failed
    assert "stderr" not in failed

    code, resumed, error = run(
        tmp_path,
        "resume",
        started["run_id"],
        "--",
        sys.executable,
        "-c",
        "pass",
    )

    assert (code, error) == (0, "")
    assert resumed is not None
    assert resumed["resumed_from"] == started["run_id"]
    result = wait_for_terminal(tmp_path, resumed["run_id"])
    assert result["status"] == "succeeded"
    assert result["session"] == "thread-42"
    assert result["session_capture"] == "provided"
    assert result["resumed_from"] == started["run_id"]


@pytest.mark.parametrize(
    ("harness", "event", "session"),
    (
        ("opencode", {"type": "step_start", "sessionID": "opencode-42"}, "opencode-42"),
        (
            "claude",
            {"type": "system", "subtype": "init", "session_id": "claude-42"},
            "claude-42",
        ),
    ),
)
def test_runner_captures_supported_harness_session_event(tmp_path, harness, event, session):
    command = f"import json; print({json.dumps(event)!r}); raise SystemExit(7)"
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--harness",
        harness,
        "--model",
        "configured-model",
        "--",
        sys.executable,
        "-c",
        command,
    )

    assert (code, error) == (0, "")
    assert started is not None
    code, failed, error = run(tmp_path, "poll", started["run_id"])
    assert (code, error) == (0, "")
    assert failed is not None
    assert failed["session"] == session
    assert failed["session_capture"] == "captured"


def test_runner_does_not_wait_for_an_orphaned_stdout_writer(tmp_path):
    marker = tmp_path / "orphan-pid"
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--",
        sys.executable,
        "-c",
        "import pathlib, subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'], "
        "start_new_session=True); pathlib.Path('orphan-pid').write_text(str(child.pid))",
    )

    assert (code, error) == (0, "")
    assert started is not None
    for _ in range(100):
        if marker.exists():
            break
        time.sleep(0.01)
    else:
        pytest.fail("orphaned stdout writer did not start")
    orphan_pid = int(marker.read_text(encoding="utf-8"))
    polled: list[tuple[int, dict | None, str]] = []
    waiter = threading.Thread(target=lambda: polled.append(run(tmp_path, "poll", started["run_id"])))
    waiter.start()
    try:
        waiter.join(2)
        assert not waiter.is_alive()
        assert polled[0][0] == 0
    finally:
        try:
            os.kill(orphan_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        waiter.join(2)


def test_runner_rejects_resume_after_conflicting_structured_sessions(tmp_path):
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--harness",
        "codex",
        "--model",
        "configured-model",
        "--",
        sys.executable,
        "-c",
        "import json; print(json.dumps({'type': 'thread.started', 'thread_id': 'thread-1'})); "
        "print(json.dumps({'type': 'thread.started', 'thread_id': 'thread-2'})); raise SystemExit(7)",
    )

    assert (code, error) == (0, "")
    assert started is not None
    code, failed, error = run(tmp_path, "poll", started["run_id"])
    assert (code, error) == (0, "")
    assert failed is not None
    assert failed["session"] is None
    assert failed["session_capture"] == "conflicting"
    code, resumed, error = run(
        tmp_path,
        "resume",
        started["run_id"],
        "--",
        sys.executable,
        "-c",
        "pass",
    )
    assert (code, resumed) == (1, None)
    assert "not resumable" in error


def test_runner_retains_safe_goal_role_metadata_without_command_argv(tmp_path):
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--goal",
        "owner/repo#42",
        "--role",
        "worker",
        "--phase",
        "implementing",
        "--harness",
        "codex",
        "--model",
        "configured-model",
        "--session",
        "session-42",
        "--",
        sys.executable,
        "-c",
        "print('never persist this')",
    )

    assert (code, error) == (0, "")
    assert started is not None
    result = wait_for_terminal(tmp_path, started["run_id"])
    assert result["goal"] == "owner/repo#42"
    assert result["role"] == "worker"
    assert result["phase"] == "implementing"
    assert result["harness"] == "codex"
    assert result["session"] == "session-42"
    state = (
        tmp_path / ".agents/local/state/agent-runs" / started["run_id"] / "state.json"
    )
    assert "configured-model" in state.read_text(encoding="utf-8")
    assert "never persist this" not in state.read_text(encoding="utf-8")


def test_rejects_second_active_run_for_worktree(tmp_path):
    code, first, error = run(
        tmp_path,
        str(tmp_path),
        "--",
        sys.executable,
        "-c",
        "import time; time.sleep(10)",
    )

    assert (code, error) == (0, "")
    assert first is not None
    try:
        code, active, error = run(tmp_path, "active", str(tmp_path))
        assert (code, error) == (0, "")
        assert active is not None
        assert active["run_id"] == first["run_id"]
        assert active["status"] in run_agent.ACTIVE
        code, second, error = run(
            tmp_path,
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "pass",
        )

        assert code == 1
        assert second is None
        assert first["run_id"] in error
    finally:
        run(tmp_path, "stop", first["run_id"])


def test_keeps_run_state_and_logs_owner_only(tmp_path):
    previous_umask = os.umask(0o022)
    try:
        code, started, error = run(
            tmp_path,
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "import sys; print('stdout'); print('stderr', file=sys.stderr)",
        )

        assert (code, error) == (0, "")
        assert started is not None
        result = wait_for_terminal(tmp_path, started["run_id"])
        assert result["status"] == "succeeded"
        directory = tmp_path / ".agents/local/state/agent-runs" / started["run_id"]
        paths = (
            directory.parent,
            directory,
            directory / "state.json",
        )
        assert all(path.stat().st_mode & 0o077 == 0 for path in paths)
    finally:
        os.umask(previous_umask)


def test_stop_terminates_only_the_matching_process_group_and_collects_output(tmp_path):
    marker = tmp_path / "child-pid"
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--",
        sys.executable,
        "-c",
        "import pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)']); "
        "pathlib.Path('child-pid').write_text(str(child.pid)); time.sleep(10)",
    )

    assert (code, error) == (0, "")
    assert started is not None
    for _ in range(100):
        if marker.exists():
            break
        time.sleep(0.02)
    else:
        pytest.fail("background child did not start")
    child_pid = int(marker.read_text(encoding="utf-8"))
    code, active, error = run(tmp_path, "fetch", started["run_id"])
    assert (code, error) == (0, "")
    assert active is not None
    assert active["status"] == "running"

    code, stopped, error = run(tmp_path, "stop", started["run_id"])

    assert (code, error) == (0, "")
    assert stopped is not None
    assert stopped["status"] == "cancelled"
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


def test_stop_recovers_monitor_loss_when_the_monitor_is_killed(tmp_path):
    marker = tmp_path / "child-pid"
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--",
        sys.executable,
        "-c",
        "import pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)']); "
        "pathlib.Path('child-pid').write_text(str(child.pid)); time.sleep(10)",
    )

    assert (code, error) == (0, "")
    assert started is not None
    state_path = tmp_path / ".agents/local/state/agent-runs" / started["run_id"] / "state.json"
    for _ in range(100):
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if marker.exists() and state["status"] == "running" and state["monitor_pid"]:
            break
        time.sleep(0.02)
    else:
        pytest.fail("monitor and child did not start")
    child_pid = int(marker.read_text(encoding="utf-8"))
    os.kill(state["monitor_pid"], signal.SIGKILL)

    code, stopped, error = run(tmp_path, "stop", started["run_id"])

    assert (code, error) == (0, "")
    assert stopped is not None
    assert stopped["status"] in {"cancelled", "failed"}
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


def test_stop_kills_group_after_monitor_and_group_leader_exit(tmp_path):
    marker = tmp_path / "child-pid"
    code, started, error = run(
        tmp_path,
        str(tmp_path),
        "--",
        sys.executable,
        "-c",
        "import pathlib, signal, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', "
        "'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(10)']); "
        "pathlib.Path('child-pid').write_text(str(child.pid)); time.sleep(10)",
    )

    assert (code, error) == (0, "")
    assert started is not None
    state_path = (
        tmp_path / ".agents/local/state/agent-runs" / started["run_id"] / "state.json"
    )
    for _ in range(100):
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if marker.exists() and state["status"] == "running" and state["monitor_pid"]:
            break
        time.sleep(0.02)
    else:
        pytest.fail("monitor and child did not start")
    child_pid = int(marker.read_text(encoding="utf-8"))
    os.kill(state["monitor_pid"], signal.SIGKILL)
    os.kill(state["child_pid"], signal.SIGTERM)
    for _ in range(100):
        if not run_agent._process_matches(state["child_pid"], state["child_start"]):
            break
        time.sleep(0.02)
    else:
        pytest.fail("process-group leader did not exit")

    try:
        code, stopped, error = run(tmp_path, "stop", started["run_id"])

        assert (code, error) == (0, "")
        assert stopped is not None
        assert stopped["status"] == "cancelled"
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        try:
            os.kill(child_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_fetch_rejects_an_unsafe_or_unknown_run_id(tmp_path):
    code, _, error = run(tmp_path, "fetch", "../other")

    assert code == 1
    assert "run_id" in error

    run_id = "a" * 32
    state = tmp_path / ".agents/local/state/agent-runs" / run_id
    state.mkdir(parents=True)
    (state / "state.json").write_text("{}", encoding="utf-8")
    code, _, error = run(tmp_path, "fetch", run_id)

    assert code == 1
    assert "state" in error
