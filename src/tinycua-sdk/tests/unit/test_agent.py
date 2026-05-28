"""Tests for agent models."""


class TestAgentPolicy:
    def test_policy_defaults(self):
        from tinycua_sdk.models import AgentPolicy

        policy = AgentPolicy()
        assert policy.max_tool_calls == 10
        assert policy.parallel_tool_calls is True
        assert policy.temperature == 1.0

    def test_policy_custom_values(self):
        from tinycua_sdk.models import AgentPolicy

        policy = AgentPolicy(max_tool_calls=5, temperature=0.5)
        assert policy.max_tool_calls == 5
        assert policy.temperature == 0.5


class TestAgent:
    def test_agent_is_not_abstract(self):
        from tinycua_sdk.models import Agent

        agent = Agent(name="test")
        assert agent.name == "test"

    def test_agent_initialization(self):
        from tinycua_sdk.models import Agent, AgentPolicy

        class TestAgent(Agent):
            def _before_turn(self):
                pass

            def _after_turn(self):
                pass

            def _build_context(self):
                return []

            def _prune_messages(self, messages):
                return messages

        agent = TestAgent(
            name="test",
            instructions="You are a test agent.",
            model="gpt-4o-mini",
        )
        assert agent.name == "test"
        assert agent.instructions == "You are a test agent."
        assert agent.model == "gpt-4o-mini"
        assert isinstance(agent.policy, AgentPolicy)

    def test_agent_with_tools(self):
        from tinycua_sdk.models import Agent
        from tinycua_sdk.tools import tool

        @tool()
        def my_tool() -> None:
            """A tool."""
            pass

        class TestAgent(Agent):
            def _before_turn(self):
                pass

            def _after_turn(self):
                pass

            def _build_context(self):
                return []

            def _prune_messages(self, messages):
                return messages

        agent = TestAgent(name="test", instructions="...", tools=[my_tool])
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "my_tool"

    def test_agent_to_config(self):
        from tinycua_sdk.models import Agent

        class TestAgent(Agent):
            def _before_turn(self):
                pass

            def _after_turn(self):
                pass

            def _build_context(self):
                return []

            def _prune_messages(self, messages):
                return messages

        agent = TestAgent(name="my-agent", instructions="Be helpful.")
        config = agent.to_config()

        assert config["name"] == "my-agent"
        assert config["instructions"] == "Be helpful."
        assert "policy" in config
