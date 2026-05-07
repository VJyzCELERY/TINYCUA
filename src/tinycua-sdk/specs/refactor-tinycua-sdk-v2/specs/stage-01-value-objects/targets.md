# Stage 1: Core Value Objects — Targets

## Purpose
Verify `LanguageModel`, `Tool`/`@tool`, and `Skill` work as pure value objects. No LLM calls needed.

---

### Target 1.1: LanguageModel Minimal Creation

**File:** `targets/01_minimal_creation.py`

```python
"""Target 1.1: Create a minimal LanguageModel with defaults."""

from tinycua_sdk import LanguageModel

m = LanguageModel(model_name="qwen/qwen3.5-9b")

assert m.provider == "openai-compatible"
assert m.model_name == "qwen/qwen3.5-9b"
assert m.temperature == 1.0
assert m.max_tokens is None
print("PASS")
```

**Expected Output:** `targets/01_minimal_creation_expected-output.txt` → `PASS`

---

### Target 1.2: LanguageModel Full Configuration

**File:** `targets/02_full_configuration.py`

```python
"""Target 1.2: Create a LanguageModel with all OpenAI-compatible params."""

from tinycua_sdk import LanguageModel

m = LanguageModel(
    provider="openai",
    model_name="gpt-4o",
    api_key="${OPENAI_API_KEY}",
    temperature=0.5,
    max_tokens=8192,
    top_p=0.9,
    frequency_penalty=0.1,
    presence_penalty=0.1,
    response_format={"type": "json_object"},
    system_prompt="You are terse.",
)

assert m.provider == "openai"
assert m.model_name == "gpt-4o"
assert m.temperature == 0.5
assert m.max_tokens == 8192
assert m.top_p == 0.9
assert m.frequency_penalty == 0.1
assert m.presence_penalty == 0.1
assert m.response_format == {"type": "json_object"}
print("PASS")
```

**Expected Output:** `targets/02_full_configuration_expected-output.txt` → `PASS`

---

### Target 1.3: LanguageModel Serialization Round-Trip

**File:** `targets/03_serialization_roundtrip.py`

```python
"""Target 1.3: Verify to_dict/from_dict round-trip preserves all data."""

from tinycua_sdk import LanguageModel

original = LanguageModel(
    model_name="test-model",
    temperature=0.3,
    max_tokens=512,
    top_p=0.8,
    frequency_penalty=0.2,
    presence_penalty=0.1,
    response_format={"type": "json_object"},
)

restored = LanguageModel.from_dict(original.to_dict())

assert restored.model_name == original.model_name
assert restored.temperature == original.temperature
assert restored.max_tokens == original.max_tokens
assert restored.top_p == original.top_p
assert restored.frequency_penalty == original.frequency_penalty
assert restored.presence_penalty == original.presence_penalty
assert restored.response_format == original.response_format
print("PASS")
```

**Expected Output:** `targets/03_serialization_roundtrip_expected-output.txt` → `PASS`

---

### Target 1.4: LanguageModel JSON Export/Import

**File:** `targets/04_json_export_import.py`

```python
"""Target 1.4: Verify to_json/from_json round-trip."""

from tinycua_sdk import LanguageModel

original = LanguageModel(
    model_name="json-test",
    temperature=0.7,
    max_tokens=256,
)

json_str = original.to_json()
restored = LanguageModel.from_json(json_str)

assert restored.model_name == original.model_name
assert restored.temperature == original.temperature
assert restored.max_tokens == original.max_tokens
print("PASS")
```

**Expected Output:** `targets/04_json_export_import_expected-output.txt` → `PASS`

---

### Target 1.5: @tool Schema Generation

**File:** `targets/05_tool_schema_generation.py`

```python
"""Target 1.5: Verify @tool generates correct OpenAI function schema."""

from tinycua_sdk import tool

@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Fetch weather for a city.
    
    Args:
        city: Name of the city (e.g., "Tokyo").
        unit: Temperature unit ("celsius" or "fahrenheit").
    """
    return f"sunny in {city}"

schema = get_weather.to_config()

assert schema["type"] == "function"
assert schema["function"]["name"] == "get_weather"
assert schema["function"]["description"] == "Fetch weather for a city."
assert "city" in schema["function"]["parameters"]["properties"]
assert "unit" in schema["function"]["parameters"]["properties"]
assert schema["function"]["parameters"]["required"] == ["city"]
print("PASS")
```

**Expected Output:** `targets/05_tool_schema_generation_expected-output.txt` → `PASS`

---

### Target 1.6: Tool.invoke Works

**File:** `targets/06_tool_invoke.py`

```python
"""Target 1.6: Verify @tool-decorated function can be invoked."""

from tinycua_sdk import tool

@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

result = add.invoke(a=2, b=3)
assert result == 5

# Test with keyword args
result2 = add.invoke(a=10, b=20)
assert result2 == 30

print("PASS")
```

**Expected Output:** `targets/06_tool_invoke_expected-output.txt` → `PASS`

---

### Target 1.7: Tool Manual Construction

**File:** `targets/07_manual_tool_construction.py`

```python
"""Target 1.7: Verify manual Tool construction works."""

from tinycua_sdk import Tool

dynamic = Tool(
    name="reverse_string",
    description="Reverse a string.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
)

schema = dynamic.to_config()
assert schema["function"]["name"] == "reverse_string"
assert schema["function"]["description"] == "Reverse a string."
print("PASS")
```

**Expected Output:** `targets/07_manual_tool_construction_expected-output.txt` → `PASS`

---

### Target 1.8: Skill Creation and Serialization

**File:** `targets/08_skill_creation.py`

```python
"""Target 1.8: Verify Skill creation, to_dict, from_dict."""

from tinycua_sdk import Skill

s = Skill(
    name="web_research",
    description="Research topics using web search.",
    instructions="Use the web_search tool for current events.",
    metadata={"category": "research"},
)

d = s.to_dict()
assert d["name"] == "web_research"
assert d["description"] == "Research topics using web search."
assert d["metadata"]["category"] == "research"

restored = Skill.from_dict(d)
assert restored.name == s.name
assert restored.description == s.description
print("PASS")
```

**Expected Output:** `targets/08_skill_creation_expected-output.txt` → `PASS`

---

### Target 1.9: SkillRegistry Operations

**File:** `targets/09_skill_registry.py`

```python
"""Target 1.9: Verify SkillRegistry register, list, get."""

from tinycua_sdk import Skill
from tinycua_sdk.skills.registry import SkillRegistry

s1 = Skill(name="coder", description="Write code", instructions="Use PEP 8.")
s2 = Skill(name="tester", description="Write tests", instructions="Cover edge cases.")

registry = SkillRegistry()
registry.register(s1)
registry.register(s2)

assert len(registry.list_skills()) == 2
assert registry.get("coder").name == "coder"
assert registry.get("nonexistent") is None

# Overwrite: register s1 again with different description
s3 = Skill(name="coder", description="Write code v2", instructions="Use PEP 8.")
registry.register(s3)
assert len(registry.list_skills()) == 2
assert registry.get("coder").name == "coder"
assert registry.get("coder").description == "Write code v2"

print("PASS")
```

**Expected Output:** `targets/09_skill_registry_expected-output.txt` → `PASS`
