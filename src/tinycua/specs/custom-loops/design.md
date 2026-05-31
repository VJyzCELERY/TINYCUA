# Design Document: Agent + Loop Integration (M2)

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-05-31

---

## Overview

Implement M2 as an integrated Agent + Loop milestone. Custom loop strategies, agent factory/configuration, system prompts, concrete agent definitions, and agent-to-agent calling tools are designed together because the SDK execution model is `Agent(loop=CustomLoop(), ...)`: loops are configuration on SDK agents, not wrappers around agents. Custom loop strategies are used only where the default SDK loop is insufficient: Classification, Exploration, and Hybrid Review. Standard single-input/single-output agents use `tinycua_sdk.agent.loop.BaseLoop` directly through SDK `Agent.run()` rather than a custom Linear/Simple loop class. All strategies are built on top of `tinycua_sdk` (`Agent`, `BaseLoop`, `LLMClient`, `LanguageModel`, `Tool`) and delegate LLM orchestration, tool execution, streaming, and cancellation to the SDK. M1 state objects are consumed as input and produced as output.

Resolved strategy choices are part of this design, not open questions:

- Standard single-input/single-output agents use SDK `BaseLoop` directly; no custom Linear/Simple loop wrapper is introduced.
- Custom loops are passed into SDK agents through `Agent(loop=CustomLoop(), ...)`; custom loops do not own or wrap `Agent` instances.
- Classification produces one structured classification result but does not enforce a true one-iteration/single-pass loop; it uses SDK `BaseLoop` default iteration behavior so the agent is not forced to stop immediately.
- Exploration stops when the LLM judges retrieved context sufficient, with `BaseLoop.max_iterations` as a hard safety cap.
- Hybrid Review deterministic checks are pluggable rules registered at construction time, not hardcoded checks inside the loop.
- Former roadmap M2/M3/M4/M5/M7 scope is collapsed into this M2 because loop selection, agent creation, prompts, and agent-calling tools must be tested in tandem.
- The final product exposes one external TINYCUA SDK agent: `Agent(loop=MainLoop(), metadata={...})`. M2 does not implement executable `MainLoop`, but it defines the metadata/configuration contract MainLoop will consume.

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

Custom loop strategies do NOT define their own LLM backend protocols, tool-calling infrastructure, retry logic, or streaming. They extend SDK classes and customize behavior through prompt design, output schemas, and control-flow hooks. Standard single-output agents do not need a custom loop strategy at all. Agent creation is centralized in the M2 factory/config registry, which constructs SDK `Agent` objects with the correct `loop`, prompt, tools, model, policy, and output validator.

### TinyCUA Default Model Configuration

TinyCUA's default model configuration is intentionally defined by this project,
not inherited from the SDK's default `LanguageModel()`. The default for all
TinyCUA agents is:

```python
TINYCUA_DEFAULT_MODEL = LanguageModel(
    provider="openai-chat-completions",
    model_name="qwen/qwen3.5-4b",
    base_url="http://localhost:1234/v1",
)
```

Use the canonical SDK provider identifier `openai-chat-completions` for the
local chat-completions endpoint. Do not use the provider alias `openai` in
TinyCUA specs, design examples, or agent factory defaults. Individual agents may
override this configuration later if needed, but M2 uses this as the de facto
default.

### Future MainLoop / External TINYCUA Agent Contract

The user-facing TINYCUA runtime should be one SDK `Agent`, not seven public
agents. That agent uses a top-level `MainLoop`:

```python
tinycua = Agent(
    name="tinycua",
    instructions=TINYCUA_MAIN_PROMPT,
    llm_model=TINYCUA_DEFAULT_MODEL,
    loop=MainLoop(),
    metadata={
        "tinycua": {
            "internal_agents": create_all_agents(),
            "state_store": SQLiteMainLoopStateStore(...),
            "artifact_store": FileSystemArtifactStore(...),
            "default_session_id": None,
            "orchestration": {
                "resume_enabled": True,
                "checkpoint_after_each_phase": True,
            },
        },
    },
)
```

