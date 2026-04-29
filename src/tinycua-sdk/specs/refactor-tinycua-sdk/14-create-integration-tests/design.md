# Stage 14 — Design: Create Integration Tests

## Overview

Write integration tests based on the working examples from Stage 13. These tests verify that the SDK components work together correctly.

## Philosophy

Integration tests validate **component interactions**, not isolated units. They answer: "Can I create an agent, add tools, and run it?" Tests mock external dependencies (LLM server) to remain fast and deterministic.

## Test Organization

```
tests/integration/
  __init__.py
  test_agent_creation.py      # From config, templates
  test_tool_execution.py      # Tool invoke, schema, composition
  test_skills_integration.py  # Skill.load(), SkillRegistry, composition
  test_loop_execution.py      # Agent loop with mocked LLM
  conftest.py                 # Shared fixtures
```

## Mock Strategy

All integration tests mock the LLM client to avoid requiring a running LLM server:

```python
# conftest.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_llm_client():
    """Mock LLM client for integration tests."""
    with patch("tinycua_sdk.agent.executor.LLMClient") as mock:
        mock.return_value.chat = AsyncMock(return_value="Mocked response")
        yield mock

@pytest.fixture
def mock_llm_with_tool_calls():
    """Mock LLM client that returns tool calls."""
    with patch("tinycua_sdk.agent.executor.LLMClient") as mock:
        # First call: tool call
        # Second call: final response
        mock.return_value.chat = AsyncMock(side_effect=[
            '{"tool_calls": [{"name": "search", "arguments": {"query": "quantum"}]}]}',
            "Quantum computing is...",
        ])
        yield mock
```

## Test Cases

### test_agent_creation.py

```python
import pytest
from tinycua_sdk import Agent, LLMModel, BackendConfig

def test_from_dict_minimal():
    """Create agent from minimal dict config."""
    config = {
        "name": "test",
        "instructions": "Test agent",
        "llm_model": {
            "model_name": "gpt-4",
            "provider": "openai",
        },
    }
    agent = Agent.from_config(config)
    assert agent.name == "test"
    assert agent.instructions == "Test agent"
    assert agent.llm_model.model_name == "gpt-4"

def test_from_dict_with_tools(mock_tool_resolver):
    """Create agent with tools from config."""
    config = {
        "name": "test",
        "llm_model": {},
        "tools": ["search", "summarize"],
    }
    agent = Agent.from_config(config)
    assert len(agent.tools) == 2

def test_from_json_file(tmp_path):
    """Load agent from JSON file."""
    config_file = tmp_path / "agent.json"
    config_file.write_text('{"name": "json_agent", "instructions": "From JSON"}')
    agent = Agent.from_config(config_file)
    assert agent.name == "json_agent"

def test_from_yaml_file(tmp_path):
    """Load agent from YAML file."""
    config_file = tmp_path / "agent.yaml"
    config_file.write_text("name: yaml_agent\ninstructions: From YAML\n")
    agent = Agent.from_config(config_file)
    assert agent.name == "yaml_agent"

def test_config_round_trip():
    """Serialize to dict and restore."""
    original = Agent(
        name="roundtrip",
        llm_model=LLMModel(model_name="gpt-4"),
    )
    config = original.to_config()
    restored = Agent.from_config(config)
    assert restored.name == "roundtrip"
    assert restored.llm_model.model_name == "gpt-4"

def test_coder_template():
    """Load coder template."""
    agent = Agent.from_config("coder")
    assert agent.name == "coder"

def test_researcher_template():
    """Load researcher template."""
    agent = Agent.from_config("researcher")
    assert agent.name == "researcher"

def test_template_with_llm_override():
    """Override LLMModel in template."""
    agent = Agent.from_config("coder")
    agent.llm_model = LLMModel(model_name="custom-model")
    assert agent.llm_model.model_name == "custom-model"

def test_invalid_template():
    """Unknown template raises ValueError."""
    with pytest.raises(ValueError):
        Agent.from_config("nonexistent_template")
```

