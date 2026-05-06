# Implementation: Stage 1 - Core Value Objects

Implement three pure value objects with no I/O dependencies: `LanguageModel`, `Tool`/`@tool`, and `Skill`. These are immutable configuration containers that can be instantiated, serialized, and tested in complete isolation.

## Context

- **Spec Reference**: [spec.md](specs/stage-01-value-objects/spec.md)
- **Design Reference**: [design.md](specs/stage-01-value-objects/design.md)
- **Priority**: P0
- **Estimated Effort**: M

## Proposed Changes

### LanguageModel (renamed from LLMModel)

#### MODIFY `tinycua_sdk/agent/llm_model.py`

- **[Rename class]**: Rename `LLMModel` to `LanguageModel` throughout the file
- **[Rationale]**: Aligns with the SDK's naming convention and spec requirements
- **[Expand fields]**: Add all OpenAI-compatible parameters (max_tokens, top_p, frequency_penalty, presence_penalty, stop, seed, response_format, tool_choice, logprobs, top_logprobs, user)
- **[Rationale]**: Full OpenAI API compatibility per spec R-1.1
- **[Add field validators]**:
  - `_normalize_provider` — normalizes provider via `resolve_provider()`
  - `_resolve_env_vars` — substitutes `${VAR_NAME}` patterns in api_key from `os.environ`
- **[Rationale]**: Required by spec R-1.1 for provider normalization and env-var substitution
- **[Add serialization methods]**:
  - `to_dict()` — serializes to plain dict, excludes None values via `model_dump(exclude_none=True)`
  - `to_json()` — serializes to indented JSON string via `model_dump_json(indent=2)`
  - `from_dict(data)` — classmethod constructor from dict
  - `from_json(data)` — classmethod constructor from JSON string
- **[Rationale]**: Required by spec R-1.1 for serialization round-trip support
- **[Add frozen config]**: Set `model_config = ConfigDict(frozen=True)` for immutability
- **[Rationale]**: Required by spec R-1.1 for immutability guarantee

### Tool / @tool decorator

#### MODIFY `tinycua_sdk/tools/decorators.py`

- **[Add Tool.dependencies field]**: Add `dependencies: list[str] = []` parameter to `Tool.__init__`
- **[Rationale]**: Required by spec R-1.2 for optional package dependency metadata
- **[Add Tool.from_callable classmethod]**: Create `from_callable(fn, dependencies)` that inspects function signature and docstring
- **[Rationale]**: Required by spec R-1.2 for automatic schema generation from function signatures
- **[Add @tool decorator function]**: Support both `@tool` and `@tool(dependencies=["requests"])` syntax
- **[Rationale]**: Required by spec R-1.2 for decorator usage patterns
- **[Add _python_type_to_json_schema helper]**: Map Python types to JSON Schema types (str→string, int/float→number, bool→boolean, list→array, dict→object, Any/unannotated→omitted)
- **[Rationale]**: Required by spec R-1.2 for schema generation
- **[Add _parse_param_descriptions helper]**: Extract parameter descriptions from Google-style docstring Args: section
- **[Rationale]**: Required by spec R-1.2 for parameter description extraction
- **[Update Tool.to_config]**: Return OpenAI function-calling schema format `{type: "function", function: {name, description, parameters}}`
- **[Rationale]**: Required by spec R-1.2 for OpenAI compatibility
- **[Update Tool.invoke]**: Raise `RuntimeError` if `_callable` is None
- **[Rationale]**: Required by spec R-1.2 for error handling

### Skill value object

#### MODIFY `tinycua_sdk/skills/models.py`

- **[Replace with spec-compliant Skill class]**: Implement frozen Pydantic model with fields `name`, `description`, `instructions`, `metadata`
- **[Rationale]**: Required by spec R-1.3 for Skill value object
- **[Add to_dict method]**: Serialize to plain dict via `model_dump()`
- **[Rationale]**: Required by spec R-1.3 for serialization
- **[Add from_dict classmethod]**: Deserialize from dict via `cls(**data)`
- **[Rationale]**: Required by spec R-1.3 for deserialization

### SkillRegistry

#### MODIFY `tinycua_sdk/skills/registry.py`

- **[Implement SkillRegistry class]**:
  - `__init__` — initializes empty `_skills` dict
  - `register(skill)` — stores skill by name (overwrites duplicates)
  - `list_skills()` — returns list of all registered skills
  - `get(name)` — returns skill by name or None
- **[Rationale]**: Required by spec R-1.3 for skill discovery

### Package exports

#### MODIFY `tinycua_sdk/__init__.py`

- **[Add to __all__]**: Add `LanguageModel`, `Tool`, `tool`, `Skill`, `SkillRegistry`
- **[Rationale]**: Required by spec for public API exposure

### Integration tests (converted from targets)

#### NEW `tests/integration/goals/test_gs_01_language_model_definition.py`

