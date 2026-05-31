# Design Document: Custom Loop Types (M2)

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-05-31

---

## Overview

Implement reusable custom agent loop strategies only where the default SDK loop is insufficient: Classification, Exploration, and Hybrid Review. Standard single-input/single-output agents such as Task Analyzer and Task Assessor use `tinycua_sdk.agent.loop.BaseLoop` directly through SDK `Agent.run()` rather than a custom Linear/Simple loop class. Custom loop strategies are built on top of `tinycua_sdk` (`BaseLoop`, `Agent`, `LLMClient`, `LanguageModel`, `Tool`) and add prompt structure, output schemas, and control-flow variants (iterative retrieval, two-phase review) while delegating LLM orchestration, tool execution, streaming, and cancellation to the SDK. M1 state objects are consumed as input and produced as output. The Agent Factory (M3) will map each agent either to a custom strategy or to direct SDK `BaseLoop` usage.

---

## Architecture

### Dependency: `tinycua_sdk`

All loop execution depends on `tinycua_sdk`. Custom loop strategies extend or compose with SDK primitives; standard agents use SDK `BaseLoop` directly. The SDK provides:

| SDK Component | Used For |
|---|---|
| `tinycua_sdk.agent.loop.BaseLoop` | Tool-calling execution loop, streaming, cancellation, message handling |
| `tinycua_sdk.agent.Agent` | LLM interaction, tool permissions, skills, policy |
| `tinycua_sdk.agent.llm_client.LLMClient` | Provider abstraction (OpenAI, etc.) |
| `tinycua_sdk.agent.llm_model.LanguageModel` | Model configuration (provider, api_key, model name) |
| `tinycua_sdk.tools.decorators.Tool` | Tool definition and schema enforcement |
| `tinycua_sdk.agent.executor.ToolExecutor` | Tool invocation and result normalization |

Custom loop strategies do NOT define their own LLM backend protocols, tool-calling infrastructure, retry logic, or streaming. They extend SDK classes and customize behavior through prompt design, output schemas, and control-flow hooks. Standard single-output agents do not need a custom loop strategy at all.

### Module Layout

```
src/tinycua/tinycua/
├── __init__.py
├── agent/
├── cli/
├── loops/                           # NEW
│   ├── __init__.py                  # Re-exports all loop types + SDK integration types
│   ├── classification.py            # ClassificationLoop (extends BaseLoop)
│   ├── exploration.py               # ExplorationLoop (extends BaseLoop)
│   ├── hybrid_review.py             # HybridReviewLoop (extends BaseLoop)
│   ├── schema_validator.py          # Output validation (uses SDK event/model infra)
│   └── errors.py                    # LoopError hierarchy (thin wrappers around SDK errors)
├── state/                           # M1 (existing)
│   └── ...
└── ...
```

**Note**: There is no `base.py` with custom `LoopBase`, `LLMBackend`, or `ToolDef` classes. There is also no `linear.py` / `LinearAgentLoop` / `SimpleLoop` wrapper. The canonical base class is `tinycua_sdk.agent.loop.BaseLoop`. The canonical tool infrastructure is `tinycua_sdk.tools.decorators.Tool` and `tinycua_sdk.agent.executor.ToolExecutor`. Standard single-input/single-output agents use SDK `BaseLoop` directly.

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/` | New | Custom loop strategies extending `tinycua_sdk.agent.loop.BaseLoop`; no custom wrapper for direct BaseLoop use |
| `tinycua/state/` | Unchanged | Loops consume M1 state objects as input/output |
| `tinycua/__init__.py` | Modified | May re-export `tinycua.loops` submodule |
| `tinycua_sdk` | **No changes** | Used as-is; custom loops extend SDK classes, do not modify SDK |

---

## Loop Architecture

### Uniform Interface (SDK Integration)

Custom loop strategies extend `tinycua_sdk.agent.loop.BaseLoop` and integrate with `tinycua_sdk.agent.Agent`. Standard single-input/single-output agents use SDK `BaseLoop` directly without an additional custom loop class:

```python
from tinycua_sdk.agent.loop import BaseLoop
from tinycua_sdk.agent import Agent
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.tools.decorators import Tool


