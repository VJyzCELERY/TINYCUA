# Stage 12 — Design: Refactor Core Config

## Overview

Update `core/config.py` (`SDKConfig`) to contain only framework-level configuration. Remove stateful concerns (`memory`, `session`, `environment`).

## Design Decisions

### Why Remove memory, session, environment?

1. **memory**: Out of scope — consumer manages memory systems.
2. **session**: Out of scope — consumer manages session lifecycle.
3. **environment**: Dev/staging/prod is a deployment concern, not an SDK concern.

### What Stays?

1. **llm**: Default LLM configuration for agents created without explicit LLMModel.
2. **loop**: Default loop configuration (max_iterations only).
3. **skills**: Default skill loading configuration (directories, auto_load).
4. **backend_url**: Default backend URL for remote execution (consumer may use this).

## Config Classes (Target)

### LLMConfig

```python
class LLMConfig(BaseModel):
    """Default LLM configuration for SDK-wide defaults."""
    model_config = ConfigDict(frozen=True)
    
    provider: str = "openai-compatible"
    model: str = "gpt-4o-mini"
    base_url: str = "http://localhost:1234/v1"
    api_key: SecretStr = SecretStr("")
    temperature: float = 1.0
    
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMConfig":
        return cls(**data)
```

### LoopConfig

```python
class LoopConfig(BaseModel):
    """Default loop configuration."""
    model_config = ConfigDict(frozen=True)
    
    max_iterations: int = 5
    # No 'type' field — SDK provides only BaseLoop
    
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopConfig":
        return cls(**data)
```

### SkillsConfig

```python
class SkillsConfig(BaseModel):
    """Default skill loading configuration.
    
    Note: These defaults are used by consumer code that chooses
    to load skills from directories. The SDK itself does not
    perform filesystem I/O.
    """
    model_config = ConfigDict(frozen=True)
    
    directories: list[str] = Field(default_factory=lambda: ["./skills"])
    auto_load: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillsConfig":
        return cls(**data)
```

### SDKConfig

```python
class SDKConfig(BaseModel):
    """Framework-level configuration."""
    model_config = ConfigDict(frozen=True)
    
    llm: LLMConfig = Field(default_factory=LLMConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    backend_url: str = "http://localhost:8000"
    
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SDKConfig":
        return cls(**data)
    
    @classmethod
    def from_yaml(cls, path: str | Path) -> "SDKConfig":
        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f))
    
    @classmethod
    def from_json(cls, path: str | Path) -> "SDKConfig":
        with open(path) as f:
            return cls.from_dict(json.load(f))
```

## Removed Fields

| Field | Reason |
|-------|--------|
| `memory` | Out of scope — consumer concern |
| `session` | Out of scope — consumer concern |
| `environment` | Deployment concern — not SDK concern |

## Migration from Old Config

### Before
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

### After
```python
class SDKConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    backend_url: str = "http://localhost:8000"
```

## Note on Context/Security Configs

Context compression, security permissions, and approval modes are **consumer concerns**. The SDK's `Agent` accepts `instructions` as a string; the consumer decides how to construct it (including any context window management or permission checks). The `LLMModel` carries the `system_prompt` for model-specific behavior tuning.

## Acceptance Criteria

- [ ] `SDKConfig` contains only `llm`, `loop`, `skills`, `backend_url`.
- [ ] `LoopConfig` has no `type` field.
- [ ] `memory`, `session`, `environment` fields are removed.
- [ ] All config classes support `from_dict()` / `to_dict()`.
- [ ] `from_yaml()` and `from_json()` classmethods work.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, 02, 11.
- **Blocks**: None.
