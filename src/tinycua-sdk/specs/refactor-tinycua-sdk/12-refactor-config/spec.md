# Stage 12 — Refactor Core Config

## Objective

Update `core/config.py` (`SDKConfig`) to contain only framework-level configuration. Remove stateful concerns.

## Files to Modify

| File | Changes |
|------|---------|
| `core/config.py` | Refactor `SDKConfig` structure |

## Config Changes

### BEFORE
```python
class SDKConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    backend_url: str = "http://localhost:8000"
    environment: str = "dev"
```

### AFTER
```python
class LLMConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: str = "openai-compatible"
    model: str = "gpt-4o-mini"
    base_url: str = "http://localhost:1234/v1"
    api_key: SecretStr = SecretStr("")
    temperature: float = 1.0

class LoopConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: str = "default"
    max_iterations: int = 5

class SkillsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    directories: list[str] = Field(default_factory=lambda: ["./skills"])
    auto_load: bool = True

class SDKConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    backend_url: str = "http://localhost:8000"
```

## Removed Fields

- `memory` — out of scope
- `session` — out of scope
- `environment` — not needed (see refactor-target §6.3)

## Acceptance Criteria

- [ ] `SDKConfig` does not have `memory`, `session`, or `environment` fields.
- [ ] `SDKConfig.from_env()` loads framework config from env vars.
- [ ] `SDKConfig.from_yaml()` loads framework config from YAML files.
- [ ] New unit tests from Stage 02 pass.

## Dependencies

- **Requires**: Stage 01, Stage 02