class ClassificationLoop(BaseLoop):
    """Single-pass classification using SDK's BaseLoop + Agent."""

    def __init__(
        self,
        agent: Agent,            # SDK Agent configured with LanguageModel + system prompt
        max_iterations: int = 1, # Single pass for classification
    ):
        super().__init__(max_iterations=max_iterations)
        self._agent = agent

    async def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]:
        """Execute the classification loop via SDK's BaseLoop.run()."""
        return await super().run(agent, messages, tools, override_instructions, stream)
```

**Design principle**: Custom loop types are thin strategies used only when behavior differs from the SDK default. The SDK's `BaseLoop.run()` handles tool calling, message management, streaming, and cancellation. Custom loops override or wrap `run()` to add domain-specific control flow (e.g., iterative gap checking, deterministic pre-checks). If an agent only needs a normal single invocation with optional tool-calling iteration, it uses `BaseLoop` directly.

### Loop Input/Output

Input and output follow M1 state object schemas. Each loop type documents which fields it requires:

| Execution Strategy | Input (M1 type or dict) | Output (M1 type or dict) |
|--------------------|------------------------|-------------------------|
| Classification custom loop | `{user_query, chat_history, session_context}` | `{context_enhanced_query, mode_decision}` |
| Exploration custom loop | `{context_enhanced_query}` | `{context_summary, key_points, known_gaps, ...}` |
| Direct SDK `BaseLoop` | Agent-specific schema (e.g., `DigestedInformation`) | Agent-specific schema (e.g., `Task` tree) |
| Hybrid Review custom loop | `{task, task_result, execution_log}` | `{status, reason, confidence, ...}` |

### Output Validation (SchemaValidator)

```python
class SchemaValidator:
    """Validates structured LLM output against type schemas.

    Uses the SDK's event/model infrastructure for parsing and retry.
    Does NOT implement its own LLM calling or retry logic — it wraps
    an SDK Agent.run() call and validates the result.
    """

    def __init__(
        self,
        validation_fn: Callable[[dict], tuple[bool, str | None]],
        max_validation_retries: int = 2,
    ): ...

    async def validate(
        self,
        agent: Agent,
        messages: list[dict],
        system_prompt: str,
        tools: list[Tool] | None = None,
    ) -> dict[str, Any]:
        """Run Agent, validate output, retry with error context on failure."""
        ...
```

### Flow Diagram

```
               ┌──────────────────────────────────────────┐
               │              Agent Factory (M3)           │
               │  select_loop(agent_type) → BaseLoop       │
               └────────────┬─────────────────────────────┘
                            │
                            ▼
    ┌───────────────────────────────────────────────────────────────┐
    │                    tinycua_sdk.agent.loop.BaseLoop             │
    │  ┌─────────────────────────────────────────────────────────┐  │
    │  │  Custom Loop Strategy (extends BaseLoop)                 │  │
    │  │  ┌───────────────────┐  ┌────────────────────────────┐  │  │
    │  │  │  Loop-specific     │  │  SchemaValidator           │  │  │
    │  │  │  control flow      │  │  (output validation        │  │  │
    │  │  │  (see sections     │  │   + retry via Agent)       │  │  │
    │  │  │   below)           │  │                            │  │  │
    │  │  └─────────┬─────────┘  └────────────┬───────────────┘  │  │
    │  │            │                         │                   │  │
    │  │  ┌─────────▼─────────────────────────▼───────────────┐  │  │
    │  │  │  SDK Agent.run() → LLMClient.chat()               │  │  │
    │  │  │  (tool execution, streaming, cancellation)        │  │  │
    │  │  └───────────────────────────────────────────────────┘  │  │
    │  └─────────────────────────────────────────────────────────┘  │
    └───────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  Typed state object output
