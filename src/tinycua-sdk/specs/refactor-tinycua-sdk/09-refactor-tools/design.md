# Stage 09 — Design: Refactor Tools Framework

## Overview

Clean up the `tools/` package to contain only the framework (decorator, schema, parser, resolver) and generic built-in tools. Remove memory-dependent tools. Ensure `@tool` returns a `Tool` instance directly with no side effects.

## Design Decisions

### What Stays

The SDK provides the **tool framework** — the primitives for defining and using tools:

1. **`@tool` decorator**: Converts a function into a `Tool` dataclass instance
2. **`Tool` dataclass**: Value object with metadata, schema, and invocation
3. **`schema.py`**: JSON-schema generation from function signatures
4. **`parser.py`**: Source code parsing for tool introspection
5. **`resolver.py`**: Pure functions for dependency resolution
6. **`mcp.py`**: MCP (Model Context Protocol) integration
7. **`cua/`**: CUA (Computer Use Agent) sub-package
8. **`native/context_tools.py`**: Generic context utilities (stateless)

### What Is Deleted

1. **`tools/memory.py`**: MemoryBackend hierarchy — stateful
2. **`tools/memory_tools.py`**: `remember`, `recall`, `forget` — depend on memory

### What Is Moved

1. **`skills/tools.py`**: Skill-native tools → `tools/native/skills_tools.py`
2. **`CallableTool`**: Delete (redundant — standard `Tool.invoke()` handles kwargs)

## Package Layout (Target)

```
tools/
  __init__.py
  decorators.py          # @tool, Tool dataclass
  schema.py              # JSON-schema generation
  parser.py              # Source parsing
  resolver.py            # Dependency resolution (pure functions)
  mcp.py                 # MCP integration
  cua/                   # CUA helpers
  native/                # Built-in tools shipped with the SDK
    __init__.py
    context_tools.py     # Generic context utilities
    skills_tools.py      # Skill-native tools (moved from skills/)
```

## Code Changes

### decorators.py

```python
# BEFORE
from tinycua_sdk.core.registry import ToolRegistry

@dataclass
class Tool:
    ...

def tool(func=None, *, name=None, description=None):
    def decorator(fn):
        t = Tool(...)
        ToolRegistry.register(t)  # SIDE EFFECT
        return t
    return decorator

# AFTER
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    _fn: Callable | None = field(default=None, repr=False)
    _source: str | None = field(default=None, repr=False)
    _external_dependencies: list[str] = field(default_factory=list)
    _tool_dependencies: list[dict] = field(default_factory=list)
    _version: str | None = field(default=None, repr=False)
    
    def to_config(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
    
    def to_bundle(self) -> dict[str, Any]:
        return {
            **self.to_config(),
            "source": self._source,
            "external_dependencies": self._external_dependencies,
            "tool_dependencies": self._tool_dependencies,
            "version": self._version,
        }
    
    def invoke(self, **kwargs: Any) -> Any:
        if self._fn is None:
            raise RuntimeError(f"Tool {self.name} has no function")
        return self._fn(**kwargs)

def tool(func=None, *, name=None, description=None):
    """Decorator that converts a function into a Tool instance.
    
    Returns a Tool instance directly. No global registration.
    """
    def decorator(fn):
        return Tool(
            name=name or fn.__name__,
            description=description or fn.__doc__ or "",
            parameters=_extract_schema(fn),
            _fn=fn,
            _source=_get_source(fn),
        )
    
    if func is not None:
        return decorator(func)
    return decorator
```

### __init__.py

```python
# BEFORE
from .decorators import tool, Tool
from .memory import MemoryBackend, get_memory_backend  # Deleted
from .memory_tools import remember, recall, forget  # Deleted

# AFTER
from .decorators import tool, Tool
from .schema import generate_schema
from .mcp import MCPClient

__all__ = ["tool", "Tool", "generate_schema", "MCPClient"]
```

### Remove CallableTool

```python
# skills/tools.py — DELETE CallableTool
# It exists solely to convert positional args to kwargs.
# Tool.invoke() already accepts **kwargs, so CallableTool is redundant.

# BEFORE
class CallableTool:
    def __init__(self, fn):
        self.fn = fn
        self.sig = inspect.signature(fn)
    
    def __call__(self, *args, **kwargs):
        bound = self.sig.bind(*args, **kwargs)
        return self.fn(**bound.arguments)

# AFTER
# Just use the standard Tool.invoke(**kwargs)
```

## Future-Proofing

The `Tool` dataclass reserves fields for future dependency resolution:

- `_external_dependencies`: Python packages the tool needs (e.g., `requests`, `pandas`)
- `_tool_dependencies`: Other tools this tool depends on
- `_version`: Tool version for compatibility checking

The **consumer** (not the SDK) will implement:
1. Parsing `@tool(dependencies=["requests"])` from the bundle
2. Creating isolated `.venv` environments per tool
3. Activating the tool's `.venv` before `invoke()`

## Acceptance Criteria

- [ ] `tools/memory.py` does not exist.
- [ ] `tools/memory_tools.py` does not exist.
- [ ] `@tool` decorator returns a `Tool` instance directly (no side effects).
- [ ] `ToolRegistry` singleton is not used in `tools/`.
- [ ] `CallableTool` is deleted (replaced by standard `Tool.invoke()`).
- [ ] `tools/__init__.py` does not export memory-related symbols.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02, Stage 08.
- **Blocks**: Stage 11 (Agent refactor depends on clean tool framework).
