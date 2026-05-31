# Design Document: Agent + Loop Integration (M2)

**Spec**: ./spec.md
**Detailed designs**: `src/tinycua/docs/design/`
**Status**: Draft
**Last Updated**: 2026-05-31

---

## Overview

Implement M2 as an integrated Agent + Loop milestone. Custom loop strategies, agent wrapper classes, system prompts, and agent-to-agent calling tools are designed together because the SDK execution model is `Agent(loop=CustomLoop(), ...)` — loops are configuration on SDK agents, not wrappers around agents.

Internal TinyCUA agents are **wrapper classes** (e.g., `QueryAnalyst`, `TaskExecutor`) that compose (not extend) an SDK `Agent` internally. The wrapper owns the configured agent, a typed `StateInformation` instance, and domain-specific methods (`run()`, `save_state()`, `restore_state()`). Loops stay focused on low-level execution; wrappers handle pre-processing, post-processing, validation, and context management.

### Resolved Strategy Choices

- Standard single-input/single-output agents use `ReActAgentLoop` (shared, extends SDK `BaseLoop`)
- Custom loops (`QueryAnalystLoop`, `InformationDigestionLoop`, `ResultReviewLoop`) extend SDK `BaseLoop` directly
- Classification uses SDK `BaseLoop` default iteration — no `max_iterations=1`
- Exploration stops on LLM-judged sufficiency with `BaseLoop.max_iterations` hard cap
- Hybrid Review deterministic checks are pluggable rules at construction
- Former roadmap M2/M3/M4/M5/M7 collapsed into one milestone
- Final product: `TinyCUA` wrapper class composing SDK `Agent` with `MainLoop`

For detailed design documentation, see:

| Document | Content |
|----------|---------|
| [`docs/design/README.md`](src/tinycua/docs/design/README.md) | Reading order and index |
| [`docs/design/overview.md`](src/tinycua/docs/design/overview.md) | Project structure, module layout, layer separation, tool sources |
| [`docs/design/base-agent-wrapper.md`](src/tinycua/docs/design/base-agent-wrapper.md) | `BaseAgentWrapper[S]`, `StateInformation` ABC + subclasses |
| [`docs/design/loop-strategies.md`](src/tinycua/docs/design/loop-strategies.md) | All loop types |
| Per-agent docs | `query-analyst.md`, `information-digester.md`, `task-analyzer.md`, `task-assessor.md`, `task-executor.md`, `result-reviewer.md`, `primary-agent.md` |
| [`docs/design/agent-calls.md`](src/tinycua/docs/design/agent-calls.md) | Agent-to-agent calling tools |
| [`docs/design/tinycua-agent.md`](src/tinycua/docs/design/tinycua-agent.md) | `TinyCUA` external wrapper and `MainLoop` contract |

---

## Architecture

### Dependency: `tinycua_sdk`

All loop execution depends on `tinycua_sdk`. Custom loop strategies extend SDK primitives; standard agents use `ReActAgentLoop` (thin `BaseLoop` wrapper).

| SDK Component | Used For |
|---|---|
| `BaseLoop` | Tool-calling execution loop, streaming, cancellation |
| `Agent` | LLM interaction, tool permissions, policy |
| `LLMClient` | Provider abstraction |
| `LanguageModel` | Model configuration |
| `Tool` | Tool definition and schema enforcement |
| `ToolExecutor` | Tool invocation and result normalization |

Custom loop strategies do NOT define their own LLM backend protocols, tool-calling infrastructure, retry logic, or streaming.

### TinyCUA Default Model

```python
TINYCUA_DEFAULT_MODEL = LanguageModel(
    provider="openai-chat-completions",
    model_name="qwen/qwen3.5-4b",
    base_url="http://localhost:1234/v1",
)
```

Defined in `tinycua.config.types`. Use canonical provider `openai-chat-completions` — NOT alias `openai`.

---

## Loop Architecture

### Loop Hierarchy