```

### Error Handling (via SDK)

Custom loops do not implement their own retry logic. They rely on the SDK's infrastructure:

| Error Case | SDK Behavior | Loop Type Responsibility |
|------------|-------------|-------------------------|
| Transient LLM error (rate limit, timeout) | SDK's `LLMClient` handles retry/backoff | Propagate as `LoopTransientError` if SDK exhausts retries |
| Permanent LLM error (auth, bad request) | SDK raises immediately | Propagate as `LoopPermanentError` |
| Output validation failure | SchemaValidator retries Agent.run() with error context | Raise `LoopOutputValidationError` after max validation retries |
| Invalid input | — | Raise `ValueError` before any LLM call |
| Tool call failure | SDK's `ToolExecutor` returns error as observation | LLM decides next action |
| Missing required tool | — | Raise `LoopPermanentError` at construction |

---

## Loop Type Designs

### 1. Classification Loop

**Architecture reference**: `query-analyst.md`, `task-classification.md`

**Purpose**: High-level context scan → multi-dimensional scoring → ModeDecision.

**SDK integration**: Extends `BaseLoop` with `max_iterations=1`. Configures an SDK `Agent` with a structured classification system prompt and no tools. The SDK's `BaseLoop.run()` handles the single LLM call, message construction, and response parsing.

**Implementation approach**:
1. Constructor receives an SDK `Agent` pre-configured with the classification system prompt and output schema.
2. `run()` constructs the user message from `user_query + chat_history + session_context`.
3. Delegates to `BaseLoop.run()` for the LLM call.
4. SchemaValidator validates the parsed JSON against the classification schema.
5. Returns `{context_enhanced_query, mode_decision}`.

**No tools**: The Classification loop (Query Analyst) does not use tools. The SDK `Agent` is configured with an empty tools list.

**Key design decisions**:
- Single LLM call (not iterative) — Query Analyst is designed to be fast, not deep.
- Scoring is embedded in the LLM prompt as a rubric.
- Uses SDK's `BaseLoop` for message handling and LLM orchestration — no custom LLM calling.

### 2. Exploration Loop

**Architecture reference**: `information-digestion.md`, `context-retrieval.md`

**Purpose**: Iterative gap identification + retrieval → DigestedInformation.

**SDK integration**: Extends `BaseLoop`. Configures an SDK `Agent` with an `enhanced_context_retrieval` SDK `Tool`. The SDK's `BaseLoop` handles the tool-calling iteration (LLM requests tool → tool executes → result returned → LLM evaluates). The Exploration loop adds gap-evaluation logic on top.

**Internal flow**:

```
┌──────────────┐   ┌──────────────┐   ┌───────────────┐   ┌───────────────┐
│  Input: CEQ  │──▶▶  SDK Agent   │──▶▶  Enhanced     │──▶▶  Extract &    │
│  caller info │   │  identifies  │   │  Context      │   │  evaluate     │
│              │   │  gaps (LLM)  │   │  Retrieval    │   │  (LLM)        │
└──────────────┘   └──────────────┘   │  (SDK Tool)   │   └───────┬───────┘
                                      └──────────────┘           │
                                          ▲        │              │
                                          │        ▼              │
                                          │  ┌──────────────┐    │
                                          │  │  Gaps        │    │
                                          └──│  addressed?  │◀───┘
                                              │  (LLM-judged)│
                                              └──────┬───────┘
                                                     │ No → loop back
                                                     ▼ Yes
                                              ┌──────────────┐
                                              │  Structure   │
                                              │  & output    │
                                              │  (LLM)       │
                                              └──────┬───────┘
                                                     ▼
                                              ┌──────────────┐
                                              │  Output:     │
                                              │  Digested    │
                                              │  Information │
                                              └──────────────┘
```

**Implementation approach**:
1. Constructor receives an SDK `Agent` with `enhanced_context_retrieval` SDK `Tool` registered.
2. `run()` overrides `BaseLoop.run()` to add gap-evaluation between SDK iterations:
   a. SDK `BaseLoop` handles the tool-calling iteration (LLM → tool → observe → repeat).
   b. After each SDK iteration, the loop checks if the LLM's output indicates gaps are addressed.
   c. If gaps remain AND `max_iterations` not reached → continue with accumulated context.
   d. If gaps addressed or max reached → validate and return `DigestedInformation`.

**Tools required**: `enhanced_context_retrieval` SDK `Tool` — searches Session Context.

**Stop conditions**: LLM-judged sufficiency (via output parsing) OR SDK's `BaseLoop.max_iterations` (configurable, default 5).

### 3. Direct SDK BaseLoop Usage (Task Analyzer / Task Assessor)

**Architecture reference**: `task-analysis.md` (Task Analyzer), `task-assessor.md` (Task Assessor)

**Purpose**: Single input → single output with SDK-provided ReAct/tool-calling internal iteration but no custom routing branches, exploration phase, or deterministic review phase.

**SDK integration**: Use `tinycua_sdk.agent.loop.BaseLoop` directly through `Agent.run()`. Configure the agent with a system prompt, optional output schema validation, and optional SDK `Tool` objects. The SDK's `BaseLoop` provides the `think → act → observe → repeat` iteration. A separate `LinearAgentLoop`, `SimpleLoop`, or equivalent wrapper is intentionally not created.

**Implementation approach**:
- Agent Factory creates an SDK `Agent` pre-configured with the agent-specific system prompt, `LanguageModel`, optional SDK `Tool` objects, and default `BaseLoop`.
- The caller invokes `Agent.run()` directly.
- SchemaValidator (or an equivalent output-validation layer) validates the returned content against the agent's schema.
- No custom loop class is introduced for this execution pattern.

**Configuration**:
```python
from tinycua_sdk.agent import Agent
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.tools.decorators import Tool

