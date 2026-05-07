# Implementation: Stage 12 — Refactor Core Config

Refactor `core/config.py` so `SDKConfig` contains only framework-level configuration (LLM, loop, skills, backend_url) and removes stateful concerns (`memory`, `session`, `environment`). All config classes gain `from_dict()`, `to_dict()`, `from_yaml()`, and `from_json()` support.

## Context

- **Spec Reference**: `spec.md`
- **Design Reference**: `design.md`
- **Priority**: P1
- **Estimated Effort**: S

## Proposed Changes

### core/config.py

#### [MODIFY] `core/config.py`

- **[Description of change]**: Remove `MemoryConfig`, `SessionConfig`, and `environment` from `SDKConfig`. Add `model_config = ConfigDict(frozen=True)` to `LLMConfig`, `LoopConfig`, `SkillsConfig`, and `SDKConfig`.
- **[Rationale]**: Memory and session are consumer concerns, not SDK concerns. `environment` is a deployment concern.

#### [MODIFY] `LLMConfig` in `core/config.py`

- **[Description of change]**: Ensure `LLMConfig` has `provider`, `model`, `base_url`, `api_key` (as `SecretStr`), and `temperature`. Add `to_dict()` and `from_dict()` methods.
- **[Rationale]**: Consistent serialization support per design.

#### [MODIFY] `LoopConfig` in `core/config.py`

- **[Description of change]**: Ensure `LoopConfig` has only `max_iterations` (no `type` field). Add `to_dict()` and `from_dict()` methods.
- **[Rationale]**: SDK provides only `BaseLoop`; loop type selection is a consumer concern.

#### [MODIFY] `SkillsConfig` in `core/config.py`

- **[Description of change]**: Ensure `SkillsConfig` has `directories` and `auto_load`. Add `to_dict()` and `from_dict()` methods.
- **[Rationale]**: Skill loading defaults need serialization support.

#### [MODIFY] `SDKConfig` in `core/config.py`

- **[Description of change]**: Keep `llm`, `loop`, `skills`, and `backend_url`. Remove `memory`, `session`, and `environment`. Add `to_dict()`, `from_dict()`, `from_yaml()`, and `from_json()` classmethods.
- **[Rationale]**: Framework-level config only; consumer handles memory/session.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `LLMConfig` | Modify | Add `model_config = ConfigDict(frozen=True)`, `to_dict()`, `from_dict()` |
| `LoopConfig` | Modify | Add `model_config = ConfigDict(frozen=True)`, `to_dict()`, `from_dict()` |
| `SkillsConfig` | Modify | Add `model_config = ConfigDict(frozen=True)`, `to_dict()`, `from_dict()` |
| `SDKConfig` | Modify | Remove `memory`, `session`, `environment`; add frozen config, serialization helpers |
| `MemoryConfig` | Remove | Removed from `SDKConfig` (consumer concern) |
| `SessionConfig` | Remove | Removed from `SDKConfig` (consumer concern) |

## Data Model Changes

```python
class LLMConfig(BaseModel):
    """Default LLM configuration for SDK-wide defaults."""
    model_config = ConfigDict(frozen=True)
    provider: str = "openai-compatible"
    model: str = "gpt-4o-mini"
    base_url: str = "http://localhost:1234/v1"
    api_key: SecretStr = SecretStr("")
    temperature: float = 1.0

class LoopConfig(BaseModel):
    """Default loop configuration."""
    model_config = ConfigDict(frozen=True)
    max_iterations: int = 5

class SkillsConfig(BaseModel):
    """Default skill loading configuration."""
    model_config = ConfigDict(frozen=True)
    directories: list[str] = Field(default_factory=lambda: ["./skills"])
    auto_load: bool = True

class SDKConfig(BaseModel):
    """Framework-level configuration."""
    model_config = ConfigDict(frozen=True)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    backend_url: str = "http://localhost:8000"
```

## Verification Plan

### Automated Tests

- [ ] Unit tests for `LLMConfig.from_dict()` / `to_dict()`
- [ ] Unit tests for `LoopConfig.from_dict()` / `to_dict()`
- [ ] Unit tests for `SkillsConfig.from_dict()` / `to_dict()`
- [ ] Unit tests for `SDKConfig.from_dict()` / `to_dict()`
- [ ] Unit tests for `SDKConfig.from_yaml()`
- [ ] Unit tests for `SDKConfig.from_json()`
- [ ] Full `pytest` suite passes for remaining tests

### Manual Verification

- [ ] Verify `SDKConfig` does not expose `memory`, `session`, or `environment`
- [ ] Verify all config classes are frozen (`model_config = ConfigDict(frozen=True)`)

## Rollout Strategy

1. **Phase 1** (Refactor): Update `core/config.py` to new structure.
2. **Phase 2** (Tests): Update or add unit tests to cover new serialization methods and removed fields.
3. **Phase 3** (Verification): Run full test suite to ensure nothing else breaks.

## Dependencies

### Internal Dependencies

- [ ] Depends on Stage 01, Stage 02, Stage 11
- [ ] Blocks: None

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Other code references `SDKConfig.memory` or `SDKConfig.session` | High | Run full test suite; fix any breakages before merge |
| Missing imports (`yaml`, `json`, `Path`) | Low | Add necessary imports in `core/config.py` |

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
