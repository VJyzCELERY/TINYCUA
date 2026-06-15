"""Integration tests for Hermes agent WildClawBench adapter."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from hermes_benchmark.base_agent import AgentExecution, AgentTaskSpec
from hermes_benchmark.hermes_agent import HermesAgent


@pytest.fixture
def hermes_config(tmp_path):
    """Create a temporary Hermes config YAML file."""
    config = {
        "model": "gpt-4",
        "api_base": "https://api.openai.com/v1",
        "api_key_env": "HERMES_API_KEY",
        "temperature": 0.0,
        "max_tokens": 4096,
        "timeout": 120,
    }
    config_path = tmp_path / "hermes-config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return str(config_path)


@pytest.fixture
def task_spec(tmp_path):
    """Create a minimal AgentTaskSpec for testing."""
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "output"
    return AgentTaskSpec(
        task_id="hermes-test-001",
        task={"type": "simple", "prompt": "test"},
        workspace_path=str(workspace),
        prompt="Write a single sentence about penguins.",
        timeout_seconds=60,
        output_dir=output_dir,
        model="gpt-4",
    )


def test_hermes_agent_properties(hermes_config):
    """Verify HermesAgent static properties match BaseAgent contract."""
    agent = HermesAgent(config_path=hermes_config)
    assert agent.expects_gateway is False
    assert isinstance(agent.transcript_container_path, str)
    assert agent.transcript_container_path.endswith("transcript.jsonl")


def test_hermes_agent_config_validation_invalid_path():
    """Verify HermesAgent raises FileNotFoundError for missing config."""
    with pytest.raises(FileNotFoundError):
        HermesAgent(config_path="/nonexistent/path.yaml")


def test_hermes_agent_config_validation_missing_field(tmp_path):
    """Verify HermesAgent raises ValueError for missing required config fields."""
    config_path = tmp_path / "bad-config.yaml"
    with open(config_path, "w") as f:
        yaml.dump({"model": "gpt-4"}, f)  # missing api_base, api_key_env
    with pytest.raises(ValueError, match="api_base"):
        HermesAgent(config_path=str(config_path))


def test_hermes_agent_docker_command_structure(task_spec, hermes_config, monkeypatch):
    """Verify HermesAgent builds correct docker run command."""

    class MockRun:
        def __init__(self, *args, **kwargs):
            self.returncode = 0
            self.stdout = "image_id_123\n"
            self.stderr = ""

    monkeypatch.setattr(subprocess, "run", MockRun)

    spawned_commands = []

    class MockPopen:
        def __init__(self, cmd, **kwargs):
            spawned_commands.append(cmd)
            self.returncode = 0
            self._stdout = b""
            self._stderr = b""

        def communicate(self, timeout=None):
            return (self._stdout, self._stderr)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def kill(self):
            pass

        def wait(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", MockPopen)

    # Ensure API key env var is set for validation
    monkeypatch.setitem(os.environ, "HERMES_API_KEY", "sk-test-key")

    agent = HermesAgent(config_path=hermes_config)
    execution = agent.run_task(task_spec)

    assert len(spawned_commands) == 1
    cmd = spawned_commands[0]
    assert cmd[0] == "docker"
    assert cmd[1] == "run"
    assert "--rm" in cmd
    assert "hermes-agent" in cmd
    assert execution.error is None


def test_hermes_agent_missing_api_key(hermes_config, task_spec, monkeypatch):
    """Verify HermesAgent returns error when required API key env var is missing."""
    monkeypatch.delenv("HERMES_API_KEY", raising=False)

    agent = HermesAgent(config_path=hermes_config)
    execution = agent.run_task(task_spec)

    assert execution.error is not None
    assert "HERMES_API_KEY" in execution.error


def test_hermes_agent_docker_build_failure(hermes_config, task_spec, monkeypatch):
    """Verify HermesAgent handles Docker build failure gracefully."""
    def raise_build_error(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["docker", "build"])

    monkeypatch.setattr(subprocess, "run", raise_build_error)
    monkeypatch.setitem(os.environ, "HERMES_API_KEY", "sk-test-key")

    agent = HermesAgent(config_path=hermes_config)
    execution = agent.run_task(task_spec)

    assert execution.error is not None
    assert "build" in execution.error.lower() or "docker" in execution.error.lower()


def test_hermes_agent_container_timeout(hermes_config, task_spec, monkeypatch):
    """Verify HermesAgent handles container timeout gracefully."""

    class MockRun:
        def __init__(self, *args, **kwargs):
            self.returncode = 0
            self.stdout = "image_id_123\n"
            self.stderr = ""

    monkeypatch.setattr(subprocess, "run", MockRun)

    class TimeoutPopen:
        def __init__(self, cmd, **kwargs):
            self._cmd = cmd

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd=self._cmd, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def kill(self):
            pass

        def wait(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", TimeoutPopen)
    monkeypatch.setitem(os.environ, "HERMES_API_KEY", "sk-test-key")

    agent = HermesAgent(config_path=hermes_config)
    execution = agent.run_task(task_spec)

    assert execution.error is not None
    assert "timed out" in execution.error.lower()


def test_hermes_collect_usage_empty(task_spec, tmp_path, hermes_config):
    """Verify collect_usage returns zeroed values when no artifacts exist."""
    agent = HermesAgent(config_path=hermes_config)
    usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)

    assert usage["requests"] == 0
    assert usage["total_tokens"] is None
    assert usage["cost"] == 0.0


def test_hermes_collect_usage_with_transcript(task_spec, tmp_path, hermes_config):
    """Verify collect_usage parses Hermes transcript for usage data."""
    transcript_path = tmp_path / "transcript.jsonl"
    transcript_data = [
        {"type": "llm.request", "usage": {"total_tokens": 100}},
        {"type": "response.completed", "usage": {"total_tokens": 50}},
    ]
    with open(transcript_path, "w") as f:
        for event in transcript_data:
            f.write(json.dumps(event) + "\n")

    agent = HermesAgent(config_path=hermes_config)
    usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)

    assert usage["requests"] == 2
    assert usage["total_tokens"] == 150