### test_tool_execution.py

```python
import pytest
from tinycua_sdk import Agent, LLMModel, tool

@tool
def search(query: str) -> str:
    return f"Results for: {query}"

@tool
def summarize(text: str) -> str:
    return f"Summary: {text}"

@pytest.mark.asyncio
async def test_tool_invoked_during_run(mock_llm_with_tool_calls):
    """Tool is called during agent run."""
    agent = Agent(llm_model=LLMModel(), tools=[search])
    response = await agent.run("Search for quantum")
    # Verify tool was invoked
    assert "Quantum" in response or "Mocked" in response

@pytest.mark.asyncio
async def test_multiple_tools(mock_llm_client):
    """Multiple tools available."""
    agent = Agent(llm_model=LLMModel(), tools=[search, summarize])
    assert len(agent.tools) == 2
    response = await agent.run("Do something")
    assert response == "Mocked response"

@pytest.mark.asyncio
async def test_no_tools(mock_llm_client):
    """Agent without tools still runs."""
    agent = Agent(llm_model=LLMModel())
    response = await agent.run("Hello")
    assert response == "Mocked response"

def test_tool_direct_invoke():
    """Direct Tool.invoke()."""
    result = search.invoke(query="test")
    assert result == "Results for: test"

def test_tool_schema():
    """Schema generation for API calls."""
    schema = search.to_config()
    assert schema["name"] == "search"
    assert "query" in schema["parameters"]

@pytest.mark.asyncio
async def test_tool_error_handling(mock_llm_client):
    """Tool exceptions handled gracefully."""
    @tool
    def failing_tool():
        raise RuntimeError("Tool failed")
    
    agent = Agent(llm_model=LLMModel(), tools=[failing_tool])
    response = await agent.run("Use failing tool")
    # Should not crash; may return error message
    assert isinstance(response, str)

@pytest.mark.asyncio
async def test_add_tools_then_run(mock_llm_client):
    """Add tools after construction."""
    agent = Agent(llm_model=LLMModel())
    agent.add_tools(search)
    response = await agent.run("Search")
    assert response == "Mocked response"

@pytest.mark.asyncio
async def test_add_multiple_tools(mock_llm_client):
    """Add list of tools."""
    agent = Agent(llm_model=LLMModel())
    agent.add_tools([search, summarize])
    assert len(agent.tools) == 2
    response = await agent.run("Do something")
    assert response == "Mocked response"
```

### test_skills_integration.py

```python
import pytest
from tinycua_sdk import Agent, LLMModel, Skill, SkillRegistry

def test_add_single_skill():
    """Add one skill."""
    agent = Agent(llm_model=LLMModel())
    agent.add_skills(Skill(name="coder"))
    assert len(agent.skills) == 1

def test_add_multiple_skills():
    """Add list of skills."""
    agent = Agent(llm_model=LLMModel())
    agent.add_skills([Skill(name="a"), Skill(name="b")])
    assert len(agent.skills) == 2

def test_skill_at_construction():
    """Skills at Agent construction."""
    agent = Agent(llm_model=LLMModel(), skills=[Skill(name="coder")])
    assert len(agent.skills) == 1

@pytest.mark.asyncio
async def test_agent_with_skill_run(mock_llm_client):
    """Run with skill."""
    agent = Agent(
        llm_model=LLMModel(),
        skills=[Skill(name="coder", instructions="Write code")],
    )
    response = await agent.run("Write a function")
    assert response == "Mocked response"

def test_skill_load():
    """Skill.load(markdown_text)."""
    text = """
---
name: researcher
category: research
tools:
  - search
---
# Researcher
## Instructions
Research thoroughly.
"""
    skill = Skill.load(text)
    assert skill.name == "researcher"
    assert skill.category == "research"

def test_skill_registry_load():
    """Load skills into registry."""
    registry = SkillRegistry()
    registry.register(Skill(name="a"))
    registry.register(Skill(name="b"))
    assert len(registry.list_skills()) == 2

def test_registry_not_singleton():
    """Independent registries."""
    r1 = SkillRegistry()
    r2 = SkillRegistry()
    r1.register(Skill(name="a"))
    assert r2.get("a") is None

def test_filter_skills_by_category():
    """Filter in registry."""
    registry = SkillRegistry()
    registry.register(Skill(name="a", category="dev"))
    registry.register(Skill(name="b", category="research"))
    dev_skills = registry.list_skills(category="dev")
    assert len(dev_skills) == 1
    assert dev_skills[0].name == "a"

def test_skill_config_round_trip():
    """Serialize and deserialize skill."""
    original = Skill(name="test", instructions="Do something")
    d = original.to_dict()
    restored = Skill.from_dict(d)
    assert restored.name == "test"
    assert restored.instructions == "Do something"
```