`MainLoop` is the architecture overview orchestration flow: Query Analyst →
route by `ModeDecision` → Primary Agent directly, Information Digester + Worker
Mode, or Uncertain Mode handling. It coordinates internal configured agents but
does not expose them as separate user-facing agents.

M2 must keep the internal agent registry and agent-calling tools compatible with
this future external loop. `agent.config.metadata` is the intended wildcard
configuration storage for MainLoop dependencies and state hooks. TINYCUA's
storage preference is SQLite-first for structured session state, with optional
filesystem-backed storage for artifacts, snapshots, logs, attachments, or simple
deployment needs. The executable
MainLoop implementation is deferred to the top-level orchestration milestone,
after session and worker orchestration foundations exist.

#### MainLoop continuation state requirements

MainLoop needs per-session continuation state so an interrupted TINYCUA run can
resume from the last safe checkpoint. The future state object/store should track:

- `session_id`
- current orchestration phase (`query_analysis`, `primary_agent`,
  `information_digestion`, `worker`, `uncertain`, `final_response`, etc.)
- active internal agent
- active sub-session / Worker state reference
- last completed step / checkpoint
- pending user action, if any
- current `ContextEnhancedQuery`
- current `ModeDecision`
- current `DigestedInformation`
- active `Task` tree and current task id
- current `WorkerResult`
- final response status

M2 does not persist this state yet, but its config registry must avoid globals
and preserve clear hooks for a SQLite-first session store, optional filesystem
artifact/snapshot storage, and in-memory test/cache storage.

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
├── agents/                          # NEW
│   ├── __init__.py
│   ├── factory.py                    # Creates configured SDK Agent instances
│   ├── configs.py                    # AgentKind → prompt/tools/loop/schema mapping
│   └── prompts.py                    # System prompts derived from architecture docs
├── orchestration/                    # FUTURE (M6)
│   ├── main_loop.py                  # MainLoop external TINYCUA agent loop
│   └── state_store.py                # MainLoop continuation state store
├── tools/                           # Existing / expanded
│   └── agent_calls.py                # SDK Tool wrappers: call_query_analyst, etc.
├── state/                           # M1 (existing)
│   └── ...
└── ...
```

**Note**: There is no `base.py` with custom `LoopBase`, `LLMBackend`, or `ToolDef` classes. There is also no `linear.py` / `LinearAgentLoop` / `SimpleLoop` wrapper. The canonical base class is `tinycua_sdk.agent.loop.BaseLoop`. The canonical tool infrastructure is `tinycua_sdk.tools.decorators.Tool` and `tinycua_sdk.agent.executor.ToolExecutor`. Standard single-input/single-output agents use SDK `BaseLoop` directly. Custom loops are instantiated by the factory and assigned to SDK agents through the `Agent(loop=...)` constructor argument.

`tinycua/orchestration/main_loop.py` is shown as the future home for MainLoop so the product goal is explicit. It is not implemented by the M2 internal-agent integration work unless the top-level orchestration milestone is also in scope.

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/` | New | Custom loop strategies extending `tinycua_sdk.agent.loop.BaseLoop`; no custom wrapper for direct BaseLoop use |
| `tinycua/agents/` | New | Agent factory/config registry, prompt definitions, and schema mapping for all seven architecture agents |
| `tinycua/tools/agent_calls.py` | New | Agent-to-agent SDK `Tool` wrappers that call configured SDK agents |
| `tinycua/orchestration/main_loop.py` | Future | MainLoop external TINYCUA agent loop; consumes M2 internal agent registry and session state hooks |
| `tinycua/state/` | Unchanged | Loops consume M1 state objects as input/output |
| `tinycua/__init__.py` | Modified | May re-export `tinycua.loops` submodule |
| `tinycua_sdk` | **No changes** | Used as-is; custom loops extend SDK classes, do not modify SDK |

---

## Loop Architecture

