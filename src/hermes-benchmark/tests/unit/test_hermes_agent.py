"""Unit tests for HermesAgent adapter and HermesConfig."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from hermes_benchmark.base_agent import AgentExecution, AgentTaskSpec
from hermes_benchmark.hermes_agent import HermesAgent
from hermes_benchmark.hermes_config import HermesConfig, load_hermes_config


# ---------------------------------------------------------------------------
# HermesConfig validation tests
# ---------------------------------------------------------------------------

class TestHermesConfig:
    """Tests for HermesConfig dataclass and load_hermes_config."""

    def test_config_dataclass_fields(self):
        """HermesConfig must have the expected fields with correct defaults."""
        config = HermesConfig(model="gpt-4", api_base="https://api.openai.com/v1", api_key_env="HERMES_API_KEY")
        assert config.model == "gpt-4"
        assert config.api_base == "https://api.openai.com/v1"
        assert config.api_key_env == "HERMES_API_KEY"
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.timeout == 120

    def test_load_valid_config(self, tmp_path):
        """load_hermes_config must return HermesConfig for valid YAML."""
        config_path = tmp_path / "valid-config.yaml"
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
        assert config.api_base == "https://api.anthropic.com/v1"
        assert config.api_key_env == "ANTHROPIC_API_KEY"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        assert config.timeout == 60

    def test_load_config_with_minimal_fields(self, tmp_path):
        """load_hermes_config must work with only required fields."""
        config_path = tmp_path / "minimal.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"model": "gpt-4", "api_base": "https://api.openai.com/v1", "api_key_env": "HERMES_API_KEY"}, f)

        config = load_hermes_config(str(config_path))
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.timeout == 120

    def test_load_config_missing_file(self):
        """load_hermes_config must raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_hermes_config("/nonexistent/path.yaml")

    def test_load_config_missing_required_fields(self, tmp_path):
        """load_hermes_config must raise ValueError for missing required fields."""
        config_path = tmp_path / "bad-config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"model": "gpt-4"}, f)

        with pytest.raises(ValueError, match="api_base"):
            load_hermes_config(str(config_path))

    def test_load_config_missing_all_required(self, tmp_path):
        """load_hermes_config must list all missing fields in error."""
        config_path = tmp_path / "empty.yaml"
        with open(config_path, "w") as f:
            yaml.dump({}, f)

        with pytest.raises(ValueError) as excinfo:
            load_hermes_config(str(config_path))
        msg = str(excinfo.value)
        assert "model" in msg
        assert "api_base" in msg
        assert "api_key_env" in msg

    def test_load_config_not_a_mapping(self, tmp_path):
        """load_hermes_config must raise ValueError for non-mapping YAML."""
        config_path = tmp_path / "scalar.yaml"
        with open(config_path, "w") as f:
            f.write("just a string\n")

        with pytest.raises(ValueError, match="YAML mapping"):
            load_hermes_config(str(config_path))


# ---------------------------------------------------------------------------
# HermesAgent properties tests
# ---------------------------------------------------------------------------

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
    return AgentTaskSpec(
        task_id="unit-test-hermes-001",
        task={"type": "simple", "prompt": "test"},
        workspace_path=str(tmp_path / "workspace"),
        prompt="Test prompt",
        timeout_seconds=30,
        output_dir=tmp_path / "output",
        model="gpt-4",
    )


class TestHermesAgentProperties:
    """Tests for HermesAgent static properties."""

    def test_expects_gateway_returns_false(self, hermes_config):
        """expects_gateway must return False."""
        agent = HermesAgent(config_path=hermes_config)
        assert agent.expects_gateway is False

    def test_transcript_container_path_ends_with_jsonl(self, hermes_config):
        """transcript_container_path must end with transcript.jsonl."""
        agent = HermesAgent(config_path=hermes_config)
        path = agent.transcript_container_path
        assert isinstance(path, str)
        assert path.endswith("transcript.jsonl")

    def test_prepare_grading_transcript_returns_container_path(self, hermes_config):
        """prepare_grading_transcript returns transcript_container_path."""
        agent = HermesAgent(config_path=hermes_config)
        result = agent.prepare_grading_transcript("any-id")
        assert result == agent.transcript_container_path


# ---------------------------------------------------------------------------
# HermesAgent config validation tests
# ---------------------------------------------------------------------------

class TestHermesAgentConfigValidation:
    """Tests for HermesAgent config validation."""

    def test_invalid_config_path_raises_error(self):
        """HermesAgent must raise FileNotFoundError for missing config."""
        with pytest.raises(FileNotFoundError):
            HermesAgent(config_path="/nonexistent/path.yaml")

    def test_missing_required_field_raises_error(self, tmp_path):
        """HermesAgent must raise ValueError for missing required fields."""
        config_path = tmp_path / "bad-config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"model": "gpt-4"}, f)
        with pytest.raises(ValueError, match="api_base"):
            HermesAgent(config_path=str(config_path))

    def test_valid_config_creates_agent(self, hermes_config):
        """HermesAgent must be created successfully with valid config."""
        agent = HermesAgent(config_path=hermes_config)
        assert agent._config.model == "gpt-4"
        assert agent._config.api_base == "https://api.openai.com/v1"
        assert agent._config.api_key_env == "HERMES_API_KEY"


# ---------------------------------------------------------------------------
# HermesAgent Docker command construction tests
# ---------------------------------------------------------------------------