agent = Agent(
    name="task-analyzer",
    instructions="<agent-specific system prompt>",
    llm_model=LanguageModel(provider="openai", model="gpt-4o"),
    tools=[...],  # Optional: SDK Tool objects
    # loop omitted → Agent.run() uses SDK BaseLoop()
)
raw_result = await agent.run(query="<serialized DigestedInformation>")
result = await schema_validator.validate_output(raw_result, output_schema=Task)
```

**Key distinction from Exploration/Review loops**:
- No gap-iteration control (unlike Exploration) — SDK's `BaseLoop` handles tool iteration.
- No branching decisions (unlike Hybrid Review) — the agent produces exactly one output.
- One input, one output — the agent may think internally via SDK's ReAct/tool loop but produces a single definitive result after validation.
- No `tinycua.loops.linear` module and no custom `LinearAgentLoop` type.

### 4. Hybrid Review Loop

**Architecture reference**: `result-reviewer.md`

**Purpose**: Two-phase review: deterministic checks first, then LLM semantic review via SDK `Agent.run()` → ReviewerDecision.

**SDK integration**: Extends `BaseLoop`. Phase 1 runs custom deterministic rules (no SDK involvement). Phase 2 delegates to SDK `Agent.run()` for LLM semantic review. The SDK handles message construction, LLM calling, and response parsing.

**Internal flow**:

```
┌──────────────┐   ┌────────────────────┐   ┌─────────────────┐   ┌──────────────┐
│  Input:      │──▶▶  Phase 1:          │──▶▶  Phase 2:       │──▶▶  Output:      │
│  TaskResult  │   │  Deterministic     │   │  SDK Agent.run()│   │  Reviewer     │
│  Task        │   │  checks            │   │  (LLM Semantic  │   │  Decision     │
│  ExecLog     │   │  (custom rules)    │   │   Review)       │   │              │
│              │   │                    │   │                 │   │              │
│              │   │  • schema validity │   │  • correctness  │   │              │
│              │   │  • missing fields  │   │  • sufficiency  │   │              │
│              │   │  • required struct │   │  • recovery     │   │              │
│              │   │                    │   │  • context      │   │              │
│              │   └─────────┬──────────┘   │    propagation  │   │              │
│              │             │              └────────┬────────┘   └──────────────┘
│              │             ▼                       │
│              │      ╔══════════════╗               │
│              │      ║  Fail →      ║               │
│              │      ║  escalate or ║               │
│              │      ║  replan      ║               │
│              │      ╚══════════════╝               │
│              │                                     │
│              │        Phase 2 determines:          │
│              │        accept / retry / replan /    │
│              │        escalate_user                │
└──────────────┘                                     │
                                                     ▼
                                              ┌──────────────┐
                                              │  Output:     │
                                              │  Reviewer    │
                                              │  Decision    │
                                              └──────────────┘
```

**Implementation approach**:
1. Constructor receives an SDK `Agent` (for Phase 2) and a list of `DeterministicRule` objects (for Phase 1).
2. `run()`:
   a. **Phase 1**: Evaluate all deterministic rules. If any rule fails with severity `escalate` or `replan`, skip Phase 2 and return the deterministic result immediately.
   b. **Phase 2**: If Phase 1 passes, delegate to SDK `Agent.run()` with the review system prompt and input context. The LLM evaluates semantic quality and produces one of four statuses.
3. For `accepted`: LLM must also compute `context_updates`.
4. For `retry`: LLM must include `retry_instructions`.
5. For `replan`: LLM must include rationale.
6. For `escalate_user`: LLM must include user-facing explanation.

**Deterministic check rules** (pluggable at construction):

```python
@dataclass
class DeterministicRule:
    name: str
    check: Callable[[dict, dict, dict], DeterministicRuleResult]

@dataclass
class DeterministicRuleResult:
    passed: bool
    reason: str | None = None
    severity: str | None = None  # "escalate" | "replan"

