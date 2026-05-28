# Stage 9: Final Integration & Polish — Design

**Spec**: `specs/refactor-tinycua-sdk-v2/specs/stage-09-final-integration/spec.md`

## Final Architecture

### Module Structure

```
tinycua_sdk/
├── __init__.py              # Public API exports only
├── agent/
│   ├── __init__.py
│   ├── agent.py             # Agent (public face)
│   ├── config.py            # AgentConfig, AgentPolicy
│   ├── executor.py          # AgentExecutor, ToolExecutor
│   ├── llm_client.py        # LLMClient ABC, OpenAICompatibleClient
│   ├── llm_model.py         # LanguageModel
│   └── loop.py              # BaseLoop
├── core/
│   └── providers.py         # Provider resolution (openai-compatible only)
├── models/
│   ├── request.py           # Message, ResponseRequest, ToolDefinition
│   ├── response.py          # Response, StreamEvent, etc.
│   └── result.py            # RunResult, ToolCall (no planning stubs)
├── security/
│   ├── approval.py          # ApprovalWorkflow ABC, DefaultApprovalWorkflow
│   └── permissions.py       # Deleted or kept empty
├── skills/
│   ├── __init__.py
│   ├── models.py            # Skill
│   └── registry.py          # SkillRegistry
└── tools/
    ├── __init__.py
    ├── decorators.py        # Tool, @tool
    └── schema.py            # JSON Schema generation utilities
```

### Deleted Modules (for reference)

```
tinycua_sdk/
├── agent/
│   ├── backend_kind.py      # DELETED (H-01)
│   ├── templates.py         # DELETED (H-02)
│   ├── loader.py            # DELETED (M-03)
│   ├── loop_resolver.py     # DELETED (H-03)
│   ├── tool_resolver.py     # DELETED (H-04)
│   ├── skill_resolver.py    # DELETED (H-05)
│   ├── hooks.py             # DELETED (H-16)
│   ├── validator.py         # DELETED (M-01)
│   └── definition.py        # DELETED (collapsed into AgentConfig)
├── core/
│   └── config.py            # DELETED (M-14)
├── tools/
│   ├── cua/                 # DELETED (L-04)
│   ├── mcp.py               # DELETED (M-09)
│   ├── parser.py            # DELETED (L-18)
│   ├── resolver.py          # DELETED (M-15)
│   └── native/
│       └── context_tools.py # DELETED (M-04)
├── skills/
│   ├── cache.py             # DELETED (L-15)
│   └── improver.py          # DELETED (L-08)
├── events/                  # DELETED (L-16)
├── utils/                   # DELETED (L-17)
└── models/
    └── task.py              # DELETED (M-07)
```

## `__init__.py` Final State

```python
"""tinycua_sdk - TINYCUA AI Agent Development Kit."""

from tinycua_sdk.agent.agent import Agent
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.tools.decorators import Tool, tool
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.agent.loop import BaseLoop
from tinycua_sdk.security.approval import ApprovalWorkflow

__all__ = [
    "Agent",
    "LanguageModel",
    "Tool",
    "tool",
    "Skill",
    "SkillRegistry",
    "BaseLoop",
    "ApprovalWorkflow",
]
```

## Type Cleanup Checklist

For each file, check and fix:

1. **`agent/agent.py`**
   - `Agent.__init__` parameters: no `Any` where concrete types exist.
   - `Agent.run()` return type: `str | AsyncIterator[dict]`.
   - `Agent._call_llm()` return type: `dict[str, Any]` (acceptable `Any` for LLM response).

2. **`agent/config.py`**
   - `AgentConfig` fields: all typed.
   - `AgentPolicy` fields: all typed.

3. **`agent/llm_model.py`**
   - `LanguageModel` fields: all typed with Pydantic.

4. **`agent/loop.py`**
   - `BaseLoop.run()` signature: fully typed.
   - `messages` parameter: `list[dict[str, str]]` (or `list[dict]` for flexibility).

5. **`agent/executor.py`**
   - `ToolExecutor.execute()` parameters: fully typed.

6. **`tools/decorators.py`**
   - `@tool` decorator return type: `Tool`.
   - `Tool.invoke()` return type: `Any` (acceptable — tool return types are unknown).

7. **`skills/models.py`**
   - `Skill` fields: all typed.

## Test Strategy

### Integration Tests (16 goal tests) — The North Star
These validate the entire stack. Run them first.

```bash
pytest tests/integration/goals/ -v
```

### Unit Tests — Focused Validation
Replace old unit tests with focused tests for:

| Test File | What it tests |
|-----------|---------------|
| `test_language_model.py` | Serialization, env-var substitution, defaults |
| `test_tool.py` | Schema generation, type mapping, invoke |
| `test_skill.py` | Creation, to_dict, from_dict |
| `test_skill_registry.py` | Register, list, get, overwrite |
| `test_agent_config.py` | Config construction, to_config |
| `test_tool_executor.py` | Permission checks, approval workflow integration |
| `test_base_loop.py` | Iteration limits, cancellation, message building |
| `test_llm_client.py` | Mocked HTTP requests, response normalization |

### Mock Transport
Keep the `MockOpenAIClient` in `tests/conftest.py` or `tests/mocks/llm_client.py`:

```python
# tests/mocks/llm_client.py
from tinycua_sdk.agent.llm_client import LLMClient

class MockLLMClient(LLMClient):
    def __init__(self, responses):
        self.responses = iter(responses)

    async def chat(self, messages, tools, model_config):
        return next(self.responses)
```

## Release Readiness Checklist

- [ ] `pytest tests/integration/goals/` → 16 passed, 0 failed
- [ ] `pytest tests/unit/` → all pass
- [ ] `ruff check tinycua_sdk/` → exits 0
- [ ] `ruff format tinycua_sdk/` → run and committed
- [ ] `from tinycua_sdk import *` → only `__all__` items
- [ ] No `NotImplementedError` in production code
- [ ] `AGENTS.md` updated
- [ ] `README.md` updated (if it references old APIs)
- [ ] Changelog updated
- [ ] Version bumped in `pyproject.toml`

## Final Verification Commands

```bash
# 1. Import check
cd src/tinycua-sdk && python -c "import tinycua_sdk; print('import OK')"

# 2. Full integration suite
cd src/tinycua-sdk && pytest tests/integration/goals/ -v

# 3. Linting
cd src/tinycua-sdk && ruff check tinycua_sdk/

# 4. No stubs
cd src/tinycua-sdk && grep -r "raise NotImplementedError" tinycua_sdk/ || echo "no stubs"

# 5. Public API check
cd src/tinycua-sdk && python -c "
from tinycua_sdk import *
expected = ['Agent', 'LanguageModel', 'Tool', 'tool', 'Skill', 'SkillRegistry', 'BaseLoop', 'ApprovalWorkflow']
imported = [x for x in dir() if not x.startswith('_')]
assert sorted(imported) == sorted(expected), f'Mismatch: {sorted(imported)} vs {sorted(expected)}'
print('API OK')
"
```