class TestHermesAgentDockerCommand:
    """Tests for HermesAgent Docker command construction."""

    def test_build_docker_command_structure(self, task_spec, hermes_config):
        """_build_docker_command must return correct docker run command."""
        agent = HermesAgent(config_path=hermes_config)
        cmd = agent._build_docker_command(task_spec)

        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        assert "--rm" in cmd
        assert "hermes-agent" in cmd
        assert "-v" in cmd
        assert str(task_spec.output_dir) in " ".join(cmd)

    def test_docker_command_includes_env_vars(self, task_spec, hermes_config):
        """_build_docker_command must pass API key env var to container."""
        agent = HermesAgent(config_path=hermes_config)
        cmd = agent._build_docker_command(task_spec)
        cmd_str = " ".join(cmd)

        assert "-e" in cmd or "--env" in cmd
        assert "HERMES_API_KEY" in cmd_str

    def test_docker_command_includes_model_and_prompt(self, task_spec, hermes_config):
        """_build_docker_command must pass model and prompt as args."""
        agent = HermesAgent(config_path=hermes_config)
        cmd = agent._build_docker_command(task_spec)
        cmd_str = " ".join(cmd)

        assert task_spec.model in cmd_str
        assert task_spec.prompt in cmd_str


# ---------------------------------------------------------------------------
# HermesAgent error handling tests
# ---------------------------------------------------------------------------

class TestHermesAgentErrorHandling:
    """Tests for HermesAgent error handling."""

    def test_missing_api_key(self, hermes_config, task_spec, monkeypatch):
        """run_task must return error when API key env var is missing."""
        monkeypatch.delenv("HERMES_API_KEY", raising=False)

        agent = HermesAgent(config_path=hermes_config)
        execution = agent.run_task(task_spec)

        assert execution.error is not None
        assert "HERMES_API_KEY" in execution.error

    def test_docker_build_failure(self, hermes_config, task_spec, monkeypatch):
        """run_task must handle Docker build failure gracefully."""
        def raise_build_error(*args, **kwargs):
            raise subprocess.CalledProcessError(1, ["docker", "build"])

        monkeypatch.setattr(subprocess, "run", raise_build_error)
        monkeypatch.setitem(os.environ, "HERMES_API_KEY", "sk-test-key")

        agent = HermesAgent(config_path=hermes_config)
        execution = agent.run_task(task_spec)

        assert execution.error is not None
        assert "build" in execution.error.lower()

    def test_container_timeout(self, hermes_config, task_spec, monkeypatch):
        """run_task must handle container timeout gracefully."""

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

    def test_successful_run(self, hermes_config, task_spec, monkeypatch):
        """run_task must return successful execution when Docker succeeds."""
        spawned_commands = []

        class MockRun:
            def __init__(self, *args, **kwargs):
                self.returncode = 0
                self.stdout = "image_id_123\n"
                self.stderr = ""

        monkeypatch.setattr(subprocess, "run", MockRun)

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
        monkeypatch.setitem(os.environ, "HERMES_API_KEY", "sk-test-key")

        agent = HermesAgent(config_path=hermes_config)
        execution = agent.run_task(task_spec)

        assert execution.error is None
        assert execution.elapsed_time >= 0
        assert len(spawned_commands) == 1


# ---------------------------------------------------------------------------
# HermesAgent usage collection tests
# ---------------------------------------------------------------------------

class TestHermesConfigConcurrentProfiles:
    """Tests for multiple Hermes config profiles."""

    def test_multiple_configs_independent(self, tmp_path):
        """Multiple HermesConfig instances must be independent."""
        profiles = {
            "openai": {"model": "gpt-4", "api_base": "https://api.openai.com/v1", "api_key_env": "OPENAI_KEY", "temperature": 0.0},
            "anthropic": {"model": "claude-3", "api_base": "https://api.anthropic.com/v1", "api_key_env": "ANTHROPIC_KEY", "temperature": 0.5},
        }

        configs = {}
        for name, data in profiles.items():
            config_path = tmp_path / f"{name}.yaml"
            with open(config_path, "w") as f:
                yaml.dump(data, f)
            configs[name] = load_hermes_config(str(config_path))

        assert configs["openai"].model == "gpt-4"
        assert configs["anthropic"].model == "claude-3"
        assert configs["openai"].temperature == 0.0
        assert configs["anthropic"].temperature == 0.5
        assert configs["openai"].api_key_env == "OPENAI_KEY"
        assert configs["anthropic"].api_key_env == "ANTHROPIC_KEY"


class TestHermesAgentUsageCollection:
    """Tests for HermesAgent collect_usage."""

    def test_returns_expected_keys(self, task_spec, tmp_path, hermes_config):
        """collect_usage must return dict with requests, total_tokens, cost."""
        agent = HermesAgent(config_path=hermes_config)
        usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)

        assert set(usage.keys()) == {"requests", "total_tokens", "cost"}

    def test_empty_no_artifacts(self, task_spec, tmp_path, hermes_config):
        """collect_usage must return zeroed values when no artifacts exist."""
        agent = HermesAgent(config_path=hermes_config)
        usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)

        assert usage["requests"] == 0
        assert usage["total_tokens"] is None
        assert usage["cost"] == 0.0

    def test_parses_transcript(self, task_spec, tmp_path, hermes_config):
        """collect_usage must parse transcript.jsonl for token counts."""
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

    def test_handles_malformed_transcript(self, tmp_path, hermes_config):
        """collect_usage must handle malformed JSON gracefully."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("not valid json\n")

        agent = HermesAgent(config_path=hermes_config)
        usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)

        assert usage["requests"] == 0
        assert usage["total_tokens"] is None
        assert usage["cost"] == 0.0