- **[Create from targets 1.1–1.4]**: Test LanguageModel minimal creation, full configuration, serialization round-trip (to_dict/from_dict), JSON export/import (to_json/from_json)
- **[Rationale]**: Converts targets 01_minimal_creation.py, 02_full_configuration.py, 03_serialization_roundtrip.py, 04_json_export_import.py into pytest integration tests

#### NEW `tests/integration/goals/test_int_01_tool_creation.py`

- **[Create from targets 1.5–1.7]**: Test @tool schema generation, Tool.invoke execution, manual Tool construction
- **[Rationale]**: Converts targets 05_tool_schema_generation.py, 06_tool_invoke.py, 07_manual_tool_construction.py into pytest integration tests

#### NEW `tests/integration/goals/test_int_02_skills_creation.py`

- **[Create from targets 1.8–1.9]**: Test Skill creation/serialization, SkillRegistry register/list/get/overwrite operations
- **[Rationale]**: Converts targets 08_skill_creation.py, 09_skill_registry.py into pytest integration tests

#### PRESERVE `targets/` directory

- **[Keep targets folder]**: Preserve the targets directory as source of truth for Stage 1 scenarios
- **[Rationale]**: Targets serve as executable documentation and reference implementations alongside integration tests

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `LanguageModel` | Rename + Expand | Renamed from `LLMModel`, expanded with all OpenAI-compatible parameters, serialization methods, frozen immutability |
| `Tool` class | Modify | Added `dependencies` field, `from_callable` classmethod, updated `to_config` for OpenAI format |
| `@tool` decorator | New | Decorator function with type mapping and docstring parsing helpers |
| `Skill` class | Replace | New frozen Pydantic model replacing previous implementation |
| `SkillRegistry` | Modify | Updated for discovery with register/list/get/overwrite semantics |
| `__init__.py` | Modify | Add new exports for all value objects |
| `tests/integration/goals/` | New | Integration tests converted from targets/ scenarios |
| `targets/` | Preserve | Kept as source of truth alongside integration tests |

## Data Model Changes

```python
# LanguageModel (frozen Pydantic model)
class LanguageModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: str = "openai-compatible"
    model_name: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: SecretStr = SecretStr("")
    temperature: float = 1.0
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
    system_prompt: str = "You are a helpful assistant."
    strip_thinking: bool = False
    max_context: int = 128_000

# Tool (plain class with frozen-like behavior)
class Tool:
    name: str
    description: str
    parameters: dict
    _callable: Callable | None
    dependencies: list[str]

# Skill (frozen Pydantic model)
class Skill(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    description: str
    instructions: str
    metadata: dict = {}
```

## Verification Plan

### Automated Tests

- [ ] Integration test for LanguageModel creation patterns (minimal + full config) — `tests/integration/goals/test_gs_01_language_model_definition.py`
- [ ] Integration test for LanguageModel serialization round-trip (to_dict/from_dict) — `tests/integration/goals/test_gs_01_language_model_definition.py`
- [ ] Integration test for LanguageModel JSON export/import — `tests/integration/goals/test_gs_01_language_model_definition.py`
- [ ] Integration test for @tool schema generation with type mapping — `tests/integration/goals/test_int_01_tool_creation.py`
- [ ] Integration test for Tool.invoke execution — `tests/integration/goals/test_int_01_tool_creation.py`
- [ ] Integration test for manual Tool construction — `tests/integration/goals/test_int_01_tool_creation.py`
- [ ] Integration test for Skill creation and serialization — `tests/integration/goals/test_int_02_skills_creation.py`
- [ ] Integration test for SkillRegistry register/list/get/overwrite — `tests/integration/goals/test_int_02_skills_creation.py`
- [ ] Run full integration test suite — `pytest tests/integration/goals/ -v` (expected: 3 passed, 0 failed)

### Manual Verification

- [ ] Verify LanguageModel is frozen (attempt mutation raises error)
- [ ] Verify @tool decorator works with no decorator args and with dependencies arg
- [ ] Verify SkillRegistry overwrites on duplicate name registration
- [ ] Verify env-var substitution in LanguageModel.api_key resolves `${VAR_NAME}` patterns

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | >=2.0 | Frozen models, SecretStr, serialization |

### Internal Dependencies

- [x] Depends on Stage 0 (cleanup must be complete — LLMModel rename prerequisite)
- [ ] Blocks Stages 2–9 (all other stages depend on these value objects)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `resolve_provider()` not available after Stage 0 cleanup | High | Verify Stage 0 is complete before starting; add fallback provider normalization |
| Env-var substitution conflicts with SecretStr internals | Medium | Test with both literal strings and env-var references; keep literal if var not found |
| @tool type mapping incomplete for complex types | Low | Spec defines supported mappings; omit unsupported types (allows any) |
| Frozen models break existing code that mutates | High | Comprehensive integration tests catch mutation attempts; review consumers before merge |
| `exclude_none=True` in `to_dict()` loses intentional None fields | Medium | Document behavior; ensure consumers expect None exclusion |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-02*
