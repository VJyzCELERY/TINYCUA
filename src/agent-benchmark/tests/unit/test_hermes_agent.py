"""Unit tests for HermesAgent adapter and ProviderConfig."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from agent_benchmark.base_agent import AgentExecution, AgentTaskSpec
from agent_benchmark.agents.hermes_agent import HermesAgent
from agent_benchmark.providers.base import ProviderConfig
from agent_benchmark.providers.registry import get_provider


# ---------------------------------------------------------------------------
# ProviderConfig validation tests
# ---------------------------------------------------------------------------

class TestProviderConfig:
    def test_config_dataclass_fields(self):
        config = ProviderConfig(
            name="lm-studio",
            model="gpt-4",
            api_base="https://api.openai.com/v1",
            api_key_env="HERMES_API_KEY",
        )
        assert config.name == "lm-studio"
        assert config.model == "gpt-4"
        assert config.api_base == "https://api.openai.com/v1"
        assert config.api_key_env == "HERMES_API_KEY"
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.timeout == 120

    def test_load_valid_config(self, tmp_path):
        config_path = tmp_path / "valid.yaml"
        data = {
            "provider": {
                "name": "ollama",
                "model": "llama3",
                "api_base": "http://localhost:11434/v1",
                "api_key_env": "OLLAMA_API_KEY",
                "temperature": 0.5,
                "max_tokens": 2048,
                "timeout": 60,
            }
        }
        with open(config_path, "w") as f:
            yaml.dump(data, f)

        config = ProviderConfig.from_yaml(str(config_path))
        assert config.name == "ollama"
        assert config.model == "llama3"
        assert config.temperature == 0.5

    def test_load_config_missing_file(self):
        with pytest.raises(FileNotFoundError, match="Provider config not found"):
            ProviderConfig.from_yaml("/nonexistent/path.yaml")

    def test_load_config_missing_required_fields(self, tmp_path):
        config_path = tmp_path / "bad.yaml"
        data = {"provider": {"model": "gpt-4"}}
        with open(config_path, "w") as f:
            yaml.dump(data, f)
        with pytest.raises(ValueError, match="Missing required fields"):
            ProviderConfig.from_yaml(str(config_path))

    def test_load_config_from_env(self, monkeypatch):
        monkeypatch.setenv("PROVIDER_NAME", "openrouter")
        monkeypatch.setenv("PROVIDER_API_BASE", "https://openrouter.ai/api/v1")
        monkeypatch.setenv("PROVIDER_MODEL", "openai/gpt-4")
        monkeypatch.setenv("PROVIDER_API_KEY_ENV", "OPENROUTER_API_KEY")

        config = ProviderConfig.from_env()
        assert config.name == "openrouter"
        assert config.api_base == "https://openrouter.ai/api/v1"
        assert config.model == "openai/gpt-4"

    def test_to_env_dict(self):
        config = ProviderConfig(
            name="lm-studio",
            model="qwen3.5-9b",
            api_base="http://localhost:1234/v1",
            api_key_env="LM_STUDIO_API_KEY",
        )
        env_dict = config.to_env_dict()
        assert env_dict["LLM_API_BASE"] == "http://localhost:1234/v1"
        assert env_dict["LLM_MODEL"] == "qwen3.5-9b"
        assert "LLM_API_KEY" in env_dict


# ---------------------------------------------------------------------------
# Provider registry tests
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    def test_get_provider_lm_studio(self):
        config = ProviderConfig(
            name="lm-studio",
            model="test",
            api_base="http://localhost:1234/v1",
            api_key_env="LM_STUDIO_API_KEY",
        )
        provider = get_provider("lm-studio", config)
        assert provider.config.name == "lm-studio"

    def test_get_provider_ollama(self):
        config = ProviderConfig(
            name="ollama",
            model="llama3",
            api_base="http://localhost:11434/v1",
            api_key_env="OLLAMA_API_KEY",
        )
        provider = get_provider("ollama", config)
        assert provider.config.name == "ollama"

    def test_get_provider_unknown_raises(self):
        config = ProviderConfig(
            name="unknown",
            model="test",
            api_base="http://localhost:8000/v1",
            api_key_env="TEST_API_KEY",
        )
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("unknown", config)


# ---------------------------------------------------------------------------
# HermesAgent tests
# ---------------------------------------------------------------------------

@pytest.fixture
def provider_config():
    return ProviderConfig(
        name="lm-studio",
        model="gpt-4",
        api_base="http://host.docker.internal:1234/v1",
        api_key_env="HERMES_API_KEY",
        temperature=0.0,
        max_tokens=4096,
        timeout=120,
    )


@pytest.fixture
def provider(provider_config):
    return get_provider(provider_config.name, provider_config)


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
    def test_expects_gateway_returns_false(self, provider):
        agent = HermesAgent(provider=provider)
        assert agent.expects_gateway is False

    def test_transcript_container_path(self, provider):
        agent = HermesAgent(provider=provider)
        assert agent.transcript_container_path.endswith("transcript.jsonl")


class TestHermesAgentDockerCommand:
    def test_build_command_structure(self, task_spec, provider):
        agent = HermesAgent(provider=provider)
        cmd = agent._build_docker_command(task_spec)
        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        assert "--rm" in cmd
        assert "wildclawbench-hermes-agent:latest" in cmd

    def test_command_includes_model_and_prompt(self, task_spec, provider):
        agent = HermesAgent(provider=provider)
        cmd = agent._build_docker_command(task_spec)
        cmd_str = " ".join(cmd)
        assert task_spec.model in cmd_str
        assert task_spec.prompt in cmd_str

    def test_command_uses_provider_env_vars(self, task_spec, provider):
        agent = HermesAgent(provider=provider)
        cmd = agent._build_docker_command(task_spec)
        cmd_str = " ".join(cmd)
        assert "LLM_API_BASE=" in cmd_str
        assert "LLM_MODEL=" in cmd_str


class TestHermesAgentErrorHandling:
    def test_missing_api_key(self, provider, task_spec, monkeypatch):
        monkeypatch.delenv("HERMES_API_KEY", raising=False)
        agent = HermesAgent(provider=provider)
        execution = agent.run_task(task_spec)
        assert execution.error is not None
        assert "HERMES_API_KEY" in execution.error

    def test_container_timeout(self, provider, task_spec, monkeypatch):
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

        agent = HermesAgent(provider=provider)
        execution = agent.run_task(task_spec)
        assert execution.error is not None
        assert "timed out" in execution.error.lower()


class TestHermesAgentUsageCollection:
    def test_returns_expected_keys(self, tmp_path, provider):
        agent = HermesAgent(provider=provider)
        usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)
        assert set(usage.keys()) == {"requests", "total_tokens", "cost"}

    def test_parses_transcript(self, tmp_path, provider):
        transcript_path = tmp_path / "transcript.jsonl"
        events = [
            {"type": "llm.request", "usage": {"total_tokens": 100}},
            {"type": "response.completed", "usage": {"total_tokens": 50}},
        ]
        with open(transcript_path, "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        agent = HermesAgent(provider=provider)
        usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)
        assert usage["requests"] == 2
        assert usage["total_tokens"] == 150
