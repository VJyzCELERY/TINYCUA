# Stage 6: Serialization & Directory Loading — Targets

## Purpose
Verify agent serialization, skill/tool directory loading. No LLM server needed for most targets.

---

### Target 6.1: Agent to Config Round-Trip

**File:** `targets/01_config_roundtrip.py`

```python
"""Target 6.1: Verify to_config/from_dict round-trip preserves all fields."""

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
assert config["llm_model"]["model_name"] == "test-model"
assert config["llm_model"]["temperature"] == 0.2
assert len(config["tools"]) == 1
assert len(config["skills"]) == 1

# Reconstruct from dict (note: loaded tools have no callable)
a2 = Agent.from_dict(config)
assert a2.name == "tutor"
assert a2.llm_model.model_name == "test-model"
assert a2.llm_model.temperature == 0.2
print("PASS")
```

**Expected Output:** `targets/01_config_roundtrip_expected-output.txt` → `PASS`

---

### Target 6.2: JSON Export with Redaction

**File:** `targets/02_json_redaction.py`

```python
"""Target 6.2: Verify to_json redacts api_key when requested."""

from tinycua_sdk import Agent, LanguageModel

a = Agent(
    llm_model=LanguageModel(api_key="secret123"),
)

json_redacted = a.to_json(redact_sensitive=True)
assert "secret123" not in json_redacted
assert "***" in json_redacted or "redact" in json_redacted.lower()

json_full = a.to_json(redact_sensitive=False)
assert "secret123" in json_full

print("PASS")
```

**Expected Output:** `targets/02_json_redaction_expected-output.txt` → `PASS`

---

### Target 6.3: YAML Export and Import

**File:** `targets/03_yaml_export_import.py`

```python
"""Target 6.3: Verify to_yaml/from_dict round-trip."""

import tempfile
from pathlib import Path
from tinycua_sdk import Agent, LanguageModel

a = Agent(name="yaml_test", instructions="test")

# Export to YAML file
with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
    f.write(a.to_yaml())
    path = Path(f.name)

# Import back
a2 = Agent.from_yaml_file(path)
assert a2.name == "yaml_test"
assert a2.instructions == "test"

path.unlink()
print("PASS")
```

**Expected Output:** `targets/03_yaml_export_import_expected-output.txt` → `PASS`

---

### Target 6.4: Skill Directory Loading

**File:** `targets/04_skill_directory_loading.py`

```python
"""Target 6.4: Verify Skill.load_directory discovers and parses SKILL.md files."""

from pathlib import Path
from tinycua_sdk import Skill

skills_dir = Path(__file__).parent.parent / "goals" / "intermediate" / "examples" / "skills"

all_skills = Skill.load_directory(skills_dir)
assert len(all_skills) == 3

names = {s.name for s in all_skills}
assert names == {"cli_assistant", "data_analyst", "web_research"}

# Verify single skill loading
single = Skill.from_directory(skills_dir / "web_research")
assert single.name == "web_research"
assert len(single.instructions) > 0

print("PASS")
```

**Expected Output:** `targets/04_skill_directory_loading_expected-output.txt` → `PASS`

---

### Target 6.5: Tool Directory Loading

**File:** `targets/05_tool_directory_loading.py`

```python
"""Target 6.5: Verify Tool.load_directory discovers @tool-decorated functions."""

from pathlib import Path
from tinycua_sdk import Tool

tools_dir = Path(__file__).parent.parent / "goals" / "intermediate" / "examples" / "tools"

all_tools = Tool.load_directory(tools_dir)
assert len(all_tools) >= 1

# Verify calculator package loads correctly
calc_tools = Tool.load_directory(tools_dir / "calculator")
assert len(calc_tools) >= 1
tool_names = {t.name for t in calc_tools}
print(f"Calculator tools: {tool_names}")

print("PASS")
```

**Expected Output:** `targets/05_tool_directory_loading_expected-output.txt` → `Calculator tools: {...}\nPASS` (must not raise)