### test_loop_execution.py

```python
import pytest
from tinycua_sdk import Agent, LLMModel, BaseLoop, tool

@pytest.mark.asyncio
async def test_run_basic(mock_llm_client):
    """Basic run with mocked LLM."""
    agent = Agent(llm_model=LLMModel())
    response = await agent.run("Hello")
    assert response == "Mocked response"

@pytest.mark.asyncio
async def test_run_with_messages(mock_llm_client):
    """Pass message history."""
    agent = Agent(llm_model=LLMModel())
    messages = [{"role": "user", "content": "Previous"}]
    response = await agent.run("Hello", messages=messages)
    assert response == "Mocked response"

@pytest.mark.asyncio
async def test_run_stream(mock_llm_client):
    """Streaming response."""
    agent = Agent(llm_model=LLMModel())
    chunks = []
    async for chunk in await agent.run("Hello", stream=True):
        chunks.append(chunk)
    assert len(chunks) > 0

@pytest.mark.asyncio
async def test_run_with_tools(mock_llm_with_tool_calls):
    """Tool calling in loop."""
    @tool
    def search(query: str) -> str:
        return f"Results: {query}"
    
    agent = Agent(llm_model=LLMModel(), tools=[search])
    response = await agent.run("Search for quantum")
    assert isinstance(response, str)

@pytest.mark.asyncio
async def test_run_stateless(mock_llm_client):
    """Multiple runs are independent."""
    agent = Agent(llm_model=LLMModel())
    r1 = await agent.run("Query 1")
    r2 = await agent.run("Query 2")
    assert r1 == "Mocked response"
    assert r2 == "Mocked response"

@pytest.mark.asyncio
async def test_custom_loop(mock_llm_client):
    """Agent with custom BaseLoop subclass."""
    class CustomLoop(BaseLoop):
        async def run(self, agent, messages, tools):
            # Custom logic
            return "Custom result"
    
    agent = Agent(llm_model=LLMModel(), loop=CustomLoop())
    response = await agent.run("Hello")
    assert response == "Custom result"

@pytest.mark.asyncio
async def test_base_loop_default(mock_llm_client):
    """Default BaseLoop() used when loop=None."""
    agent = Agent(llm_model=LLMModel())
    response = await agent.run("Hello")
    assert response == "Mocked response"
```

## Running Integration Tests

```bash
# All integration tests
pytest tests/integration/ -v

# Specific test file
pytest tests/integration/test_loop_execution.py -v

# With coverage
pytest tests/integration/ --cov=tinycua_sdk --cov-report=term-missing
```

## Acceptance Criteria

- [ ] All integration tests pass.
- [ ] Tests cover the examples from Stage 13.
- [ ] Tests do not require external services (mocked LLM).
- [ ] Tests verify statelessness (no side effects between runs).
- [ ] Tests use fixtures from `conftest.py`.
- [ ] Test suite runs without import errors.

## Dependencies

- **Requires**: Stage 13 (examples must exist and be working).
- **Blocks**: None.