### Uniform Interface (SDK Integration)

Custom loop strategies extend `tinycua_sdk.agent.loop.BaseLoop` and are attached to SDK agents through the `Agent(loop=...)` constructor parameter. Standard single-input/single-output agents omit the `loop` parameter and use SDK `BaseLoop` directly:

```python
from tinycua_sdk.agent.loop import BaseLoop
from tinycua_sdk.agent import Agent
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.tools.decorators import Tool


class ClassificationLoop(BaseLoop):
    """Structured classification using SDK's normal BaseLoop behavior."""

    def __init__(self):
        super().__init__()       # Use SDK default loop behavior; do not force one pass

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


query_analyst = Agent(
    name="query-analyst",
    instructions=QUERY_ANALYST_PROMPT,
    llm_model=TINYCUA_DEFAULT_MODEL,
    tools=[],
    loop=ClassificationLoop(),  # loop is passed into Agent, not wrapping Agent
)
```

**Design principle**: Custom loop types are thin strategies used only when behavior differs from the SDK default. The SDK's `BaseLoop.run()` handles tool calling, message management, streaming, and cancellation. Custom loops override `run()` to add domain-specific control flow (e.g., iterative gap checking, deterministic pre-checks), but the execution boundary remains the SDK `Agent`. If an agent only needs normal SDK execution with optional tool-calling iteration, it uses `BaseLoop` directly by omitting the custom `loop` argument.

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
               │       Agent Factory / Config Registry     │
               │  Agent(..., loop=CustomLoop() | None)     │
               └────────────┬─────────────────────────────┘
                            │
                            ▼
    ┌───────────────────────────────────────────────────────────────┐
    │                         tinycua_sdk.agent.Agent              │
    │  ┌─────────────────────────────────────────────────────────┐  │
    │  │  config.loop: CustomLoop | None                         │  │
    │  │  ┌───────────────────┐  ┌────────────────────────────┐  │  │
    │  │  │  Loop-specific     │  │  SchemaValidator           │  │  │
    │  │  │  control flow      │  │  (output validation        │  │  │
    │  │  │  (see sections     │  │   + retry via Agent)       │  │  │
    │  │  │   below)           │  │                            │  │  │
    │  │  └─────────┬─────────┘  └────────────┬───────────────┘  │  │
    │  │            │                         │                   │  │
    │  │  ┌─────────▼─────────────────────────▼───────────────┐  │  │
    │  │  │  Agent.run() → loop.run(agent, ...) → LLMClient   │  │  │
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

**Purpose**: High-level context scan → multi-dimensional scoring → one validated ModeDecision output.

**SDK integration**: Extends `BaseLoop` using the SDK's normal/default iteration behavior. It does **not** set `max_iterations=1` or otherwise force a true single-pass loop, because that can make the agent stop immediately before the SDK loop has room to complete normal execution. The Agent Factory configures an SDK `Agent` with a structured classification system prompt, no tools, and `loop=ClassificationLoop()`. The SDK's `BaseLoop.run()` handles LLM calls, message construction, and response parsing.

**Implementation approach**:
1. Constructor receives only loop-specific options, if any. It does not receive or store an SDK `Agent`.
2. `run()` constructs the user message from `user_query + chat_history + session_context`.
3. Delegates to `BaseLoop.run()` for normal SDK loop execution.
4. SchemaValidator validates the parsed JSON against the classification schema.
5. Returns `{context_enhanced_query, mode_decision}`.

**No tools**: The Classification loop (Query Analyst) does not use tools. The SDK `Agent` is configured with an empty tools list.

**Key design decisions**:
- One structured output, not one forced loop iteration — Query Analyst is designed to be fast, but the loop must still use SDK `BaseLoop` default iteration behavior rather than `max_iterations=1`.
- Scoring is embedded in the LLM prompt as a rubric.
- Uses SDK's `BaseLoop` for message handling and LLM orchestration — no custom LLM calling.

### 2. Exploration Loop

