"""Tests for Agent construction, composition, config, and run behavior."""

import pytest


class TestAgentConstruction:
    """Tests for Agent construction."""

    def test_agent_minimal_construction(self):
        """Agent can be constructed with defaults."""
        from tinycua_sdk import Agent, LanguageModel

        agent = Agent()
        assert agent.name == "assistant"
        assert agent.instructions == ""
        assert isinstance(agent.llm_model, LanguageModel)

    def test_agent_full_construction(self, default_llm, default_loop):
        """Agent can be constructed with all valid parameters."""
        from tinycua_sdk import Agent, AgentPolicy

        agent = Agent(
            name="test",
            instructions="Test instructions",
            llm_model=default_llm,
            policy=AgentPolicy(),
            metadata={"team": "platform"},
            tool_permissions={"search": "ask"},
            loop=default_loop,
        )
        assert agent.name == "test"
        assert agent.instructions == "Test instructions"
        assert agent.loop == default_loop
        assert agent.metadata == {"team": "platform"}
        assert agent.tool_permissions == {"search": "ask"}

    def test_agent_rejects_system_prompt(self):
        """Agent rejects obsolete system_prompt parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="system_prompt"):
            Agent(system_prompt="test")

    def test_agent_rejects_model(self):
        """Agent rejects obsolete model parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="model"):
            Agent(model="gpt-4")

    def test_agent_rejects_provider(self):
        """Agent rejects obsolete provider parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="provider"):
            Agent(provider="openai")

    def test_agent_rejects_base_url(self):
        """Agent rejects obsolete base_url parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="base_url"):
            Agent(base_url="http://localhost")

    def test_agent_rejects_api_key(self):
        """Agent rejects obsolete api_key parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="api_key"):
            Agent(api_key="secret")

    def test_agent_rejects_session_id(self):
        """Agent rejects obsolete session_id parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="session_id"):
            Agent(session_id="abc123")

    def test_agent_rejects_short_term_memory(self):
        """Agent rejects obsolete short_term_memory parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="short_term_memory"):
            Agent(short_term_memory=None)

    def test_agent_rejects_long_term_memory(self):
        """Agent rejects obsolete long_term_memory parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="long_term_memory"):
            Agent(long_term_memory=None)

    def test_agent_rejects_planning_prompt(self):
        """Agent rejects obsolete planning_prompt parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="planning_prompt"):
            Agent(planning_prompt="plan")

    def test_agent_rejects_mode(self):
        """Agent rejects obsolete mode parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="mode"):
            Agent(mode="local")

    def test_agent_rejects_backend_url(self):
        """Agent rejects obsolete backend_url parameter."""
        from tinycua_sdk import Agent

        with pytest.raises(TypeError, match="backend_url"):
            Agent(backend_url="http://localhost:8000")


class TestAgentToolSkillComposition:
    """Tests for Agent tool and skill composition."""

    def test_add_tools_single(self, default_llm):
        """add_tools accepts a single Tool."""
        from tinycua_sdk import Agent, tool

        @tool
        def search(q: str) -> str:
            return f"Results for {q}"

        agent = Agent(llm_model=default_llm)
        agent.add_tools(search)
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "search"

    def test_add_tools_list(self, default_llm):
        """add_tools accepts a list of Tools."""
        from tinycua_sdk import Agent, tool

        @tool
        def search(q: str) -> str:
            return f"Results for {q}"

        @tool
        def summarize(t: str) -> str:
            return f"Summary of {t}"

        agent = Agent(llm_model=default_llm)
        agent.add_tools([search, summarize])
        assert len(agent.tools) == 2

    def test_add_skills_single(self, default_llm):
        """add_skills accepts a single Skill."""
        from tinycua_sdk import Agent, Skill

        skill = Skill(name="coder", description="", instructions="Write code")
        agent = Agent(llm_model=default_llm)
        agent.add_skills(skill)
        assert len(agent.skills) == 1

    def test_add_skills_list(self, default_llm):
        """add_skills accepts a list of Skills."""
        from tinycua_sdk import Agent, Skill

        s1 = Skill(name="coder", description="", instructions="")
        s2 = Skill(name="researcher", description="", instructions="")
        agent = Agent(llm_model=default_llm)
        agent.add_skills([s1, s2])
        assert len(agent.skills) == 2


class TestAgentConfigRoundTrip:
    """Tests for Agent config serialization."""

    def test_agent_to_config(self, default_llm):
        """Agent.to_config() returns a serialization-friendly dict."""
        from tinycua_sdk import Agent

        agent = Agent(
            llm_model=default_llm,
            name="test",
            metadata={"team": "platform"},
            tool_permissions={"search": "allow"},
        )
        config = agent.to_config()
        assert config["name"] == "test"
        assert "llm_model" in config
        assert config["metadata"]["team"] == "platform"
        assert config["tool_permissions"]["search"] == "allow"

    def test_agent_from_config_dict(self, default_llm):
        """Agent.from_config() works with a dict."""
        from tinycua_sdk import Agent

        config = {
            "name": "test",
            "instructions": "Test",
            "llm_model": default_llm.to_dict(),
            "metadata": {"team": "platform"},
            "tool_permissions": {"search": "deny"},
        }
        agent = Agent.from_config(config)
        assert agent.name == "test"
        assert agent.instructions == "Test"
        assert agent.metadata == {"team": "platform"}
        assert agent.tool_permissions == {"search": "deny"}

    def test_agent_config_round_trip(self, default_llm):
        """Agent round-trips through to_config and from_config."""
        from tinycua_sdk import Agent, Skill

        skill = Skill(name="coder", description="", instructions="")
        agent = Agent(
            llm_model=default_llm,
            name="roundtrip",
            instructions="Test",
            skills=[skill],
        )
        config = agent.to_config()
        restored = Agent.from_config(config)
        assert restored.name == "roundtrip"
        assert restored.instructions == "Test"


class TestAgentRun:
    """Tests for Agent.run() stub behavior."""

    @pytest.mark.asyncio
    async def test_agent_run_not_implemented(self, default_llm):
        """Agent.run() raises NotImplementedError in Stage 2."""
        from tinycua_sdk import Agent

        agent = Agent(llm_model=default_llm)
        with pytest.raises(NotImplementedError):
            await agent.run("Hello")
