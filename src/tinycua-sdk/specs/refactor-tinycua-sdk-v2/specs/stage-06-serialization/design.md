# Stage 6: Serialization & Directory Loading — Design

## Agent Serialization

### `Agent.to_config()`

```python
def to_config(self, redact_sensitive: bool = False) -> dict:
    llm_dict = self.llm_model.to_dict()
    if redact_sensitive:
        llm_dict["api_key"] = "***"

    return {
        "name": self.name,
        "instructions": self.instructions,
        "llm_model": llm_dict,
        "tools": [t.to_config() for t in self.tools],
        "skills": [s.to_dict() for s in self.skills],
        "policy": self.policy.model_dump(),
        "metadata": self.metadata,
        "tool_permissions": self.tool_permissions,
    }
```

### `Agent.to_json()` / `Agent.to_yaml()`

```python
def to_json(self, indent: int = 2, redact_sensitive: bool = True) -> str:
    import json
    return json.dumps(self.to_config(redact_sensitive=redact_sensitive), indent=indent)

def to_yaml(self, redact_sensitive: bool = True) -> str:
    import yaml
    return yaml.dump(self.to_config(redact_sensitive=redact_sensitive), default_flow_style=False)
```

### `Agent.from_dict()`

```python
@classmethod
def from_dict(cls, config: dict) -> Agent:
    llm_data = config.get("llm_model", {})
    llm_model = LanguageModel.from_dict(llm_data) if isinstance(llm_data, dict) else LanguageModel()

    tools_data = config.get("tools", [])
    tools = [Tool.from_config(t) if isinstance(t, dict) else t for t in tools_data]

    skills_data = config.get("skills", [])
    skills = [Skill.from_dict(s) if isinstance(s, dict) else s for s in skills_data]

    policy_data = config.get("policy", {})
    policy = AgentPolicy(**policy_data) if isinstance(policy_data, dict) else AgentPolicy()

    return cls(
        name=config.get("name", "assistant"),
        instructions=config.get("instructions", ""),
        llm_model=llm_model,
        tools=tools,
        skills=skills,
        policy=policy,
        metadata=config.get("metadata", {}),
        tool_permissions=config.get("tool_permissions", {}),
    )
```

**Note:** `loop` and `approval_workflow` are not serialized. They are runtime objects that consumers must re-attach after loading.

### `Tool.from_config()`

```python
@classmethod
def from_config(cls, config: dict) -> Tool:
    func_cfg = config.get("function", {})
    return cls(
        name=func_cfg["name"],
        description=func_cfg["description"],
        parameters=func_cfg["parameters"],
        callable_=None,  # Cannot serialize callables
    )
```

Loaded tools without callables cannot be invoked. For round-trip testing, we use tools that don't need to be invoked, or we re-attach callables manually.

## Skill Directory Loading

### `Skill.load_directory()`

```python
from pathlib import Path
import yaml

class Skill:
    # ... existing methods ...

    @classmethod
    def load_directory(cls, path: Path) -> list[Skill]:
        skills = []
        for subdir in sorted(Path(path).iterdir()):
            if subdir.is_dir() and (subdir / "SKILL.md").exists():
                skills.append(cls.from_directory(subdir))
        return skills

    @classmethod
    def from_directory(cls, path: Path) -> Skill:
        skill_md = Path(path) / "SKILL.md"
        content = skill_md.read_text()

        # Parse frontmatter
        frontmatter = {}
        instructions = content
        if content.startswith("---"):
            _, frontmatter_yaml, instructions = content.split("---", 2)
            frontmatter = yaml.safe_load(frontmatter_yaml) or {}
            instructions = instructions.strip()

        name = frontmatter.pop("name", path.name)
        description = frontmatter.pop("description", "")

        return cls(
            name=name,
            description=description,
            instructions=instructions,
            metadata=frontmatter,
        )
```

## Tool Directory Loading

### `Tool.load_directory()`

```python
import importlib.util
import inspect
import sys
from pathlib import Path

class Tool:
    # ... existing methods ...

    @classmethod
    def load_directory(cls, path: Path) -> list[Tool]:
        tools = []
        for subdir in sorted(Path(path).iterdir()):
            if not subdir.is_dir():
                continue
            for py_file in sorted(subdir.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                module = _load_module_from_path(py_file)
                for name, obj in inspect.getmembers(module):
                    if isinstance(obj, Tool):
                        tools.append(obj)
        return tools


def _load_module_from_path(path: Path):
    """Load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
```

**Important:** Loading modules from arbitrary directories can have side effects. We:
1. Only scan `.py` files.
2. Skip files starting with `_`.
3. Do not execute `__main__` blocks (the loader handles this).

## Data Flow

```
Agent.to_config()
    │
    ├──► llm_model.to_dict() ──► dict with api_key redacted if requested
    ├──► [t.to_config() for t in tools] ──► list of function schemas
    ├──► [s.to_dict() for s in skills] ──► list of skill dicts
    └──► policy.model_dump() ──► dict

Agent.from_dict(config)
    │
    ├──► LanguageModel.from_dict(config["llm_model"])
    ├──► [Tool.from_config(t) for t in config["tools"]]
    ├──► [Skill.from_dict(s) for s in config["skills"]]
    └──► Agent(...)  # reconstructed

Skill.load_directory(path)
    │
    ├──► Iterate subdirectories
    ├──► Find SKILL.md
    ├──► Parse frontmatter (YAML)
    └──► Skill(name, description, instructions, metadata)

Tool.load_directory(path)
    │
    ├──► Iterate subdirectories
    ├──► Find .py files
    ├──► importlib.util.load_module
    ├──► inspect.getmembers for Tool instances
    └──► Collect Tool objects
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| SKILL.md missing in subdirectory | Skip subdirectory silently |
| SKILL.md without frontmatter | Use filename as name, empty description, full content as instructions |
| Tool directory has no @tool functions | Return empty list |
| from_dict with missing keys | Use defaults |
| from_dict with unknown keys | Ignore (forward compatibility) |
| Loaded tool has no callable | `RuntimeError` on invoke |

## File Changes

| File | Change |
|------|--------|
| `agent/agent.py` | Add `to_json`, `to_yaml`, `from_json_file`, `from_yaml_file`, `from_dict` |
| `tools/decorators.py` | Add `from_config`, `load_directory` classmethods |
| `skills/models.py` | Add `load_directory`, `from_directory` classmethods |

## Testing Strategy

- Round-trip test: create agent → to_dict → from_dict → assert equality.
- Redaction test: verify `***` in redacted output, full value in non-redacted.
- Directory loading test: create temp dirs with SKILL.md and .py files, load and verify counts.
- File-based round-trip: export to temp file, load back, assert equality.
