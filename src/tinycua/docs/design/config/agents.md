# Agent Config Dataclasses

> **File:** `docs/design/config/agents.md`
> **Package:** `tinycua.config.agents`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Overview

Each agent has a typed config dataclass extending `AgentConfigBase`. Configs hold all
overridable parameters (model, instructions, agent-specific knobs, extra tools).
The factory creates an orchestrator instance from its config.

---

## `AgentConfigBase`

```python
from dataclasses import dataclass, field
from tinycua_sdk.tools.decorators import Tool
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua.config.types import TINYCUA_DEFAULT_MODEL


@dataclass
class AgentConfigBase:
    """Base configuration shared by all TinyCUA agents."""
    name: str
    instructions: str
    model: LanguageModel = field(default_factory=lambda: TINYCUA_DEFAULT_MODEL)
    extra_tools: list[Tool] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

| Field | Purpose |
|-------|---------|
| `name` | SDK `Agent` name — set by concrete config default |
| `instructions` | System prompt — set by concrete config default |
| `model` | `LanguageModel` — defaults to `TINYCUA_DEFAULT_MODEL` |
| `extra_tools` | Externally injected tools — **empty by default**. MainLoop uses this to inject per-agent tools |
| `metadata` | Free-form dict for future extensibility |

---

## Per-Agent Configs

### `QueryAnalystConfig`

```python
@dataclass
class QueryAnalystConfig(AgentConfigBase):
    name: str = "query-analyst"
    instructions: str = QUERY_ANALYST_INSTRUCTION
```

No agent-specific fields. Classification labels are in `QUERY_ANALYST_BASE_TOOLS`.

### `InformationDigesterConfig`

```python
@dataclass
class InformationDigesterConfig(AgentConfigBase):
    name: str = "information-digester"
    instructions: str = INFORMATION_DIGESTER_INSTRUCTION
    max_iterations_override: int | None = None  # None → no iteration limit
```

### `TaskCreatorConfig`

```python
@dataclass
class TaskCreatorConfig(AgentConfigBase):
    name: str = "task-creator"
    instructions: str = TASK_CREATOR_INSTRUCTION
```

### `TaskAnalyzerConfig`

```python
@dataclass
class TaskAnalyzerConfig(AgentConfigBase):
    name: str = "task-analyzer"
    instructions: str = TASK_ANALYZER_INSTRUCTION
```

### `TaskAssessorConfig`

```python
@dataclass
class TaskAssessorConfig(AgentConfigBase):
    name: str = "task-assessor"
    instructions: str = TASK_ASSESSOR_INSTRUCTION
```

### `TaskExecutorConfig`

```python
@dataclass
class TaskExecutorConfig(AgentConfigBase):
    name: str = "task-executor"
    instructions: str = TASK_EXECUTOR_INSTRUCTION
```

### `ResultReviewerConfig`

```python
from tinycua.loops.result_review_loop import DeterministicRule

@dataclass
class ResultReviewerConfig(AgentConfigBase):
    name: str = "result-reviewer"
    instructions: str = RESULT_REVIEWER_INSTRUCTION
    deterministic_rules: list[DeterministicRule] = field(
        default_factory=lambda: [DEFAULT_SCHEMA_RULE, DEFAULT_FIELDS_RULE]
    )
```

### `PrimaryAgentConfig`

```python
@dataclass
class PrimaryAgentConfig(AgentConfigBase):
    name: str = "primary-agent"
    instructions: str = PRIMARY_AGENT_INSTRUCTION
```

### `TinyCUAConfig`

```python
@dataclass
class OrchestrationSettings:
    resume_enabled: bool = True
    checkpoint_after_each_phase: bool = True


@dataclass
class TinyCUAConfig:
    name: str = "tinycua"
    instructions: str = TINYCUA_MAIN_INSTRUCTION
    model: LanguageModel = field(default_factory=lambda: TINYCUA_DEFAULT_MODEL)
    state_store: Any = None           # e.g., SQLiteStateStore instance
    artifact_store: Any = None        # e.g., FileSystemArtifactStore instance
    internal_orchestrator_overrides: dict[AgentKind, AgentConfigBase] = field(default_factory=dict)
    orchestration: OrchestrationSettings = field(default_factory=OrchestrationSettings)
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| One config per agent | Dataclass per agent kind | Typed, auto-completing; no dict-based config lookup |
| `extra_tools` in base | Shared field, empty default | Single injection channel for MainLoop or tests |
| `metadata: dict` in base | Free-form extensibility | Future fields can be promoted to typed fields without breaking the dict |
| `max_iterations_override` on InformationDigester | Agent-specific field | Only this agent has a meaningful iteration cap override |
| `deterministic_rules` on ResultReviewer | Agent-specific field | Only the review agent uses deterministic rules |


---


---

## See also

Prev : [Config Types — `AgentKind` enum, `TINYCUA_DEFAULT_MODEL`](types.md) | Next : [Pre-Configured Tool Sets (`*_BASE_TOOLS`)](../constants/tools.md)
