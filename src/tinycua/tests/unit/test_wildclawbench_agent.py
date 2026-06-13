"""Unit tests for WildClawBench TinyCUA BaseAgent Adapter."""

import json
import subprocess
from pathlib import Path

import pytest

from tinycua.wildclawbench.agent import TinyCUAAgent
from tinycua.wildclawbench.base_agent import AgentExecution, AgentTaskSpec


@pytest.fixture
def task_spec(tmp_path):
    """Create a minimal AgentTaskSpec for testing."""
    return AgentTaskSpec(
        task_id="unit-test-001",
        task={"type": "simple", "prompt": "test"},
        workspace_path=str(tmp_path / "workspace"),
        prompt="Test prompt",
        timeout_seconds=30,
        output_dir=tmp_path / "output",
        model="test-model",
    )


class TestTinyCUAAgentProperties:
    """Tests for TinyCUAAgent static properties."""

    def test_expects_gateway_returns_false(self):
        """expects_gateway must return False — no long-running process."""
        agent = TinyCUAAgent()
        assert agent.expects_gateway is False

    def test_transcript_container_path_ends_with_jsonl(self):
        """transcript_container_path must end with transcript.jsonl."""
        agent = TinyCUAAgent()
        path = agent.transcript_container_path
        assert isinstance(path, str)
        assert path.endswith("transcript.jsonl")

    def test_prepare_grading_transcript_returns_container_path(self):
        """prepare_grading_transcript returns the same value as transcript_container_path."""
        agent = TinyCUAAgent()
        result = agent.prepare_grading_transcript("any-id")
        assert result == agent.transcript_container_path


class TestRunTaskCommand:
    """Tests for run_task CLI command construction."""

    def test_builds_correct_command(self, task_spec, monkeypatch):
        """Command must include tinycua run, prompt, and all flags."""
        spawned_commands = []

        class MockPopen:
            def __init__(self, cmd, **kwargs):
                spawned_commands.append(cmd)
                self.returncode = 0

            def communicate(self, timeout=None):
                return (b"", b"")

            def kill(self):
                pass

            def wait(self):
                pass

        monkeypatch.setattr(subprocess, "Popen", MockPopen)

        agent = TinyCUAAgent(tinycua_bin="/usr/local/bin/tinycua")
        agent.run_task(task_spec)

        assert len(spawned_commands) == 1
        cmd = spawned_commands[0]
        assert cmd[0] == "/usr/local/bin/tinycua"
        assert cmd[1] == "run"
        assert cmd[2] == "Test prompt"
        assert "--timeout" in cmd
        assert "--output-dir" in cmd
        assert "--workspace" in cmd
        assert "--model" in cmd

    def test_includes_base_url_when_configured(self, task_spec, monkeypatch):
        """Command must include --base-url when base_url is set."""
        spawned_commands = []

        class MockPopen:
            def __init__(self, cmd, **kwargs):
                spawned_commands.append(cmd)
                self.returncode = 0

            def communicate(self, timeout=None):
                return (b"", b"")

            def kill(self):
                pass

            def wait(self):
                pass

        monkeypatch.setattr(subprocess, "Popen", MockPopen)

        agent = TinyCUAAgent(base_url="http://localhost:8080")
        agent.run_task(task_spec)

        cmd = spawned_commands[0]
        assert "--base-url" in cmd
        assert "http://localhost:8080" in cmd

    def test_includes_api_key_when_configured(self, task_spec, monkeypatch):
        """Command must include --api-key when api_key is set."""
        spawned_commands = []

        class MockPopen:
            def __init__(self, cmd, **kwargs):
                spawned_commands.append(cmd)
                self.returncode = 0

            def communicate(self, timeout=None):
                return (b"", b"")

            def kill(self):
                pass

            def wait(self):
                pass

        monkeypatch.setattr(subprocess, "Popen", MockPopen)

        agent = TinyCUAAgent(api_key="secret-key")
        agent.run_task(task_spec)

        cmd = spawned_commands[0]
        assert "--api-key" in cmd
        assert "secret-key" in cmd

    def test_sets_environment_variables(self, task_spec, monkeypatch):
        """Subprocess env must include TINYCUA_BASE_URL, TINYCUA_API_KEY, TINYCUA_MODEL."""
        captured_env = {}

        class MockPopen:
            def __init__(self, cmd, **kwargs):
                captured_env.update(kwargs.get("env", {}))
                self.returncode = 0

            def communicate(self, timeout=None):
                return (b"", b"")

            def kill(self):
                pass

            def wait(self):
                pass

        monkeypatch.setattr(subprocess, "Popen", MockPopen)

        agent = TinyCUAAgent(
            base_url="http://test.local", api_key="test-key", model="custom-model"
        )
        agent.run_task(task_spec)

        assert captured_env.get("TINYCUA_BASE_URL") == "http://test.local"
        assert captured_env.get("TINYCUA_API_KEY") == "test-key"
        assert captured_env.get("TINYCUA_MODEL") == "test-model"


