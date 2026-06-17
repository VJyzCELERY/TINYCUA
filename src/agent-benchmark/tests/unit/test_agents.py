"""Unit tests for DockerAgent base class and agent registry."""

import os
import subprocess
from pathlib import Path

import pytest

from agent_benchmark.base_agent import AgentExecution, AgentTaskSpec
from agent_benchmark.agents.docker_agent import DockerAgent
from agent_benchmark.agents import get_agent, list_agents


# ---------------------------------------------------------------------------
# Concrete test agent
# ---------------------------------------------------------------------------

class StubAgent(DockerAgent):
    """Minimal concrete agent for testing DockerAgent."""
    image_name = "test-image:v1"
    api_key_env = "STUB_API_KEY"


# ---------------------------------------------------------------------------
# DockerAgent tests
# ---------------------------------------------------------------------------

@pytest.fixture
def task_spec(tmp_path):
    return AgentTaskSpec(
        task_id="test-001",
        task={"type": "simple"},
        workspace_path=str(tmp_path / "workspace"),
        prompt="Test prompt",
        timeout_seconds=30,
        output_dir=tmp_path / "output",
        model="test-model",
    )


class TestDockerAgentProperties:
    def test_expects_gateway_false(self):
        agent = StubAgent()
        assert agent.expects_gateway is False

    def test_transcript_container_path(self):
        agent = StubAgent()
        assert agent.transcript_container_path.endswith("transcript.jsonl")


class TestDockerAgentMissingApiKey:
    def test_returns_error_when_key_missing(self, task_spec, monkeypatch):
        monkeypatch.delenv("STUB_API_KEY", raising=False)
        agent = StubAgent()
        execution = agent.run_task(task_spec)
        assert execution.error is not None
        assert "STUB_API_KEY" in execution.error


class TestDockerAgentCollectUsage:
    def test_returns_expected_keys(self, tmp_path):
        agent = StubAgent()
        usage = agent.collect_usage("test-001", tmp_path, 1.0)
        assert set(usage.keys()) == {"requests", "total_tokens", "cost"}

    def test_empty_when_no_artifacts(self, tmp_path):
        agent = StubAgent()
        usage = agent.collect_usage("test-001", tmp_path, 1.0)
        assert usage["requests"] == 0
        assert usage["total_tokens"] is None
        assert usage["cost"] == 0.0

    def test_parses_transcript(self, tmp_path):
        import json
        transcript = tmp_path / "transcript.jsonl"
        events = [
            {"type": "llm.request", "usage": {"total_tokens": 100}},
            {"type": "response.done", "usage": {"total_tokens": 50}},
        ]
        with open(transcript, "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        agent = StubAgent()
        usage = agent.collect_usage("test-001", tmp_path, 1.0)
        assert usage["requests"] == 2
        assert usage["total_tokens"] == 150


# ---------------------------------------------------------------------------
# Agent registry tests
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    def test_list_agents(self):
        agents = list_agents()
        assert "openclaw" in agents
        assert "opencode" in agents
        assert "hermesagent" in agents

    def test_get_agent_openclaw(self):
        agent = get_agent("openclaw")
        assert agent.image_name == "wildclawbench-ubuntu:v1.3"
        assert agent.api_key_env == "OPENROUTER_API_KEY"

    def test_get_agent_opencode(self, tmp_path):
        import yaml
        config = {
            "model": "qwen3.5-9b",
            "api_base": "http://localhost:8000/v1",
            "api_key_env": "OPENCODE_API_KEY",
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        agent = get_agent("opencode", config_path=str(config_path))
        assert agent.image_name == "wildclawbench-ubuntu:v1.3"

    def test_get_agent_hermesagent(self, tmp_path):
        import yaml
        config = {
            "model": "gpt-4",
            "api_base": "https://api.openai.com/v1",
            "api_key_env": "HERMES_API_KEY",
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        agent = get_agent("hermesagent", config_path=str(config_path))
        assert agent.image_name == "wildclawbench-hermes-agent:v0.5"

    def test_get_agent_invalid_raises(self):
        with pytest.raises(ValueError, match="Unknown agent"):
            get_agent("nonexistent")
