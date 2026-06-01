# Agent Config Dataclasses

> **File:** `docs/design/config/agents.md`
> **Package:** `tinycua.config.agents`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Overview

Each agent has a typed config dataclass extending `AgentConfigBase`. Configs hold all
overridable parameters (model, instructions, agent-specific knobs, extra tools).
The factory creates an AgentNode instance from its config and stores the config on
that node's `session.agent_state.agent_config`.

---

## `AgentConfigBase`

```text
AgentConfigBase (base configuration dataclass shared by all TinyCUA agents)
    · name: str — required, SDK Agent name
    · instructions: str — required, system prompt
    · model: LanguageModel — default TINYCUA_DEFAULT_MODEL
    · extra_tools: list[tinycua_sdk.Tool] — default [], external injection channel for tests/adapters
    · metadata: dict[str, Any] — default {}, free-form extensibility
    · compaction_strategy: BaseCompaction | None — default None, per-agent compaction; Session inherits via agent_state.agent_config
```

| Field | Purpose |
|-------|---------|
| `name` | SDK `Agent` name — set by concrete config default |
| `instructions` | System prompt — set by concrete config default |
| `model` | `LanguageModel` — defaults to `TINYCUA_DEFAULT_MODEL` |
| `extra_tools` | Externally injected tools — **empty by default**. Tests or integration adapters may use this to inject per-agent tools |
| `metadata` | Free-form dict for future extensibility |
| `compaction_strategy` | Per-agent compaction strategy (`BaseCompaction \| None`) — Session inherits via `agent_state.agent_config` |

---

## Per-Agent Configs

### `QueryAnalystConfig`

```text
QueryAnalystConfig extends AgentConfigBase
    · name = "query-analyst"
    · instructions = QUERY_ANALYST_INSTRUCTION
    · classification_labels: list[str] = TINYCUA_INPUT_GATE_CLASSIFICATION
    · hitl_enabled: bool = False
```

`classification_labels` makes QueryAnalyst reusable as the root TinyCUA input gate,
TinyCUAWorker input gate, or future decision gate. Root default is
`["passthrough", "worker"]`; worker overrides use
`TINYCUA_WORKER_INPUT_GATE_CLASSIFICATION`.

### `InformationDigesterConfig`

```text
InformationDigesterConfig extends AgentConfigBase
    · name = "information-digester"
    · instructions = INFORMATION_DIGESTER_INSTRUCTION
    · max_iterations_override: int | None = None  (None = no iteration limit)
```

### `TaskAnalyzerConfig`

```text
TaskAnalyzerConfig extends AgentConfigBase
    · name = "task-analyzer"
    · instructions = TASK_ANALYZER_INSTRUCTION
```

### `TaskAssessorConfig`

```text
TaskAssessorConfig extends AgentConfigBase
    · name = "task-assessor"
    · instructions = TASK_ASSESSOR_INSTRUCTION
```

### `TaskExecutorConfig`

```text
TaskExecutorConfig extends AgentConfigBase
    · name = "task-executor"
    · instructions = TASK_EXECUTOR_INSTRUCTION
```

### `ResultReviewerConfig`

```text
ResultReviewerConfig extends AgentConfigBase
    · name = "result-reviewer"
    · instructions = RESULT_REVIEWER_INSTRUCTION
    · deterministic_rules: list[DeterministicRule] — default [DEFAULT_SCHEMA_RULE, DEFAULT_FIELDS_RULE]
```

### `PrimaryAgentConfig`

```text
PrimaryAgentConfig extends AgentConfigBase
    · name = "primary-agent"
    · instructions = PRIMARY_AGENT_INSTRUCTION
```

### `TinyCUAConfig`

```text
OrchestrationSettings (standalone dataclass, not AgentConfigBase)
    · resume_enabled: bool = True
    · checkpoint_after_each_phase: bool = True

TinyCUAConfig (standalone dataclass, not AgentConfigBase)
    · name: str = "tinycua"
    · state_store: Any = None  (e.g., SQLiteStateStore)
    · artifact_store: Any = None  (e.g., FileSystemArtifactStore)
    · agent_node_overrides: dict[AgentKind, AgentConfigBase] = {}
    · orchestration: OrchestrationSettings — default OrchestrationSettings()
```

`TinyCUAConfig` intentionally has no `instructions`, `model`, or `extra_tools` for a
top-level SDK `Agent`: TinyCUA is a graph/orchestration runtime, not an agent wrapper.
Model and instruction settings belong to the AgentNode configs that TinyCUA routes to.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| One config per agent | Dataclass per agent kind | Typed, auto-completing; no dict-based config lookup |
| `extra_tools` in base | Shared field, empty default | Single injection channel for tests/adapters |
| `metadata: dict` in base | Free-form extensibility | Future fields can be promoted to typed fields without breaking the dict |
| `compaction_strategy` in base | `BaseCompaction \| None` on `AgentConfigBase` | Each agent can have its own compaction strategy; Session derives from `agent_state.agent_config` |
| `max_iterations_override` on InformationDigester | Agent-specific field | Only this agent has a meaningful iteration cap override |
| `deterministic_rules` on ResultReviewer | Agent-specific field | Only the review agent uses deterministic rules |


---


---


---

## See also

Prev : [Config Types — `AgentKind` enum, `TINYCUA_DEFAULT_MODEL`](types.md) | Next : [Pre-Configured Tool Sets (`*_BASE_TOOLS`)](../constants/tools.md)


## Related

- [AgentKind enum and TINYCUA_DEFAULT_MODEL](types.md)
- [*_BASE_TOOLS referenced in each config](../constants/tools.md)
- [*_INSTRUCTION constants used as defaults](../constants/instructions.md)