class TestRunTaskExecution:
    """Tests for run_task execution results."""

    def test_returns_agent_execution_with_elapsed_time(self, task_spec, monkeypatch):
        """run_task must return AgentExecution with elapsed_time >= 0."""
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

    def test_returns_error_when_binary_not_found(self, task_spec, monkeypatch):
        """run_task must handle FileNotFoundError gracefully."""

        def raise_fnf(*args, **kwargs):
            raise FileNotFoundError("binary missing")

        monkeypatch.setattr(subprocess, "Popen", raise_fnf)

        agent = TinyCUAAgent(tinycua_bin="missing-bin")
        execution = agent.run_task(task_spec)

        assert execution.error is not None
        assert "not found" in execution.error.lower()

    def test_returns_error_on_non_zero_exit(self, task_spec, monkeypatch):
        """run_task must capture non-zero exit codes as errors."""

        class FailPopen:
            def __init__(self, cmd, **kwargs):
                self.returncode = 1

            def communicate(self, timeout=None):
                return (b"", b"error output")

            def kill(self):
                pass

            def wait(self):
                pass

        monkeypatch.setattr(subprocess, "Popen", FailPopen)

        agent = TinyCUAAgent()
        execution = agent.run_task(task_spec)

        assert execution.error is not None
        assert "exited with code 1" in execution.error

    def test_kills_process_on_timeout(self, task_spec, monkeypatch):
        """run_task must kill the process when timeout occurs."""
        killed = []

        class TimeoutPopen:
            def __init__(self, cmd, **kwargs):
                self._cmd = cmd

            def communicate(self, timeout=None):
                raise subprocess.TimeoutExpired(cmd=self._cmd, timeout=timeout)

            def kill(self):
                killed.append(True)

            def wait(self):
                pass

        monkeypatch.setattr(subprocess, "Popen", TimeoutPopen)

        agent = TinyCUAAgent()
        execution = agent.run_task(task_spec)

        assert execution.error is not None
        assert "timed out" in execution.error.lower()
        assert len(killed) == 1

    def test_returns_timeout_error_on_exit_code_124(self, task_spec, monkeypatch):
        """run_task must treat exit code 124 as timeout."""

        class ExitCode124Popen:
            def __init__(self, cmd, **kwargs):
                self._cmd = cmd

            def communicate(self, timeout=None):
                return (b"", b"")

            def kill(self):
                pass

            def wait(self):
                pass

            @property
            def returncode(self):
                return 124

        monkeypatch.setattr(subprocess, "Popen", ExitCode124Popen)

        agent = TinyCUAAgent()
        execution = agent.run_task(task_spec)

        assert execution.error is not None
        assert "timed out" in execution.error.lower()

    def test_creates_output_directory(self, task_spec, monkeypatch):
        """run_task must create output_dir if it doesn't exist."""
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

    def test_creates_workspace(self, task_spec, monkeypatch):
        """run_task must create workspace_path if it doesn't exist."""
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


class TestCollectUsage:
    """Tests for collect_usage transcript parsing."""

    def test_returns_expected_keys(self, task_spec, tmp_path):
        """collect_usage must return dict with requests, total_tokens, cost."""
        agent = TinyCUAAgent()
        usage = agent.collect_usage("task-001", tmp_path, 1.0)

        assert set(usage.keys()) == {"requests", "total_tokens", "cost"}
        assert isinstance(usage["requests"], int)
        assert usage["cost"] == 0.0

    def test_parses_transcript_for_tokens(self, task_spec, tmp_path):
        """collect_usage must sum total_tokens from transcript events."""
        transcript = tmp_path / "transcript.jsonl"
        events = [
            {"type": "llm.request", "usage": {"total_tokens": 100}},
            {"type": "response.completed", "usage": {"total_tokens": 50}},
            {"type": "tool.call", "usage": {}},
        ]
        with open(transcript, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        agent = TinyCUAAgent()
        usage = agent.collect_usage("task-001", tmp_path, 1.0)

        assert usage["requests"] == 2
        assert usage["total_tokens"] == 150

    def test_returns_zeroed_for_missing_transcript(self, tmp_path):
        """collect_usage must return zeroed values when transcript is missing."""
        agent = TinyCUAAgent()
        usage = agent.collect_usage("task-001", tmp_path, 1.0)

        assert usage["requests"] == 0
        assert usage["total_tokens"] is None
        assert usage["cost"] == 0.0

    def test_handles_malformed_json(self, tmp_path):
        """collect_usage must handle malformed JSON gracefully."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("not valid json\n")

        agent = TinyCUAAgent()
        usage = agent.collect_usage("task-001", tmp_path, 1.0)

        assert usage["requests"] == 0
        assert usage["total_tokens"] is None
        assert usage["cost"] == 0.0


class TestRunTaskTranscript:
    """Tests for transcript/log file creation."""

    def test_creates_transcript_and_log_files(self, task_spec, monkeypatch):
        """run_task must create transcript.jsonl and agent.log in output_dir."""
        output_dir = Path(task_spec.output_dir)

        def mock_popen(cmd, **kwargs):
            transcript = output_dir / "transcript.jsonl"
            log = output_dir / "agent.log"
            transcript.parent.mkdir(parents=True, exist_ok=True)
            transcript.write_text('{"type": "llm.request", "usage": {"total_tokens": 10}}\n')
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
