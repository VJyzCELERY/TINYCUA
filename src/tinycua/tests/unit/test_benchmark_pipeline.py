"""Unit tests for benchmark pipeline integration (agent factory, CLI args)."""

from pathlib import Path

import pytest
import yaml

from tinycua.scripts.benchmark_config import BenchmarkConfig, parse_args
from tinycua.scripts.run_benchmark import _create_agent
from tinycua.wildclawbench.agent import TinyCUAAgent
from hermes_benchmark.hermes_agent import HermesAgent


class TestBenchmarkConfig:
    """Tests for BenchmarkConfig with new agent_backend and hermes_config_path fields."""

    def test_default_agent_backend_is_tinycua(self):
        """Default agent_backend must be 'tinycua'."""
        config = BenchmarkConfig()
        assert config.agent_backend == "tinycua"

    def test_hermes_config_path_defaults_to_none(self):
        """hermes_config_path must default to None."""
        config = BenchmarkConfig()
        assert config.hermes_config_path is None

    def test_from_args_sets_agent_backend(self):
        """from_args must propagate --agent-backend."""
        args = parse_args(["--agent-backend", "hermesagent"])
        config = BenchmarkConfig.from_args(args)
        assert config.agent_backend == "hermesagent"

    def test_from_args_sets_hermes_config(self, tmp_path):
        """from_args must propagate --hermes-config path."""
        config_path = tmp_path / "hermes.yaml"
        config_path.write_text("")
        args = parse_args(["--hermes-config", str(config_path)])
        config = BenchmarkConfig.from_args(args)
        assert config.hermes_config_path == str(config_path)

    def test_from_args_defaults_when_args_missing(self):
        """from_args must use defaults when args don't include new fields."""
        args = parse_args(["--output-dir", "/tmp"])
        config = BenchmarkConfig.from_args(args)
        assert config.agent_backend == "tinycua"
        assert config.hermes_config_path is None


class TestAgentFactory:
    """Tests for _create_agent factory function."""

    def test_create_tinycua_agent(self):
        """_create_agent must return TinyCUAAgent for default backend."""
        config = BenchmarkConfig()
        agent = _create_agent(config)
        assert isinstance(agent, TinyCUAAgent)

    def test_create_hermes_agent(self, tmp_path):
        """_create_agent must return HermesAgent for hermesagent backend."""
        config_path = tmp_path / "hermes-config.yaml"
        config_data = {
            "model": "gpt-4",
            "api_base": "https://api.openai.com/v1",
            "api_key_env": "HERMES_API_KEY",
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        config = BenchmarkConfig(agent_backend="hermesagent", hermes_config_path=str(config_path))
        agent = _create_agent(config)
        assert isinstance(agent, HermesAgent)

    def test_create_hermes_agent_missing_config_raises_value_error(self):
        """_create_agent must raise ValueError when hermes_config_path is missing."""
        config = BenchmarkConfig(agent_backend="hermesagent", hermes_config_path=None)
        with pytest.raises(ValueError, match="--hermes-config"):
            _create_agent(config)

    def test_tinycua_agent_has_expected_config(self):
        """TinyCUAAgent created by factory must inherit benchmark config."""
        config = BenchmarkConfig(
            model_name="custom-model",
            base_url="http://test.local:8080/v1",
            api_key="test-key-123",
        )
        agent = _create_agent(config)
        assert agent._tinycua_bin == "tinycua"


class TestCLIParsing:
    """Tests for CLI argument parsing of new arguments."""

    def test_parse_agent_backend_tinycua(self):
        """--agent-backend tinycua must parse correctly."""
        args = parse_args(["--agent-backend", "tinycua"])
        assert args.agent_backend == "tinycua"

    def test_parse_agent_backend_hermesagent(self):
        """--agent-backend hermesagent must parse correctly."""
        args = parse_args(["--agent-backend", "hermesagent"])
        assert args.agent_backend == "hermesagent"

    def test_parse_hermes_config_path(self, tmp_path):
        """--hermes-config must parse path correctly."""
        config_path = tmp_path / "test-config.yaml"
        config_path.write_text("")
        args = parse_args(["--hermes-config", str(config_path)])
        assert args.hermes_config == str(config_path)

    def test_parse_combined_args(self, tmp_path):
        """Multiple new args must parse together."""
        config_path = tmp_path / "my-config.yaml"
        config_path.write_text("")
        args = parse_args([
            "--agent-backend", "hermesagent",
            "--hermes-config", str(config_path),
            "--output-dir", "/tmp/results",
        ])
        assert args.agent_backend == "hermesagent"
        assert args.hermes_config == str(config_path)
        assert args.output_dir == "/tmp/results"
