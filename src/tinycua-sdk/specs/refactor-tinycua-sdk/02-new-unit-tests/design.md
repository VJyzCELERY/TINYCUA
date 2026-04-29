# Stage 02 — Design: New Unit Tests

## Overview

Write a comprehensive unit test suite that defines the success criteria for the refactored SDK. These tests will fail initially (since the implementation doesn't exist yet) and will guide the implementation in Stages 03–12. This is Test-Driven Development (TDD) — tests first, implementation second.

## Philosophy

Unit tests validate the **public API contract** of the SDK, not internal implementation details. They answer the question: "Can a consumer use this SDK to build an agent?" Tests should be fast, isolated, and not require external services.

## Test Organization

```
tests/
  unit/
    __init__.py
    test_agent.py          # Agent construction, config, run
    test_tool.py           # @tool decorator, Tool dataclass
    test_skills.py         # Skill dataclass, SkillRegistry
    test_config.py         # Config serialization/deserialization
    test_loop.py           # BaseLoop behavior
    test_templates.py      # Agent templates
    test_llm_model.py      # LLMModel value object
    test_backend_config.py # BackendConfig value object
  conftest.py              # Shared fixtures
```

## Test Fixtures

### conftest.py

```python
import pytest
from tinycua_sdk import LLMModel, BackendConfig, BackendKind, BaseLoop

@pytest.fixture
def default_llm():
    """Default LLMModel for tests."""
    return LLMModel(
        provider="openai-compatible",
        model_name="gpt-4o-mini",
        base_url="http://localhost:1234/v1",
    )

@pytest.fixture
def default_backend():
    """Default BackendConfig for tests."""
    return BackendConfig(kind=BackendKind.LOCAL)

@pytest.fixture
def default_loop():
    """Default BaseLoop for tests."""
    return BaseLoop(max_iterations=3)

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing Agent.run()."""
    return "Mocked LLM response"
```

## Test Cases

### test_agent.py

#### Construction Tests
```python
def test_agent_minimal_construction(default_llm):
    """Agent can be constructed with just an LLMModel."""
    from tinycua_sdk import Agent
    agent = Agent(llm_model=default_llm)
    assert agent.name == "assistant"
    assert agent.instructions == ""
    assert agent.llm_model == default_llm

def test_agent_full_construction(default_llm, default_backend, default_loop):
    """Agent can be constructed with all parameters."""
    from tinycua_sdk import Agent, AgentPolicy
    agent = Agent(
        name="test",
        instructions="Test instructions",
        llm_model=default_llm,
        policy=AgentPolicy(),
        backend=default_backend,
        max_depth=5,
        loop=default_loop,
    )
    assert agent.name == "test"
    assert agent.instructions == "Test instructions"
    assert agent.max_depth == 5
    assert agent.loop == default_loop

def test_agent_rejects_obsolete_parameters(default_llm):
    """Agent rejects old parameters like system_prompt, model, provider."""
    from tinycua_sdk import Agent
    with pytest.raises(TypeError):
        Agent(system_prompt="test")
    with pytest.raises(TypeError):
        Agent(model="gpt-4")
    with pytest.raises(TypeError):
        Agent(provider="openai")
```

#### Tool/Skill Composition Tests
```python
def test_add_tools_single(default_llm):
    """add_tools accepts a single Tool."""
    from tinycua_sdk import Agent, tool
    
    @tool
    def search(q: str) -> str:
        return f"Results for {q}"
    
    agent = Agent(llm_model=default_llm)
    agent.add_tools(search)
    assert len(agent.tools) == 1
    assert agent.tools[0].name == "search"

def test_add_tools_list(default_llm):
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

def test_add_skills_single(default_llm):
    """add_skills accepts a single Skill."""
    from tinycua_sdk import Agent, Skill
    skill = Skill(name="coder", instructions="Write code")
    agent = Agent(llm_model=default_llm)
    agent.add_skills(skill)
    assert len(agent.skills) == 1

def test_add_skills_list(default_llm):
    """add_skills accepts a list of Skills."""
    from tinycua_sdk import Agent, Skill
    s1 = Skill(name="coder")
    s2 = Skill(name="researcher")
    agent = Agent(llm_model=default_llm)
    agent.add_skills([s1, s2])
    assert len(agent.skills) == 2
```

#### Config Round-Trip Tests
```python
def test_agent_to_config(default_llm):
    """Agent.to_config() returns a serialization-friendly dict."""
    from tinycua_sdk import Agent
    agent = Agent(llm_model=default_llm, name="test")
    config = agent.to_config()
    assert config["name"] == "test"
    assert "llm_model" in config

def test_agent_from_config_dict(default_llm):
    """Agent.from_config() works with a dict."""
    from tinycua_sdk import Agent
    config = {
        "name": "test",
        "instructions": "Test",
        "llm_model": default_llm.to_dict(),
    }
    agent = Agent.from_config(config)
    assert agent.name == "test"
    assert agent.instructions == "Test"
```

#### Run Tests (Mocked)
```python
@pytest.mark.asyncio
async def test_agent_run_basic(default_llm, mock_llm_response):
    """Agent.run() returns a string."""
    from tinycua_sdk import Agent
    agent = Agent(llm_model=default_llm)
    # Mock the LLM call
    with patch.object(agent, '_call_llm', return_value=mock_llm_response):
        response = await agent.run("Hello")
    assert response == mock_llm_response

@pytest.mark.asyncio
async def test_agent_run_with_messages(default_llm):
    """Agent.run() accepts message history."""
    from tinycua_sdk import Agent
    agent = Agent(llm_model=default_llm)
    messages = [{"role": "user", "content": "Previous message"}]
    with patch.object(agent, '_call_llm', return_value="Response"):
        response = await agent.run("Hello", messages=messages)
    assert response == "Response"

@pytest.mark.asyncio
async def test_agent_run_stateless(default_llm):
    """Multiple runs are independent (no internal state)."""
    from tinycua_sdk import Agent
    agent = Agent(llm_model=default_llm)
    with patch.object(agent, '_call_llm', side_effect=["A", "B"]):
        r1 = await agent.run("Query 1")
        r2 = await agent.run("Query 2")
    assert r1 == "A"
    assert r2 == "B"
```

### test_tool.py

```python
def test_tool_decorator():
    """@tool converts a function into a Tool instance."""
    from tinycua_sdk import tool
    
    @tool
    def search(query: str) -> str:
        """Search for information."""
        return f"Results for {query}"
    
    assert search.name == "search"
    assert "Search for information" in search.description
    assert "query" in search.parameters

def test_tool_invoke():
    """Tool.invoke() calls the underlying function."""
    from tinycua_sdk import tool
    
    @tool
    def add(a: int, b: int) -> int:
        return a + b
    
    result = add.invoke(a=1, b=2)
    assert result == 3

def test_tool_to_config():
    """Tool.to_config() returns a serialization-friendly dict."""
    from tinycua_sdk import tool
    
    @tool
    def search(query: str) -> str:
        return f"Results for {query}"
    
    config = search.to_config()
    assert config["name"] == "search"
    assert "parameters" in config

def test_tool_no_singleton_registry():
    """@tool does not register into a global singleton."""
    from tinycua_sdk import tool
    
    @tool
    def my_tool():
        pass
    
    # Tool should be a standalone instance, not registered anywhere
    assert hasattr(my_tool, 'name')
    assert hasattr(my_tool, 'invoke')
```

### test_skills.py

```python
def test_skill_construction():
    """Skill can be constructed programmatically."""
    from tinycua_sdk import Skill
    skill = Skill(name="coder", instructions="Write code")
    assert skill.name == "coder"
    assert skill.instructions == "Write code"

def test_skill_load_markdown():
    """Skill.load() parses Markdown text."""
    from tinycua_sdk import Skill
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
    assert "search" in skill.tools

def test_skill_registry_non_singleton():
    """SkillRegistry is not a singleton."""
    from tinycua_sdk import SkillRegistry, Skill
    r1 = SkillRegistry()
    r2 = SkillRegistry()
    r1.register(Skill(name="a"))
    assert r2.get("a") is None  # Independent registries

def test_skill_registry_list():
    """SkillRegistry.list_skills() returns all skills."""
    from tinycua_sdk import SkillRegistry, Skill
    registry = SkillRegistry()
    registry.register(Skill(name="a", category="dev"))
    registry.register(Skill(name="b", category="research"))
    assert len(registry.list_skills()) == 2
    assert len(registry.list_skills(category="dev")) == 1
```

### test_config.py

```python
def test_llm_model_to_dict():
    """LLMModel.to_dict() returns a plain dict."""
    from tinycua_sdk import LLMModel
    llm = LLMModel(model_name="gpt-4")
    d = llm.to_dict()
    assert d["model_name"] == "gpt-4"

def test_llm_model_from_dict():
    """LLMModel.from_dict() reconstructs the model."""
    from tinycua_sdk import LLMModel
    d = {"model_name": "gpt-4", "provider": "openai"}
    llm = LLMModel.from_dict(d)
    assert llm.model_name == "gpt-4"

def test_sdk_config_structure():
    """SDKConfig contains only framework concerns."""
    from tinycua_sdk import SDKConfig
    config = SDKConfig()
    assert hasattr(config, 'llm')
    assert hasattr(config, 'loop')
    assert hasattr(config, 'skills')
    assert hasattr(config, 'backend_url')
    assert not hasattr(config, 'memory')
    assert not hasattr(config, 'session')

def test_agent_config_round_trip():
    """AgentConfig round-trips through dict."""
    from tinycua_sdk import AgentConfig, LLMModel
    original = AgentConfig(
        name="test",
        llm_model=LLMModel(model_name="gpt-4"),
    )
    d = original.to_dict()
    restored = AgentConfig.from_dict(d)
    assert restored.name == "test"
    assert restored.llm_model.model_name == "gpt-4"
```

### test_loop.py

```python
def test_base_loop_construction():
    """BaseLoop can be constructed with max_iterations."""
    from tinycua_sdk import BaseLoop
    loop = BaseLoop(max_iterations=10)
    assert loop.max_iterations == 10

def test_base_loop_default():
    """BaseLoop defaults to reasonable max_iterations."""
    from tinycua_sdk import BaseLoop
    loop = BaseLoop()
    assert loop.max_iterations == 5

def test_base_loop_extensible():
    """BaseLoop can be subclassed."""
    from tinycua_sdk import BaseLoop
    
    class CustomLoop(BaseLoop):
        async def run(self, agent, messages, tools):
            return "Custom result"
    
    loop = CustomLoop()
    assert loop.max_iterations == 5

def test_resolve_loop_none():
    """resolve_loop(None) returns BaseLoop()."""
    from tinycua_sdk.agent.loop import resolve_loop
    loop = resolve_loop(None)
    assert isinstance(loop, BaseLoop)

def test_resolve_loop_instance():
    """resolve_loop(BaseLoop()) returns the instance."""
    from tinycua_sdk import BaseLoop
    from tinycua_sdk.agent.loop import resolve_loop
    original = BaseLoop()
    resolved = resolve_loop(original)
    assert resolved is original

def test_resolve_loop_rejects_react():
    """resolve_loop("react") raises ValueError."""
    from tinycua_sdk.agent.loop import resolve_loop
    with pytest.raises(ValueError):
        resolve_loop("react")
```

### test_templates.py

```python
def test_coder_template_exists():
    """Coder template can be loaded."""
    from tinycua_sdk import Agent
    agent = Agent.from_config("coder")  # template name
    assert agent.name == "coder"

def test_researcher_template_exists():
    """Researcher template can be loaded."""
    from tinycua_sdk import Agent
    agent = Agent.from_config("researcher")
    assert agent.name == "researcher"

def test_template_with_llm_override():
    """Template LLM can be overridden."""
    from tinycua_sdk import Agent, LLMModel
    agent = Agent.from_config("coder")
    # Override LLM
    agent.llm_model = LLMModel(model_name="custom")
    assert agent.llm_model.model_name == "custom"
```

## Mock Strategy

All tests that call `Agent.run()` must mock the LLM client to avoid requiring a running LLM server:

```python
from unittest.mock import patch, AsyncMock

# Patch the LLM call at the executor level
with patch('tinycua_sdk.agent.executor.LLMClient') as mock:
    mock.return_value.chat = AsyncMock(return_value="Mocked")
```

## Running the Tests

```bash
# These tests will FAIL initially — that's expected
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_agent.py -v

# Run with coverage
pytest tests/unit/ --cov=tinycua_sdk --cov-report=term-missing
```

## Acceptance Criteria

- [ ] All test files in `tests/unit/` are created.
- [ ] Tests cover all public APIs: Agent, Tool, Skill, Config, BaseLoop, Templates.
- [ ] Tests are organized by component (one test file per module).
- [ ] Tests use fixtures from `conftest.py`.
- [ ] Tests mock LLM calls (no external server required).
- [ ] Tests fail initially (TDD — implementation comes in later stages).
- [ ] Test suite runs without import errors.

## Dependencies

- **Requires**: Stage 01 (legacy tests deleted to avoid confusion).
- **Blocks**: Stages 03–12 (implementation must make these tests pass).