loop = HybridReviewLoop(
    agent=review_agent,  # SDK Agent for Phase 2
    deterministic_rules=[
        DeterministicRule(name="SchemaValidity", check=check_schema),
        DeterministicRule(name="RequiredFields", check=check_fields),
    ],
)
```

---

## Data Model

### SDK Types (Provided by `tinycua_sdk` — NOT redefined)

The following types are imported from `tinycua_sdk`, not redefined:

```python
from tinycua_sdk.agent.loop import BaseLoop         # Base class for all loops
from tinycua_sdk.agent import Agent                  # Agent with LLM, tools, skills
from tinycua_sdk.agent.llm_client import LLMClient    # Provider abstraction
from tinycua_sdk.agent.llm_model import LanguageModel # Model configuration
from tinycua_sdk.tools.decorators import Tool         # Tool definition + schema
```

### Custom Types (Defined by `tinycua.loops`)

Only types specific to the domain logic are defined:

```python
from enum import Enum

class LoopType(str, Enum):
    """Execution strategy identifiers for Agent Factory."""
    SDK_BASE = "sdk_base"  # Direct tinycua_sdk BaseLoop; no custom loop class
    CLASSIFICATION = "classification"
    EXPLORATION = "exploration"
    HYBRID_REVIEW = "hybrid_review"


@dataclass
class DeterministicRule:
    """A pluggable deterministic check rule (Hybrid Review Loop only)."""
    name: str
    check: Callable[..., DeterministicRuleResult]


@dataclass
class DeterministicRuleResult:
    """Result of a deterministic check."""
    passed: bool
    reason: str | None = None
    severity: str | None = None  # "escalate" | "replan"
```

### Loop Errors (thin wrappers around SDK exceptions)

```python
class LoopError(Exception):
    """Base class for all loop errors."""

class LoopTransientError(LoopError):
    """Transient failure — caller may retry."""

class LoopPermanentError(LoopError):
    """Permanent failure — caller should not retry."""

class LoopOutputValidationError(LoopError):
    """Output failed validation after all retries exhausted."""
```

---

## API / Interface Contracts

### Public API: `tinycua.loops` package

```python
# SDK types (re-exported for convenience)
from tinycua_sdk.agent.loop import BaseLoop
from tinycua_sdk.agent import Agent
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.tools.decorators import Tool

