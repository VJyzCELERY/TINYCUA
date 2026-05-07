# Stage 2: Agent Configuration & Creation — Targets

## Purpose
Verify `Agent` can be instantiated and configured with all parameters. No LLM calls needed.

---

### Target 2.1: Minimal Agent Creation

**File:** `targets/01_minimal_agent.py`

```python
"""Target 2.1: Create a minimal Agent with no arguments."""

from tinycua_sdk import Agent

a = Agent()

assert a.name == "assistant"
assert a.instructions == ""
assert a.llm_model.model_name == "gpt-4o-mini"
assert len(a.tools) == 0
assert len(a.skills) == 0
print("PASS")
```

**Expected Output:** `targets/01_minimal_agent_expected-output.txt` → `PASS`

---

### Target 2.2: Named Agent with Instructions and Model

**File:** `targets/02_named_agent.py`

```python
"""Target 2.2: Create a named agent with custom instructions and model."""

from tinycua_sdk import Agent, LanguageModel

a = Agent(
    name="greeter",
    instructions="You are a friendly greeter.",
    llm_model=LanguageModel(
        provider="openai-compatible",
        model_name="qwen/qwen3.5-9b",
        base_url="http://localhost:1234/v1",
        api_key="dummy",
    ),
)

assert a.name == "greeter"
assert a.instructions == "You are a friendly greeter."
assert a.llm_model.model_name == "qwen/qwen3.5-9b"
print("PASS")
```

**Expected Output:** `targets/02_named_agent_expected-output.txt` → `PASS`

---

### Target 2.3: Agent with Policy

**File:** `targets/03_agent_with_policy.py`

```python
"""Target 2.3: Create an agent with custom policy settings."""

from tinycua_sdk import Agent, AgentPolicy

a = Agent(
    name="researcher",
    instructions="Cite your sources.",
    policy=AgentPolicy(max_tool_calls=15, parallel_tool_calls=True),
)

assert a.policy.max_tool_calls == 15
assert a.policy.parallel_tool_calls is True
print("PASS")
```

**Expected Output:** `targets/03_agent_with_policy_expected-output.txt` → `PASS`

---

### Target 2.4: Agent with Metadata

**File:** `targets/04_agent_with_metadata.py`

```python
"""Target 2.4: Create an agent with consumer-defined metadata."""

from tinycua_sdk import Agent

a = Agent(
    name="tagged_assistant",
    instructions="Help the user.",
    metadata={
        "team": "platform",
        "cost_center": "eng-123",
        "version": "2.1.0",
    },
)

assert a.metadata["team"] == "platform"
assert a.metadata["cost_center"] == "eng-123"
print("PASS")
```

**Expected Output:** `targets/04_agent_with_metadata_expected-output.txt` → `PASS`

---

### Target 2.5: Dynamic add_tools and add_skills

**File:** `targets/05_dynamic_composition.py`

```python
"""Target 2.5: Verify tools and skills can be added after creation."""

from tinycua_sdk import Agent, Skill, tool

@tool
def calc(expr: str) -> str:
    """Evaluate expression."""
    return str(eval(expr))

s = Skill(name="math", description="Math help", instructions="Show work.")

a = Agent()
assert len(a.tools) == 0
assert len(a.skills) == 0

a.add_tools(calc)
a.add_skills(s)

assert len(a.tools) == 1
assert a.tools[0].name == "calc"
assert len(a.skills) == 1
assert a.skills[0].name == "math"

# Test list input
@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

s2 = Skill(name="testing", description="Write tests", instructions="Cover edge cases.")
a.add_tools([add])
a.add_skills([s2])

assert len(a.tools) == 2
assert len(a.skills) == 2
print("PASS")
```

**Expected Output:** `targets/05_dynamic_composition_expected-output.txt` → `PASS`

---

### Target 2.6: to_config Serializes All Fields

**File:** `targets/06_to_config.py`

```python
"""Target 2.6: Verify to_config() captures all fields."""

from tinycua_sdk import Agent, LanguageModel, Skill, tool

@tool
def calc(expr: str) -> str:
    """Evaluate expression."""
    return str(eval(expr))

s = Skill(name="math", description="Math help", instructions="Show work.")

a = Agent(
    name="tutor",
    instructions="Be patient.",
    llm_model=LanguageModel(model_name="test-model", temperature=0.2),
    tools=[calc],
    skills=[s],
)

config = a.to_config()

assert config["name"] == "tutor"
assert config["instructions"] == "Be patient."
assert config["llm_model"]["model_name"] == "test-model"
assert config["llm_model"]["temperature"] == 0.2
assert len(config["tools"]) == 1
assert config["tools"][0]["function"]["name"] == "calc"
assert len(config["skills"]) == 1
assert config["skills"][0]["name"] == "math"
assert "tool_permissions" in config
assert config["tool_permissions"] == {}
print("PASS")
```

**Expected Output:** `targets/06_to_config_expected-output.txt` → `PASS`