**Architecture reference**: `information-digestion.md`, `context-retrieval.md`

**Purpose**: Iterative gap identification + retrieval → DigestedInformation.

**SDK integration**: Extends `BaseLoop`. The Agent Factory configures an SDK `Agent` with an `enhanced_context_retrieval` SDK `Tool` and `loop=ExplorationLoop()`. The SDK's `BaseLoop` handles the tool-calling iteration (LLM requests tool → tool executes → result returned → LLM evaluates). The Exploration loop adds gap-evaluation logic on top.

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
1. Constructor receives loop-specific options such as sufficiency thresholds or max-iteration overrides, if needed. It does not receive or store an SDK `Agent`.
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
- Agent Factory creates an SDK `Agent` pre-configured with the agent-specific system prompt, `LanguageModel`, optional SDK `Tool` objects, and no custom `loop` argument so SDK `BaseLoop` is used.
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
    llm_model=TINYCUA_DEFAULT_MODEL,
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

**SDK integration**: Extends `BaseLoop`. The Agent Factory configures the Result Reviewer as an SDK `Agent` with review instructions, review tools, and `loop=HybridReviewLoop(deterministic_rules=...)`. Phase 1 runs custom deterministic rules. Phase 2 delegates to `super().run(agent, ...)` / SDK `BaseLoop` behavior for LLM semantic review. The SDK handles message construction, LLM calling, and response parsing.

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
1. Constructor receives a list of `DeterministicRule` objects (for Phase 1). It does not receive or store an SDK `Agent`.
2. `run()`:
   a. **Phase 1**: Evaluate all deterministic rules. If any rule fails with severity `escalate` or `replan`, skip Phase 2 and return the deterministic result immediately.
   b. **Phase 2**: If Phase 1 passes, delegate to SDK `BaseLoop` behavior using the `agent` passed into `run()`. The agent's review system prompt and input context drive semantic evaluation and produce one of four statuses.
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
    deterministic_rules=[
        DeterministicRule(name="SchemaValidity", check=check_schema),
        DeterministicRule(name="RequiredFields", check=check_fields),
    ],
)