```
SDK BaseLoop
├── ReActAgentLoop           (shared — TaskAnalyzer, TaskAssessor, TaskExecutor, PrimaryAgent)
├── QueryAnalystLoop         (classification control flow)
├── InformationDigestionLoop (iterative retrieval + gap evaluation)
├── ResultReviewLoop         (two-phase: deterministic + LLM review)
└── MainLoop                 (FUTURE M6 — full orchestration)
```

### Custom Loops

Loops extend `BaseLoop.run()` and are attached to the composed SDK agent inside the wrapper via `Agent(loop=...)`. Details in [`docs/design/loop-strategies.md`](src/tinycua/docs/design/loop-strategies.md).

### Output Validation

`SchemaValidator` wraps SDK `Agent.run()` with output validation and retry. On validation failure, retries the agent with error context; raises `LoopOutputValidationError` after max retries exhausted.

### Error Handling

Loops rely on SDK infrastructure:

| Error Case | SDK Behavior | Loop Responsibility |
|------------|-------------|---------------------|
| Transient LLM error | `LLMClient` retry/backoff | Propagate as `LoopTransientError` |
| Permanent LLM error | SDK raises immediately | Propagate as `LoopPermanentError` |
| Output validation failure | `SchemaValidator` retries | Raise `LoopOutputValidationError` |
| Invalid input | — | Raise `ValueError` before LLM call |

---

## Agent Wrapper Architecture

Every architecture agent is a typed wrapper class extending `BaseAgentWrapper[S]`. Wrappers compose an SDK `Agent` internally; the agent is not publicly exposed.

### Tool Sources

Every agent's `_build_agent()` merges exactly two tool sources:

```python
self.agent = Agent(
    tools=[*QUERY_ANALYST_BASE_TOOLS, *self.config.extra_tools],
    loop=QueryAnalystLoop(),
)
```

| Source | Location | Purpose |
|--------|----------|---------|
| `*_BASE_TOOLS` | `tinycua.constants.tools` | Pre-configured tool set (code-level constant) |
| `config.extra_tools` | Agent config dataclass | Externally injected — **empty by default** |

### Agent Loop Mapping

| Agent | Loop | Extends | Custom Behavior |
|-------|------|---------|-----------------|
| QueryAnalyst | `QueryAnalystLoop` | `BaseLoop` | Classification |
| InformationDigester | `InformationDigestionLoop` | `BaseLoop` | Iterative retrieval |
| TaskAnalyzer | `ReActAgentLoop` | `BaseLoop` | (none) |
| TaskAssessor | `ReActAgentLoop` | `BaseLoop` | (none) |
| TaskExecutor | `ReActAgentLoop` | `BaseLoop` | (none) |
| ResultReviewer | `ResultReviewLoop` | `BaseLoop` | Two-phase review |
| PrimaryAgent | `ReActAgentLoop` | `BaseLoop` | (none) |

---

## Data Model

### SDK Types (imported, NOT redefined)

`BaseLoop`, `Agent`, `LLMClient`, `LanguageModel`, `Tool` from `tinycua_sdk`.

### Custom Types

- **Loop errors**: `LoopError`, `LoopTransientError`, `LoopPermanentError`, `LoopOutputValidationError`
- **Hybrid Review**: `DeterministicRule`, `DeterministicRuleResult`
- **Enum**: `LoopType` (`REACT`, `QUERY_ANALYST`, `INFORMATION_DIGESTION`, `RESULT_REVIEW`)

---

## Future Documentation Sync

During implementation, synchronize:
- Architecture docs: update loop type references (`overview.md`, `task-analysis.md`, `task-assessor.md`)
- SDK cookbook: correct `custom-execution-loops.md` to show `Agent(loop=...)`

See spec.md Future Documentation Sync sections for full list.

---

## References

- Spec: `./spec.md`
- Design docs: `src/tinycua/docs/design/`
- Architecture docs: `src/tinycua/docs/architecture/`
- SDK `BaseLoop`: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- SDK `Agent`: `src/tinycua-sdk/tinycua_sdk/agent/agent.py`
