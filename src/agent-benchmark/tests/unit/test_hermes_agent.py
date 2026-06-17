"""Unit tests for HermesAgent adapter and HermesConfig."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from agent_benchmark.base_agent import AgentExecution, AgentTaskSpec
from agent_benchmark.agents.hermes_agent import HermesAgent, HermesConfig, load_hermes_config


# ---------------------------------------------------------------------------
# HermesConfig validation tests
# ---------------------------------------------------------------------------

class TestHermesConfig:
    def test_config_dataclass_fields(self):
        config = HermesConfig(model="gpt-4", api_base="https://api.openai.com/v1", api_key_env="HERMES_API_KEY")
        assert config.model == "gpt-4"
        assert config.api_base == "https://api.openai.com/v1"
        assert config.api_key_env == "HERMES_API_KEY"
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.timeout == 120

    def test_load_valid_config(self, tmp_path):
        config_path = tmp_path / "valid.yaml"
        data = {
            "model": "claude-3",
            "api_base": "https://api.anthropic.com/v1",
            "api_key_env": "ANTHROPIC_API_KEY",
            "temperature": 0.5,
            "max_tokens": 2048,
            "timeout": 60,
        }
        with open(config_path, "w") as f:
            yaml.dump(data, f)

        config = load_hermes_config(str(config_path))
        assert config.model == "claude-3"
        assert config.temperature == 0.5

    def test_load_config_missing_file(self):
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_hermes_config("/nonexistent/path.yaml")

    def test_load_config_missing_required_fields(self, tmp_path):
        config_path = tmp_path / "bad.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"model": "gpt-4"}, f)
        with pytest.raises(ValueError, match="api_base"):
            load_hermes_config(str(config_path))


# ---------------------------------------------------------------------------
# HermesAgent tests
# ---------------------------------------------------------------------------

@pytest.fixture
def hermes_config(tmp_path):
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
    return AgentTaskSpec(
        task_id="hermes-test-001",
        task={"type": "simple", "prompt": "test"},
        workspace_path=str(tmp_path / "workspace"),
        prompt="Test prompt",
        timeout_seconds=30,
        output_dir=tmp_path / "output",
        model="gpt-4",
    )


class TestHermesAgentProperties:
    def test_expects_gateway_returns_false(self, hermes_config):
        agent = HermesAgent(config_path=hermes_config)
        assert agent.expects_gateway is False

    def test_transcript_container_path(self, hermes_config):
        agent = HermesAgent(config_path=hermes_config)
        assert agent.transcript_container_path.endswith("transcript.jsonl")


class TestHermesAgentConfigValidation:
    def test_invalid_config_path_raises(self):
        with pytest.raises(FileNotFoundError):
            HermesAgent(config_path="/nonexistent/path.yaml")

    def test_missing_required_field_raises(self, tmp_path):
        config_path = tmp_path / "bad.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"model": "gpt-4"}, f)
        with pytest.raises(ValueError, match="api_base"):
            HermesAgent(config_path=str(config_path))


class TestHermesAgentDockerCommand:
    def test_build_command_structure(self, task_spec, hermes_config):
        agent = HermesAgent(config_path=hermes_config)
        cmd = agent._build_docker_command(task_spec)
        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        assert "--rm" in cmd
        assert "wildclawbench-hermes-agent:v0.5" in cmd

    def test_command_includes_model_and_prompt(self, task_spec, hermes_config):
        agent = HermesAgent(config_path=hermes_config)
        cmd = agent._build_docker_command(task_spec)
        cmd_str = " ".join(cmd)
        assert task_spec.model in cmd_str
        assert task_spec.prompt in cmd_str


class TestHermesAgentErrorHandling:
    def test_missing_api_key(self, hermes_config, task_spec, monkeypatch):
        monkeypatch.delenv("HERMES_API_KEY", raising=False)
        agent = HermesAgent(config_path=hermes_config)
        execution = agent.run_task(task_spec)
        assert execution.error is not None
        assert "HERMES_API_KEY" in execution.error

    def test_container_timeout(self, hermes_config, task_spec, monkeypatch):
        class MockRun:
            def __init__(self, *args, **kwargs):
                self.returncode = 0
                self.stdout = "image_id\n"
                self.stderr = ""
        monkeypatch.setattr(subprocess, "run", MockRun)

        class TimeoutPopen:
            def __init__(self, cmd, **kwargs):
                self._cmd = cmd
            def communicate(self, timeout=None):
                raise subprocess.TimeoutExpired(cmd=self._cmd, timeout=timeout)
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def kill(self): pass
            def wait(self): pass

        monkeypatch.setattr(subprocess, "Popen", TimeoutPopen)
        monkeypatch.setitem(os.environ, "HERMES_API_KEY", "sk-test-key")

        agent = HermesAgent(config_path=hermes_config)
        execution = agent.run_task(task_spec)
        assert execution.error is not None
        assert "timed out" in execution.error.lower()


class TestHermesAgentUsageCollection:
    def test_returns_expected_keys(self, tmp_path, hermes_config):
        agent = HermesAgent(config_path=hermes_config)
        usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)
        assert set(usage.keys()) == {"requests", "total_tokens", "cost"}

    def test_parses_transcript(self, tmp_path, hermes_config):
        transcript_path = tmp_path / "transcript.jsonl"
        events = [
            {"type": "llm.request", "usage": {"total_tokens": 100}},
            {"type": "response.completed", "usage": {"total_tokens": 50}},
        ]
        with open(transcript_path, "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        agent = HermesAgent(config_path=hermes_config)
        usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)
        assert usage["requests"] == 2
        assert usage["total_tokens"] == 150