# Custom loop types
from tinycua.loops import (
    # Loop implementations (extend BaseLoop)
    ClassificationLoop,
    ExplorationLoop,
    HybridReviewLoop,
    # Validation
    SchemaValidator,
    # Hybrid Review types
    DeterministicRule,
    DeterministicRuleResult,
    # Enum
    LoopType,
    # Errors
    LoopError,
    LoopTransientError,
    LoopPermanentError,
    LoopOutputValidationError,
)
```

### Loop type → Agent mapping (for Agent Factory)

| Execution Strategy | Agents Using It | SDK Agent Config | Input Type | Output Type |
|--------------------|----------------|-----------------|------------|-------------|
| Custom Classification loop | Query Analyst | System prompt + no tools | `{user_query, chat_history, context}` | `{context_enhanced_query, mode_decision}` |
| Custom Exploration loop | Information Digester | System prompt + `enhanced_context_retrieval` SDK Tool | `ContextEnhancedQuery` | `DigestedInformation` |
| Direct SDK `BaseLoop` | Task Analyzer | Task analysis prompt + optional tools + schema validation | `DigestedInformation` | `Task` tree |
| Direct SDK `BaseLoop` | Task Assessor | Assessment prompt + optional tools + schema validation | `Task` tree + `WorkerConfig` | `list[task_id]` selection |
| Custom Hybrid Review loop | Result Reviewer | Review prompt + pluggable deterministic rules | `{task, task_result, execution_log}` | `ReviewerDecision` |

---

## Future Architecture Documentation Sync

This PR is spec/design-only and should not edit `src/tinycua/docs/architecture/` yet. During implementation, the architecture docs should be synchronized with this design:

| Architecture Doc | Future Change |
|------------------|---------------|
| `overview.md` | Update the Agent Loop Types table so Task Analyzer and Task Assessor are mapped to direct SDK `BaseLoop` usage instead of a separate input→output / Linear / Simple loop type. |
| `task-analysis.md` | Clarify that Task Analyzer is an SDK `Agent` using default SDK `BaseLoop`; any single-output guarantee comes from prompt/schema validation around `Agent.run()`. |
| `task-assessor.md` | Clarify that Task Assessor is an SDK `Agent` using default SDK `BaseLoop`; decomposition-selection output is schema-validated outside the loop. |
| Any architecture docs mentioning "Linear", "Simple", or "input→output" loop semantics | Normalize wording to distinguish direct SDK `BaseLoop` usage from true custom loop strategies. |

The implementation phase should include an architecture-doc synchronization task after the SDK-integrated loop design is finalized.

---

## Implementation Phases

### Phase 1 — SDK Integration Foundation

- [ ] Verify `tinycua-sdk` dependency is available and properly configured in `pyproject.toml`
- [ ] Create `tinycua/loops/errors.py` with error hierarchy (thin wrappers)
- [ ] Create `tinycua/loops/schema_validator.py` that wraps SDK `Agent.run()` with output validation and retry
- [ ] Create `tinycua/loops/__init__.py` re-exporting SDK types and custom loop types

### Phase 2 — Classification Loop

- [ ] Implement `tinycua/loops/classification.py` extending `BaseLoop`, configuring SDK `Agent` with classification prompt
- [ ] Write unit tests using mock SDK `Agent`: valid outputs for all three modes, anti-laziness safeguards, edge cases

### Phase 3 — Exploration Loop

- [ ] Implement `tinycua/loops/exploration.py` extending `BaseLoop`, adding gap-evaluation between SDK iterations
- [ ] Define Enhanced Context Retrieval as an SDK `Tool` (full implementation in M6; stub for now)
- [ ] Write unit tests using mock SDK `Agent`: multi-iteration retrieval, stop on sufficiency, empty results → known_gaps

### Phase 4 — Direct SDK BaseLoop Mapping

- [ ] Configure Agent Factory mapping so Task Analyzer and Task Assessor use SDK `BaseLoop` directly (no `tinycua/loops/linear.py`)
- [ ] Add output schema validation tests for Task Analyzer and Task Assessor around SDK `Agent.run()`
- [ ] Verify optional SDK `Tool` usage and pure-reasoning behavior through SDK `BaseLoop`

### Phase 5 — Hybrid Review Loop

- [ ] Implement `tinycua/loops/hybrid_review.py` with two-phase execution: deterministic rules + SDK `Agent.run()`
- [ ] Write unit tests using mock SDK `Agent`: all four statuses, deterministic failure overrides LLM, context_updates on accept

### Phase 6 — Integration & Documentation

- [ ] Integration tests: end-to-end with mock SDK `Agent` for each loop type
- [ ] Docstrings and usage examples for all loop types
- [ ] Sync architecture docs listed in **Future Architecture Documentation Sync**
- [ ] Verify all loops integrate correctly with SDK's `BaseLoop.run()` interface
- [ ] Verify all M1 state types are properly consumed and produced

---

## Technical Decisions

0. **Decision**: Custom loop strategies MUST extend or compose with `tinycua_sdk.agent.loop.BaseLoop` and use `tinycua_sdk.agent.Agent` for LLM interaction. Standard single-input/single-output agents MUST use SDK `BaseLoop` directly. No custom LLM backend protocols, tool-calling infrastructure, or streaming logic.
   - **Reason**: The SDK already provides a mature, tested execution infrastructure (`BaseLoop`, `Agent`, `LLMClient`, `Tool`, `ToolExecutor`). Redefining these in `tinycua.loops` would create a parallel, incompatible infrastructure that cannot integrate with the rest of the TINYCUA system (Agent Factory, tool registry, M4 agents). Custom loop strategies are only needed where domain control flow differs from SDK default behavior — prompt design, output schemas, iterative retrieval, or deterministic pre-checks.
   - **Alternatives Considered**: Standalone loops with custom `LLMBackend` Protocol and `ToolDef` dataclass — rejected because they bypass the SDK's tool execution, streaming, cancellation, and event system, creating two incompatible execution paths. A custom Linear/Simple loop wrapper — rejected because SDK `BaseLoop` already represents that execution pattern.

1. **Decision**: Uniform execution uses SDK `BaseLoop` rather than custom per-loop interfaces.
   - **Reason**: Agent Factory needs to treat custom strategies and standard agents consistently. The SDK's `BaseLoop.run()` already provides a uniform signature. Custom loops extend this without changing the interface contract; standard agents use it directly.
   - **Alternatives Considered**: Custom `LoopBase` with `LLMBackend` Protocol — rejected per Decision #0.

2. **Decision**: Single LLM call for Classification loop rather than iterative scoring.
   - **Reason**: Query Analyst is designed for speed. Multi-dimensional scoring is embedded in the prompt as a single reasoning step. SDK's `BaseLoop` with `max_iterations=1` enforces single-pass.
   - **Alternatives Considered**: Separate scoring and CEQ generation calls — adds latency with no architectural benefit.

3. **Decision**: Pluggable deterministic rules for Hybrid Review loop rather than hardcoded checks.
   - **Reason**: Different agents may need different deterministic validations. Defaults provided (SchemaValidity, RequiredFields) but extensible by Agent Factory.
   - **Alternatives Considered**: Hardcoded checks — simpler but less extensible.

4. **Decision**: SchemaValidator wraps SDK `Agent.run()` rather than implementing standalone LLM calling with retry.
   - **Reason**: The SDK already handles LLM calling, retry, and error handling. SchemaValidator adds output validation and retry-with-error-context on top, without duplicating LLM infrastructure.
   - **Alternatives Considered**: Standalone LLM calling with custom retry — rejected per Decision #0.

5. **Decision**: Both LLM-judged and SDK `max_iterations`-based stop conditions for Exploration loop.
   - **Reason**: LLM judging sufficiency is context-aware. The SDK's `BaseLoop.max_iterations` provides a hard cap. Combined, they prevent both premature stops and infinite loops.
   - **Alternatives Considered**: Count-only — ignores whether gaps are addressed. LLM-only — risk of infinite loop.

6. **Decision**: Do not implement a custom Linear/Simple loop type; use SDK `BaseLoop` directly for Task Analyzer, Task Assessor, and similar agents.
   - **Reason**: The SDK already implements the needed default ReAct/tool-calling behavior (think → tool call → observe → repeat). The only additional requirement for these agents is a single structured output, which can be enforced by prompt design and output validation around `Agent.run()`.
   - **Alternatives Considered**: Custom Linear/Simple wrapper — rejected because it adds naming confusion and duplicates SDK behavior without adding control-flow semantics. Custom ReAct loop — rejected because it cannot integrate as cleanly with SDK's `Tool`, `ToolExecutor`, streaming, or cancellation.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LLM output parsing failures with real models | Medium | High | SchemaValidator retries via SDK Agent with error context. Lower retry threshold surfaces failures early. |
| Exploration loop infinite retrieval | Low | Medium | SDK's `BaseLoop.max_iterations` prevents infinite loops. Configurable at construction. |
| Hybrid Review deterministic/LLM conflict | Low | Medium | Deterministic checks win — if they fail, Phase 2 (SDK Agent) is skipped entirely. |
| Direct SDK BaseLoop misused for branching agents | Low | Low | Documented per agent which execution strategy to use. Agent Factory maps only standard single-output agents to direct SDK `BaseLoop`; specialized branching/exploration/review agents use custom strategies. |
| SDK version incompatibility | Low | Medium | `tinycua` depends on `tinycua-sdk>=0.1.0` via workspace. SDK breaking changes require coordinated updates. |
| SDK BaseLoop interface changes | Low | Medium | Custom loops extend BaseLoop — SDK interface changes may require loop updates. Mitigated by workspace dependency pinning. |

---

## References

- Spec: `./spec.md`
- SDK `BaseLoop`: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- SDK `Agent`: `src/tinycua-sdk/tinycua_sdk/agent/agent.py`
- SDK `LLMClient`: `src/tinycua-sdk/tinycua_sdk/agent/llm_client.py`
- SDK `Tool`: `src/tinycua-sdk/tinycua_sdk/tools/decorators.py`
- Architecture overview: `src/tinycua/docs/architecture/overview.md` (Agent Loop Types table)
- Query Analyst spec: `src/tinycua/docs/architecture/query-analyst.md`
- Task Classification: `src/tinycua/docs/architecture/task-classification.md`
- Information Digestion: `src/tinycua/docs/architecture/information-digestion.md`
- Task Analysis: `src/tinycua/docs/architecture/task-analysis.md`
- Task Assessor: `src/tinycua/docs/architecture/task-assessor.md`
- Result Reviewer: `src/tinycua/docs/architecture/result-reviewer.md`
- State Objects (M1): `src/tinycua/docs/architecture/state-objects.md`
