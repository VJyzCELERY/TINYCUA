# Stage 1: Core Value Objects — Design

**Spec**: `specs/refactor-tinycua-sdk-v2/specs/stage-01-value-objects/spec.md`

## File Changes

### `tinycua_sdk/agent/llm_model.py`

```python
"""LanguageModel configuration value object."""
from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from tinycua_sdk.core.providers import resolve_provider


class LanguageModel(BaseModel):
    """Immutable language model endpoint configuration."""

    model_config = ConfigDict(frozen=True)

    # --- Required with defaults ---
    provider: str = "openai-compatible"
    model_name: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: SecretStr = SecretStr("")
    temperature: float = 1.0
    system_prompt: str = "You are a helpful assistant."
    strip_thinking: bool = False
    max_context: int = 128_000

    # --- Optional OpenAI-compatible params ---
    max_tokens: int | None = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: str | list[str] | None = None
    seed: int | None = None
    response_format: dict | None = None
    tool_choice: str | dict | None = None
    logprobs: bool = False
    top_logprobs: int | None = None
    user: str | None = None

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, v: str) -> str:
        return resolve_provider(v)

    @field_validator("api_key", mode="before")
    @classmethod
    def _resolve_env_vars(cls, v: str | SecretStr) -> SecretStr:
        if isinstance(v, SecretStr):
            v = v.get_secret_value()
        # Substitute ${VAR_NAME} patterns
        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        resolved = re.sub(r"\$\{(\w+)\}", replacer, str(v))
        return SecretStr(resolved)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict, excluding None values."""
        return self.model_dump(exclude_none=True)

    def to_json(self) -> str:
        """Serialize to JSON string.

        Warning: api_key is serialized as its plain value (not redacted).
        Do not write the output of this method to logs or shared files,
        as it will expose the API key in plaintext.
        """
        import json
        data = self.model_dump(exclude_none=True)
        if isinstance(data.get("api_key"), SecretStr):
            data["api_key"] = data["api_key"].get_secret_value()
        return json.dumps(data, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LanguageModel:
        """Deserialize from plain dict."""
        return cls(**data)

    @classmethod
    def from_json(cls, data: str) -> LanguageModel:
        """Deserialize from JSON string.

        Note: api_key must be provided as a plain string in JSON.
        """
        import json
        parsed = json.loads(data)
        if isinstance(parsed.get("api_key"), str):
            parsed["api_key"] = SecretStr(parsed["api_key"])
        return cls(**parsed)
```

### `tinycua_sdk/tools/decorators.py`

```python
"""Tool decorator and Tool class."""
from __future__ import annotations

import inspect
import json
import re
from typing import Any, Callable


class Tool:
    """Represents a callable tool with an LLM-friendly schema."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        callable_: Callable | None = None,
        dependencies: list[str] | None = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self._callable = callable_
        self.dependencies = dependencies or []

    def to_config(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def invoke(self, **kwargs: Any) -> Any:
        if self._callable is None:
            raise RuntimeError(f"Tool '{self.name}' has no callable.")
        return self._callable(**kwargs)

    @classmethod
    def from_callable(
        cls,
        fn: Callable,
        dependencies: list[str] | None = None,
    ) -> Tool:
        """Create a Tool from a callable by inspecting its signature."""
        name = fn.__name__
        description = (fn.__doc__ or "").strip().split("\n")[0]

        sig = inspect.signature(fn)
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            prop: dict[str, Any] = {}
            if param.annotation is not inspect.Parameter.empty:
                prop["type"] = _python_type_to_json_schema(param.annotation)
            if param.default is inspect.Parameter.empty:
                required.append(param_name)
            properties[param_name] = prop

        # Parse docstring for param descriptions
        param_descs = _parse_param_descriptions(fn.__doc__ or "")
        for pname, pdesc in param_descs.items():
            if pname in properties:
                properties[pname]["description"] = pdesc

        parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        return cls(
            name=name,
            description=description,
            parameters=parameters,
            callable_=fn,
            dependencies=dependencies,
        )


def tool(fn: Callable | None = None, *, dependencies: list[str] | None = None) -> Tool:
    """Decorator to convert a function into a Tool."""
    def decorator(f: Callable) -> Tool:
        return Tool.from_callable(f, dependencies=dependencies)

    if fn is not None:
        return decorator(fn)
    return decorator


def _python_type_to_json_schema(py_type: type) -> str:
    """Map Python types to JSON Schema types."""
    origin = getattr(py_type, "__origin__", None)
    if origin is list or py_type is list:
        return "array"
    if origin is dict or py_type is dict:
        return "object"
    mapping = {
        str: "string",
        int: "number",
        float: "number",
        bool: "boolean",
    }
    return mapping.get(py_type, "string")  # fallback


def _parse_param_descriptions(docstring: str) -> dict[str, str]:
    """Extract parameter descriptions from Google-style docstring."""
    descriptions: dict[str, str] = {}
    args_match = re.search(r"Args:\s*\n(.+?)(?:\n\n|\n[A-Z][a-z]+:|\Z)", docstring, re.DOTALL)
    if not args_match:
        return descriptions
    args_section = args_match.group(1)
    for line in args_section.strip().split("\n"):
        line = line.strip()
        if line.startswith("-") or line.startswith("*"):
            line = line[1:].strip()
        m = re.match(r"(\w+):\s*(.+)", line)
        if m:
            descriptions[m.group(1)] = m.group(2)
    return descriptions
```

### `tinycua_sdk/skills/models.py`

```python
"""Skill value object."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Skill(BaseModel):
    """Immutable skill metadata."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    instructions: str
    metadata: dict = {}

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Skill:
        return cls(**data)
```

### `tinycua_sdk/skills/registry.py`

```python
"""Skill registry for discovery."""
from __future__ import annotations

from tinycua_sdk.skills.models import Skill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)
```

### `tinycua_sdk/__init__.py` (update)

```python
from tinycua_sdk.agent import LanguageModel
from tinycua_sdk.tools.decorators import Tool, tool
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.skills.registry import SkillRegistry

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentDefinition",
    "AgentExecutor",
    "AgentPolicy",
    "BaseLoop",
    "LanguageModel",
    "Skill",
    "SkillRegistry",
    "Tool",
    "tool",
]
```

## Data Flow

No data flow — these are pure value objects. Construction is direct:

```
Consumer code
    │
    ├──► LanguageModel(**kwargs) ──► frozen Pydantic instance
    ├──► @tool decorator ──► Tool instance wrapping function
    └──► Skill(**kwargs) ──► frozen Pydantic instance
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `Tool.invoke()` with no callable | `RuntimeError` |
| `@tool` on a function with no docstring | `description` is empty string |
| `@tool` on a function with unannotated params | Type omitted from schema (allows any) |
| `LanguageModel` with unknown provider | Resolved by `resolve_provider()`; may keep literal string |

## Testing Strategy

- Unit tests for `_python_type_to_json_schema` mapping.
- Unit tests for `_parse_param_descriptions` with various docstring styles.
- Unit tests for env-var substitution in `LanguageModel`.
- Integration tests (the goal scripts) validate the public API.
