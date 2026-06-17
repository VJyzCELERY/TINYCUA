"""Unit tests for BaseAgent ABC and all adapters."""

from __future__ import annotations

import pytest

from agents_benchmark.base_agent import AgentTaskSpec, BaseAgent


class TestBaseAgentABC:
    """Tests that BaseAgent cannot be instantiated directly."""

    def test_cannot_instantiate_base_agent(self):
        """BaseAgent is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore[abstract]


class TestHermesAgentAdapter:
    """Tests for the HermesAgentAdapter."""

    def test_implements_base_agent(self):
        """HermesAgentAdapter must implement BaseAgent interface."""
        from agents_benchmark.agents.hermes import HermesAgentAdapter

        assert issubclass(HermesAgentAdapter, BaseAgent)

    def test_name_property(self):
        """name must return 'hermes'."""
        from agents_benchmark.agents.hermes import HermesAgentAdapter

        agent = HermesAgentAdapter.__new__(HermesAgentAdapter)
        agent._config = type(
            "C", (), {"api_key_env": "K", "api_base": "B", "model": "M"}
        )()
        assert agent.name == "hermes"

    def test_expects_gateway_returns_false(self):
        """expects_gateway must return False."""
        from agents_benchmark.agents.hermes import HermesAgentAdapter

        agent = HermesAgentAdapter.__new__(HermesAgentAdapter)
        agent._config = type(
            "C", (), {"api_key_env": "K", "api_base": "B", "model": "M"}
        )()
        assert agent.expects_gateway is False

    def test_transcript_container_path(self):
        """transcript_container_path must end with transcript.jsonl."""
        from agents_benchmark.agents.hermes import HermesAgentAdapter

        agent = HermesAgentAdapter.__new__(HermesAgentAdapter)
        agent._config = type(
            "C", (), {"api_key_env": "K", "api_base": "B", "model": "M"}
        )()
        assert agent.transcript_container_path.endswith("transcript.jsonl")


class TestClaudeCodeAdapter:
    """Tests for the ClaudeCodeAdapter stub."""

    def test_implements_base_agent(self):
        """ClaudeCodeAdapter must implement BaseAgent interface."""
        from agents_benchmark.agents.claudecode import ClaudeCodeAdapter

        assert issubclass(ClaudeCodeAdapter, BaseAgent)

    def test_name_property(self):
        """name must return 'claudecode'."""
        from agents_benchmark.agents.claudecode import ClaudeCodeAdapter

        agent = ClaudeCodeAdapter()
        assert agent.name == "claudecode"

    def test_run_task_returns_error_execution(self):
        """run_task must return AgentExecution with error for stub."""
        from agents_benchmark.agents.claudecode import ClaudeCodeAdapter

        agent = ClaudeCodeAdapter()
        spec = AgentTaskSpec(
            task_id="test",
            task={},
            workspace_path="/tmp",
            prompt="test",
            timeout_seconds=30,
            output_dir="/tmp/output",
            model="test",
        )
        result = agent.run_task(spec)
        assert result.error is not None
        assert "not yet implemented" in result.error


class TestCodexAdapter:
    """Tests for the CodexAdapter stub."""

    def test_implements_base_agent(self):
        """CodexAdapter must implement BaseAgent interface."""
        from agents_benchmark.agents.codex import CodexAdapter

        assert issubclass(CodexAdapter, BaseAgent)

    def test_name_property(self):
        """name must return 'codex'."""
        from agents_benchmark.agents.codex import CodexAdapter

        agent = CodexAdapter()
        assert agent.name == "codex"

    def test_run_task_returns_error_execution(self):
        """run_task must return AgentExecution with error for stub."""
        from agents_benchmark.agents.codex import CodexAdapter

        agent = CodexAdapter()
        spec = AgentTaskSpec(
            task_id="test",
            task={},
            workspace_path="/tmp",
            prompt="test",
            timeout_seconds=30,
            output_dir="/tmp/output",
            model="test",
        )
        result = agent.run_task(spec)
        assert result.error is not None
        assert "not yet implemented" in result.error


class TestOpenClawAdapter:
    """Tests for the OpenClawAdapter stub."""

    def test_implements_base_agent(self):
        """OpenClawAdapter must implement BaseAgent interface."""
        from agents_benchmark.agents.openclaw import OpenClawAdapter

        assert issubclass(OpenClawAdapter, BaseAgent)

    def test_name_property(self):
        """name must return 'openclaw'."""
        from agents_benchmark.agents.openclaw import OpenClawAdapter

        agent = OpenClawAdapter()
        assert agent.name == "openclaw"

    def test_run_task_returns_error_execution(self):
        """run_task must return AgentExecution with error for stub."""
        from agents_benchmark.agents.openclaw import OpenClawAdapter

        agent = OpenClawAdapter()
        spec = AgentTaskSpec(
            task_id="test",
            task={},
            workspace_path="/tmp",
            prompt="test",
            timeout_seconds=30,
            output_dir="/tmp/output",
            model="test",
        )
        result = agent.run_task(spec)
        assert result.error is not None
        assert "not yet implemented" in result.error
