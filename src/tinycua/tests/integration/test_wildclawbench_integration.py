"""Integration tests for WildClawBench TinyCUA BaseAgent Adapter."""

import json
import subprocess
from pathlib import Path

import pytest

from tinycua.wildclawbench.base_agent import AgentExecution, AgentTaskSpec
from tinycua.wildclawbench.agent import TinyCUAAgent


@pytest.fixture
def task_spec(tmp_path):
    """Create a minimal AgentTaskSpec for testing."""
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "output"
    return AgentTaskSpec(
        task_id="test-task-001",
        task={"type": "simple", "prompt": "test"},
        workspace_path=str(workspace),
        prompt="Say hello",
        timeout_seconds=30,
        output_dir=output_dir,
        model="test-model",
    )


def test_agent_expects_gateway_is_false():
    """Verify expects_gateway returns False (no long-running process needed)."""
    agent = TinyCUAAgent()
    assert agent.expects_gateway is False


def test_transcript_container_path_is_string():
    """Verify transcript_container_path returns a valid string path."""
    agent = TinyCUAAgent()
    path = agent.transcript_container_path
    assert isinstance(path, str)
    assert path.endswith("transcript.jsonl")


def test_prepare_grading_transcript_returns_container_path():
    """Verify prepare_grading_transcript returns transcript_container_path."""
    agent = TinyCUAAgent()
    result = agent.prepare_grading_transcript("any-task-id")
    assert result == agent.transcript_container_path


def test_run_task_spawns_correct_command(task_spec, monkeypatch):
    """Verify run_task builds the correct CLI command and spawns subprocess."""
    spawned_commands = []

    class MockPopen:
        def __init__(self, cmd, **kwargs):
            spawned_commands.append(cmd)
            self.returncode = 0
            self._stdout = b""
            self._stderr = b""

        def communicate(self, timeout=None):
            return (self._stdout, self._stderr)

        def kill(self):
            pass

        def wait(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", MockPopen)

    agent = TinyCUAAgent(tinycua_bin="/usr/bin/tinycua")
    execution = agent.run_task(task_spec)

    assert len(spawned_commands) == 1
    cmd = spawned_commands[0]
    assert cmd[0] == "/usr/bin/tinycua"
    assert cmd[1] == "run"
    assert cmd[2] == "Say hello"
    assert "--timeout" in cmd
    assert "--output-dir" in cmd
    assert "--workspace" in cmd
    assert "--model" in cmd
    assert execution.error is None


def test_run_task_returns_elapsed_time(task_spec, monkeypatch):
    """Verify run_task returns an AgentExecution with elapsed_time."""
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: type(
            "MockProc",
            (),
            {
                "communicate": lambda self, timeout=None: (b"", b""),
                "returncode": 0,
                "kill": lambda self: None,
                "wait": lambda self: None,
            },
        )(),
    )

    agent = TinyCUAAgent()
    execution = agent.run_task(task_spec)

    assert isinstance(execution, AgentExecution)
    assert execution.elapsed_time >= 0
    assert execution.error is None


def test_run_task_handles_timeout(task_spec, monkeypatch):
    """Verify run_task terminates subprocess on timeout and returns error."""

    class TimeoutPopen:
        def __init__(self, cmd, **kwargs):
            self._cmd = cmd
            self.returncode = None

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd=self._cmd, timeout=timeout)

        def kill(self):
            self.returncode = -9

        def wait(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", TimeoutPopen)

    agent = TinyCUAAgent()
    execution = agent.run_task(task_spec)

    assert execution.error is not None
    assert "timed out" in execution.error.lower()


def test_run_task_handles_binary_not_found(task_spec, monkeypatch):
    """Verify run_task returns error when tinycua binary is not found."""

    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("tinycua not found")

    monkeypatch.setattr(subprocess, "Popen", raise_file_not_found)

    agent = TinyCUAAgent(tinycua_bin="nonexistent-tinycua")
    execution = agent.run_task(task_spec)

    assert execution.error is not None
    assert "not found" in execution.error.lower()


def test_run_task_creates_output_dir(task_spec, monkeypatch):
    """Verify run_task creates output directory if it doesn't exist."""
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: type(
            "MockProc",
            (),
            {
                "communicate": lambda self, timeout=None: (b"", b""),
                "returncode": 0,
                "kill": lambda self: None,
                "wait": lambda self: None,
            },
        )(),
    )

    agent = TinyCUAAgent()
    agent.run_task(task_spec)

    assert Path(task_spec.output_dir).exists()


def test_collect_usage_returns_expected_keys(task_spec, tmp_path):
    """Verify collect_usage returns dict with requests, total_tokens, cost."""
    agent = TinyCUAAgent()
    usage = agent.collect_usage("test-task-001", tmp_path, 1.0)

    assert "requests" in usage
    assert "total_tokens" in usage
    assert "cost" in usage
    assert isinstance(usage["requests"], int)
    assert usage["cost"] == 0.0


def test_collect_usage_parses_transcript(task_spec, tmp_path):
    """Verify collect_usage parses transcript.jsonl for token counts."""
    transcript_path = tmp_path / "transcript.jsonl"
    transcript_data = [
        {"type": "llm.request", "usage": {"total_tokens": 100}},
        {"type": "response.completed", "usage": {"total_tokens": 50}},
        {"type": "tool.call", "usage": {}},
    ]
    with open(transcript_path, "w") as f:
        for event in transcript_data:
            f.write(json.dumps(event) + "\n")

    agent = TinyCUAAgent()
    usage = agent.collect_usage("test-task-001", tmp_path, 1.0)

    assert usage["requests"] == 2  # llm.request + response.completed
    assert usage["total_tokens"] == 150
    assert usage["cost"] == 0.0


def test_collect_usage_missing_transcript_returns_zeroed(tmp_path):
    """Verify collect_usage returns zeroed values when transcript is missing."""
    agent = TinyCUAAgent()
    usage = agent.collect_usage("test-task-001", tmp_path, 1.0)

    assert usage["requests"] == 0
    assert usage["total_tokens"] is None
    assert usage["cost"] == 0.0


def test_run_task_creates_transcript_and_log(task_spec, monkeypatch):
    """Verify run_task creates transcript.jsonl and agent.log in output_dir after execution."""
    output_dir = Path(task_spec.output_dir)

    def mock_popen(cmd, **kwargs):
        # Simulate CLI writing transcript and log files
        transcript = output_dir / "transcript.jsonl"
        log = output_dir / "agent.log"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(
            '{"type": "llm.request", "usage": {"total_tokens": 10}}\n'
        )
        log.write_text("task completed\n")

        class MockProc:
            returncode = 0

            def communicate(self, timeout=None):
                return (b"", b"")

            def kill(self):
                pass

            def wait(self):
                pass

        return MockProc()

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    agent = TinyCUAAgent()
    execution = agent.run_task(task_spec)

    assert execution.error is None
    assert (output_dir / "transcript.jsonl").exists()
    assert (output_dir / "agent.log").exists()


def test_run_task_creates_workspace(task_spec, monkeypatch):
    """Verify run_task creates workspace directory if it doesn't exist."""
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: type(
            "MockProc",
            (),
            {
                "communicate": lambda self, timeout=None: (b"", b""),
                "returncode": 0,
                "kill": lambda self: None,
                "wait": lambda self: None,
            },
        )(),
    )

    agent = TinyCUAAgent()
    agent.run_task(task_spec)

    assert Path(task_spec.workspace_path).exists()