review_agent = Agent(
    name="result-reviewer",
    instructions=RESULT_REVIEWER_PROMPT,
    llm_model=TINYCUA_DEFAULT_MODEL,
    tools=[...],
    loop=loop,
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

### Public API: `tinycua.agents` and agent-calling tools

```python
from tinycua.agents import (
    AgentKind,
    AgentConfigSpec,
    create_agent,
    create_all_agents,
)
from tinycua.tools.agent_calls import (
    call_query_analyst,
    call_information_digester,
    call_task_analyzer,
    call_task_assessor,
    call_task_executor,
    call_result_reviewer,
    call_primary_agent,
)

query_analyst = create_agent(AgentKind.QUERY_ANALYST)
assert isinstance(query_analyst.config.loop, ClassificationLoop)
```

`create_agent()` returns a configured SDK `Agent`, not a wrapper object. The
factory is responsible for attaching custom loops through `Agent(loop=...)` and
for omitting `loop` when default SDK `BaseLoop` behavior is intended.

### Loop type → Agent mapping (for Agent Factory / Config Registry)

| Agent | SDK Agent Config | Loop configuration | Input Type | Output Type |
|-------|------------------|--------------------|------------|-------------|
| Query Analyst | Classification prompt + no tools | `loop=ClassificationLoop()` | `{user_query, chat_history, context}` | `{context_enhanced_query, mode_decision}` |
| Information Digester | Digestion prompt + `enhanced_context_retrieval` SDK Tool | `loop=ExplorationLoop()` | `ContextEnhancedQuery` | `DigestedInformation` |
| Task Analyzer | Task analysis prompt + optional info tools + schema validation | default SDK `BaseLoop` (`loop` omitted) | `DigestedInformation` | `Task` tree |
| Task Assessor | Assessment prompt + schema validation | default SDK `BaseLoop` (`loop` omitted) | `Task` tree + `WorkerConfig` | `list[task_id]` selection |
| Task Executor | Execution prompt + native benchmark SDK Tools | default SDK `BaseLoop` (`loop` omitted) | `Task` | `TaskResult` |
| Result Reviewer | Review prompt + pluggable deterministic rules | `loop=HybridReviewLoop(...)` | `{task, task_result, execution_log}` | `ReviewerDecision` |
| Primary Agent | Synthesis prompt + formatting/verification SDK Tools | default SDK `BaseLoop` (`loop` omitted) | `ContextEnhancedQuery` or `WorkerResult` | final response |

### Agent-to-Agent Calling Tool Contract

Each `call_*` helper is exposed as an SDK `Tool`. The tool implementation loads
or receives the target configured SDK `Agent`, calls `target_agent.run(...)`,
validates the target schema, and returns the normalized output. It must not call
LLM clients directly or bypass the target agent's configured loop.

### MainLoop Metadata Contract

The future external TINYCUA agent should store MainLoop dependencies in
`agent.config.metadata["tinycua"]`:

| Metadata key | Purpose |
|--------------|---------|
| `internal_agents` | Mapping from `AgentKind` to configured SDK `Agent` instances |
| `state_store` | Structured session/continuation state store; SQLite-backed by default |
| `artifact_store` | Optional filesystem-backed storage for artifacts, snapshots, logs, attachments, or large/unstructured payloads |
| `default_session_id` | Optional fallback session id when caller does not provide one |
| `orchestration` | Flags/settings such as checkpointing and resume behavior |

MainLoop should read these dependencies from the external agent passed into
`run(agent, messages, tools, ...)`, not from module-level globals.

---

## Future Architecture Documentation Sync

This PR is spec/design-only and should not edit `src/tinycua/docs/architecture/` yet. During implementation, the architecture docs should be synchronized with this design:

| Architecture Doc | Future Change |
|------------------|---------------|
| `overview.md` | Update the Agent Loop Types table so Task Analyzer and Task Assessor are mapped to direct SDK `BaseLoop` usage instead of a separate input→output / Linear / Simple loop type. |
| `task-analysis.md` | Clarify that Task Analyzer is an SDK `Agent` using default SDK `BaseLoop`; any single-output guarantee comes from prompt/schema validation around `Agent.run()`. |
| `task-assessor.md` | Clarify that Task Assessor is an SDK `Agent` using default SDK `BaseLoop`; decomposition-selection output is schema-validated outside the loop. |
| Any architecture docs mentioning "Linear", "Simple", or "input→output" loop semantics | Normalize wording to distinguish direct SDK `BaseLoop` usage from true custom loop strategies. |
| `src/tinycua-sdk/docs/cookbook/execution-and-reference/custom-execution-loops.md` | Correct custom loop examples so loop instances are passed to `Agent(loop=...)`; clarify that `agent.run()` uses `agent.config.loop` or default `BaseLoop()`, not an unattached local `loop` variable. |

The implementation phase should include an architecture-doc synchronization task after the SDK-integrated loop design is finalized.

---

## Implementation Phases

### Phase 1 — SDK Integration Foundation

- [ ] Verify `tinycua-sdk` dependency is available and properly configured in `pyproject.toml`
- [ ] Create `tinycua/loops/errors.py` with error hierarchy (thin wrappers)
- [ ] Create `tinycua/loops/schema_validator.py` that wraps SDK `Agent.run()` with output validation and retry
- [ ] Create `tinycua/loops/__init__.py` re-exporting SDK types and custom loop types
- [ ] Create `tinycua/agents/` config registry and prompt module skeleton
- [ ] Define TinyCUA default model config as `LanguageModel(provider="openai-chat-completions", model_name="qwen/qwen3.5-4b", base_url="http://localhost:1234/v1")` and use it in all default agent configs
- [ ] Define MainLoop metadata contract keys (`internal_agents`, `state_store`, optional `artifact_store`, `default_session_id`, `orchestration`) so M2 configs are compatible with the future external TINYCUA agent and SQLite-first storage preference

### Phase 2 — Classification Loop

- [ ] Implement `tinycua/loops/classification.py` extending `BaseLoop`
- [ ] Configure Query Analyst as `Agent(..., loop=ClassificationLoop())` with classification prompt and schema validation
- [ ] Write unit tests using mock SDK `Agent`: valid outputs for all three modes, anti-laziness safeguards, edge cases, and no forced `max_iterations=1` single-pass configuration

### Phase 3 — Exploration Loop

- [ ] Implement `tinycua/loops/exploration.py` extending `BaseLoop`, adding gap-evaluation between SDK iterations
- [ ] Define Enhanced Context Retrieval as an SDK `Tool` contract (full native implementation belongs to the Tools milestone; stub/mock is acceptable for M2 tests)
- [ ] Configure Information Digester as `Agent(..., loop=ExplorationLoop())` with digestion prompt, retrieval tool, and schema validation
- [ ] Write unit tests using mock SDK `Agent`: multi-iteration retrieval, stop on sufficiency, empty results → known_gaps

### Phase 4 — Direct SDK BaseLoop Agent Configurations

- [ ] Configure Task Analyzer and Task Assessor to use SDK `BaseLoop` directly (no `tinycua/loops/linear.py`)
- [ ] Configure Task Executor and Primary Agent to use SDK `BaseLoop` directly with their required SDK tools
- [ ] Add output schema validation tests for standard agents around SDK `Agent.run()`
- [ ] Verify optional SDK `Tool` usage and pure-reasoning behavior through SDK `BaseLoop`

### Phase 5 — Hybrid Review Loop

- [ ] Implement `tinycua/loops/hybrid_review.py` with two-phase execution: deterministic rules + SDK `Agent.run()`
- [ ] Configure Result Reviewer as `Agent(..., loop=HybridReviewLoop(...))` with review prompt, deterministic rules, and schema validation
- [ ] Write unit tests using mock SDK `Agent`: all four statuses, deterministic failure overrides LLM, context_updates on accept

### Phase 6 — Agent-to-Agent Tools, Integration & Documentation

- [ ] Implement `call_query_analyst`, `call_information_digester`, `call_task_analyzer`, `call_task_assessor`, `call_task_executor`, `call_result_reviewer`, `call_primary_agent` as SDK `Tool` objects
- [ ] Integration tests: end-to-end with mock SDK `Agent` for each configured architecture agent
- [ ] Verify custom loops are attached through SDK `Agent(loop=...)`, not by wrapping agents
- [ ] Verify agent factory output can be placed under `Agent(loop=MainLoop(), metadata={"tinycua": {"internal_agents": ...}})` without changing internal agent APIs
- [ ] Docstrings and usage examples for all loop types
- [ ] Update SDK custom execution loops cookbook to document `Agent(loop=CustomLoop(...))` usage and remove/clarify examples where `loop = CustomLoop()` is not attached to the agent
- [ ] Sync architecture docs listed in **Future Architecture Documentation Sync**
- [ ] Verify all loops integrate correctly with SDK's `BaseLoop.run()` interface
- [ ] Verify all M1 state types are properly consumed and produced

---

## Technical Decisions

0. **Decision**: Custom loop strategies MUST extend or compose with `tinycua_sdk.agent.loop.BaseLoop` and use `tinycua_sdk.agent.Agent` for LLM interaction. Standard single-input/single-output agents MUST use SDK `BaseLoop` directly. No custom LLM backend protocols, tool-calling infrastructure, or streaming logic.
   - **Reason**: The SDK already provides a mature, tested execution infrastructure (`BaseLoop`, `Agent`, `LLMClient`, `Tool`, `ToolExecutor`). Redefining these in `tinycua.loops` would create a parallel, incompatible infrastructure that cannot integrate with the rest of the TINYCUA system (Agent Factory, tool registry, configured agents). Custom loop strategies are only needed where domain control flow differs from SDK default behavior — prompt design, output schemas, iterative retrieval, or deterministic pre-checks.
   - **Alternatives Considered**: Standalone loops with custom `LLMBackend` Protocol and `ToolDef` dataclass — rejected because they bypass the SDK's tool execution, streaming, cancellation, and event system, creating two incompatible execution paths. A custom Linear/Simple loop wrapper — rejected because SDK `BaseLoop` already represents that execution pattern.

1. **Decision**: Uniform execution uses SDK `BaseLoop` rather than custom per-loop interfaces.
   - **Reason**: Agent Factory needs to treat custom strategies and standard agents consistently. The SDK's `BaseLoop.run()` already provides a uniform signature. Custom loops extend this without changing the interface contract; standard agents use it directly.
   - **Alternatives Considered**: Custom `LoopBase` with `LLMBackend` Protocol — rejected per Decision #0.

1a. **Decision**: M2 combines custom loops, agent factory/configuration, prompts, concrete agent definitions, and agent-to-agent tools.
   - **Reason**: SDK agents own loop selection through `Agent(loop=...)`. Separating loop implementation from agent construction would hide the real integration boundary and make tests less representative.
   - **Alternatives Considered**: Keep separate roadmap milestones for loops, factory, prompts, agents, and agent calling — rejected because those pieces must be validated together through actual SDK `Agent` instances.

1b. **Decision**: TinyCUA's default model config is `provider="openai-chat-completions"`, `model_name="qwen/qwen3.5-4b"`, and `base_url="http://localhost:1234/v1"`.
   - **Reason**: TinyCUA targets a local chat-completions-compatible endpoint by default. The SDK has its own defaults, but TinyCUA agent factory defaults should be explicit and project-specific.
   - **Alternatives Considered**: SDK default `LanguageModel()` — rejected because TinyCUA needs a specific local model. Provider alias `openai` — rejected because it resolves to the Responses API and is not the intended chat-completions provider.

1c. **Decision**: MainLoop is the future single external TINYCUA agent loop and should use `agent.config.metadata` for internal agent registry and continuation-state dependencies.
   - **Reason**: TINYCUA should be exposed as one agent (`Agent(loop=MainLoop(), ...)`) while internal agents remain implementation details. SDK `Agent.metadata` is the existing wildcard configuration location, so it avoids new global registries and keeps MainLoop compatible with SDK execution.
   - **Alternatives Considered**: Expose internal agents directly to users — rejected because it leaks orchestration internals. Store MainLoop dependencies in module globals — rejected because it makes per-session state and tests harder. Implement MainLoop inside M2 — deferred because full resume behavior depends on session and worker orchestration milestones.

1d. **Decision**: TINYCUA storage is SQLite-first for structured session state, with pluggable filesystem-backed storage when useful.
   - **Reason**: SQLite provides a simple durable default for sessions, execution logs, and continuation checkpoints. Filesystem storage remains useful for larger artifacts, exported context snapshots, attachments, logs, and simple file-backed deployments. The storage contract should allow mixing both instead of forcing all data into one backend.
   - **Alternatives Considered**: SQLite-only — rejected because not all payloads are best stored in relational tables. Filesystem-only — rejected because structured session state and transactional checkpoints benefit from SQLite. In-memory-only — rejected except for tests/cache because resume requires durable state.

2. **Decision**: Classification loop produces one structured classification result without forcing `max_iterations=1` or a true single-pass loop.
   - **Reason**: Query Analyst is designed for speed, and multi-dimensional scoring is embedded in the prompt as one output contract. However, forcing a one-iteration loop can make the agent stop immediately and bypass the SDK's normal loop behavior. Classification should therefore rely on prompt/schema validation for one result while keeping SDK `BaseLoop` default iteration semantics and safety caps.
   - **Alternatives Considered**: `max_iterations=1` single-pass loop — rejected because it can prematurely stop the agent. Separate scoring and CEQ generation calls — rejected because it adds latency with no architectural benefit.

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
