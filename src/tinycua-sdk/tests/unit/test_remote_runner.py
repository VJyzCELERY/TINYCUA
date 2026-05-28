"""Unit tests for Remote Runner SDK."""

import pytest


class TestRemoteRunnerBase:
    """Test RemoteRunner base class."""

    def test_remote_runner_is_abstract(self):
        """Test that RemoteRunner cannot be instantiated directly."""
        from tinycua_sdk.runner import RemoteRunner

        with pytest.raises(TypeError):
            RemoteRunner(base_url="http://localhost:8000")

    def test_remote_runner_subclass_must_implement_methods(self):
        """Test that subclasses must implement abstract methods."""
        from tinycua_sdk.runner import RemoteRunner

        # Partial implementation should fail
        with pytest.raises(TypeError):

            class IncompleteRunner(RemoteRunner):
                pass

            IncompleteRunner(base_url="http://localhost:8000")


class TestHTTPRunner:
    """Test HTTPRunner class."""

    def test_http_runner_init(self):
        """Test HTTP runner initialization."""
        from tinycua_sdk.runner import HTTPRunner

        runner = HTTPRunner(base_url="http://localhost:8000")

        assert runner.base_url == "http://localhost:8000"
        assert runner.api_key is None
        assert runner.timeout == 30

    def test_http_runner_with_options(self):
        """Test HTTP runner with custom options."""
        from tinycua_sdk.runner import HTTPRunner

        runner = HTTPRunner(
            base_url="http://localhost:8000",
            api_key="test-key",
            timeout=60,
        )

        assert runner.api_key == "test-key"
        assert runner.timeout == 60

    def test_http_runner_headers_without_key(self):
        """Test headers when no API key."""
        from tinycua_sdk.runner import HTTPRunner

        runner = HTTPRunner(base_url="http://localhost:8000")
        headers = runner._get_headers()

        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers

    def test_http_runner_headers_with_key(self):
        """Test headers with API key."""
        from tinycua_sdk.runner import HTTPRunner

        runner = HTTPRunner(
            base_url="http://localhost:8000",
            api_key="my-key",
        )
        headers = runner._get_headers()

        assert headers["Authorization"] == "Bearer my-key"


class TestRunnerOptions:
    """Test RunnerOptions dataclass."""

    def test_runner_options_required_params(self):
        """Test RunnerOptions with required parameters."""
        from tinycua_sdk.runner import RunnerOptions

        options = RunnerOptions(model="gpt-4")

        assert options.model == "gpt-4"

    def test_runner_options_all_params(self):
        """Test RunnerOptions with all parameters."""
        from tinycua_sdk.runner import RunnerOptions

        options = RunnerOptions(
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000,
            stream=False,
        )

        assert options.model == "gpt-4"
        assert options.temperature == 0.7
        assert options.max_tokens == 1000
        assert options.stream is False

    def test_runner_options_defaults(self):
        """Test RunnerOptions default values."""
        from tinycua_sdk.runner import RunnerOptions

        options = RunnerOptions(model="gpt-4")

        assert options.temperature == 1.0
        assert options.max_tokens is None
        assert options.stream is True


class TestAgentRunnerIntegration:
    """Test Agent with runner integration."""

    def test_agent_runner_property(self):
        """Test that agent has runner property."""
        from tinycua_sdk.models import Agent
        from tinycua_sdk.runner import RemoteRunner

        class TestRunner(RemoteRunner):
            async def execute(self, messages, tools, options):
                yield "test"

            async def health_check(self):
                return True

        runner = TestRunner(base_url="http://localhost:8000")
        agent = Agent(name="test", runner=runner)

        assert agent.runner is runner

    def test_agent_without_runner(self):
        """Test agent without runner defaults to None."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="test")

        assert agent.runner is None


class TestRemoteRunnerExecute:
    """Test remote runner execute method."""

    @pytest.mark.asyncio
    async def test_execute_yields_events(self):
        """Test that execute yields stream events."""
        from tinycua_sdk.runner import RemoteRunner, RunnerOptions

        class TestRunner(RemoteRunner):
            async def execute(self, messages, tools, options):
                yield "event1"
                yield "event2"

            async def health_check(self):
                return True

        runner = TestRunner(base_url="http://localhost:8000")
        options = RunnerOptions(model="test")

        events = []
        async for event in runner.execute([], [], options):
            events.append(event)

        assert len(events) == 2
        assert events[0] == "event1"
        assert events[1] == "event2"


class TestRemoteRunnerHealthCheck:
    """Test remote runner health check."""

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self):
        """Test health check returns boolean."""
        from tinycua_sdk.runner import RemoteRunner

        class HealthyRunner(RemoteRunner):
            async def execute(self, messages, tools, options):
                yield "test"

            async def health_check(self):
                return True

        runner = HealthyRunner(base_url="http://localhost:8000")
        result = await runner.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_can_return_false(self):
        """Test health check can return False."""
        from tinycua_sdk.runner import RemoteRunner

        class UnhealthyRunner(RemoteRunner):
            async def execute(self, messages, tools, options):
                yield "test"

            async def health_check(self):
                return False

        runner = UnhealthyRunner(base_url="http://localhost:8000")
        result = await runner.health_check()

        assert result is False
