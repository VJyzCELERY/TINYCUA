# Design Document: Agent + Loop Integration (M2)

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-05-31

---

## Overview

Implement M2 as an integrated Agent + Loop milestone. Custom loop strategies, agent wrapper classes, system prompts, and agent-to-agent calling tools are designed together because the SDK execution model is `Agent(loop=CustomLoop(), ...)`: loops are configuration on SDK agents, not wrappers around agents. Internal TinyCUA agents are wrapper classes (e.g., `QueryAnalyst`, `TaskExecutor`) that compose an SDK `Agent` internally — the wrapper owns the configured agent, context state, and domain-specific methods. Custom loop strategies are used only where the default SDK loop is insufficient: Classification, Exploration, and Hybrid Review. Standard single-input/single-output agents use `tinycua_sdk.agent.loop.BaseLoop` directly through the composed SDK `Agent.run()` rather than a custom Linear/Simple loop class. All strategies are built on top of `tinycua_sdk` (`Agent`, `BaseLoop`, `LLMClient`, `LanguageModel`, `Tool`) and delegate LLM orchestration, tool execution, streaming, and cancellation to the SDK. M1 state objects are consumed as input and produced as output.

Resolved strategy choices are part of this design, not open questions:

- Standard single-input/single-output agents use SDK `BaseLoop` directly; no custom Linear/Simple loop wrapper is introduced.
- Custom loops are passed into the composed SDK agent through `Agent(loop=CustomLoop(), ...)` inside the wrapper class; custom loops do not own or wrap `Agent` instances.
- TinyCUA internal agents are wrapper classes composing (not extending) SDK `Agent`, so wrapper-level concerns (logging, verbosity, context management, state persistence) are separated from low-level loop execution.
- Wrapper class instance attributes are the canonical location for context state, session identifiers, and configuration — not SDK `Agent.metadata`.
- Classification produces one structured classification result but does not enforce a true one-iteration/single-pass loop; it uses SDK `BaseLoop` default iteration behavior so the agent is not forced to stop immediately.
- ClassificationTool is owned by the `QueryAnalyst` wrapper class and is configurable via `QueryAnalystConfig.classification_labels`.
- Exploration stops when the LLM judges retrieved context sufficient, with `BaseLoop.max_iterations` as a hard safety cap.
- Hybrid Review deterministic checks are pluggable rules registered at construction time, not hardcoded checks inside the loop.
- Former roadmap M2/M3/M4/M5/M7 scope is collapsed into this M2 because loop selection, agent creation, prompts, and agent-calling tools must be tested in tandem.
- The final product exposes one external TINYCUA wrapper: `TinyCUA(...)` composing an SDK `Agent` with `MainLoop`. M2 does not implement executable `MainLoop`, but it defines the wrapper class contract and internal agent shape MainLoop will consume.

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

Custom loop strategies do NOT define their own LLM backend protocols, tool-calling infrastructure, retry logic, or streaming. They extend SDK classes and customize behavior through prompt design, output schemas, and control-flow hooks. Standard single-output agents do not need a custom loop strategy at all. Each architecture agent is a wrapper class that composes an SDK `Agent` with the correct `loop`, prompt, tools, model, policy, and output validator; the wrapper exposes a domain-specific `run()` method and manages context state as instance attributes.

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

### Future MainLoop / External TinyCUA Agent Contract

The user-facing TINYCUA runtime should be one wrapper class, not seven public
agents. That wrapper composes an SDK `Agent` with a top-level `MainLoop`:

```python
class TinyCUA:
    """External TinyCUA agent — wraps SDK Agent with MainLoop orchestration."""

    def __init__(self, config: TinyCUAConfig):
        self.config = config
        self.agent = Agent(
            name="tinycua",
            instructions=config.instructions,
            llm_model=config.model,
            loop=MainLoop(),
            # SDK Agent.metadata is NOT used for state — wrapper attributes hold state
        )
        self.internal_agents = create_all_agents(config.internal_agent_overrides)
        self.state_store = config.state_store  # e.g., SQLiteMainLoopStateStore
        self.artifact_store = config.artifact_store  # e.g., FileSystemArtifactStore
        self.session_state: dict | None = None

    async def run(self, user_query: str, session_id: str | None = None) -> Response:
        ...
```

```python
@dataclass
class TinyCUAConfig:
    """Configuration for the external TinyCUA wrapper class."""
    instructions: str = TINYCUA_MAIN_PROMPT
    model: LanguageModel = TINYCUA_DEFAULT_MODEL
    state_store: Any = None     # SQLiteMainLoopStateStore or None
    artifact_store: Any = None  # FileSystemArtifactStore or None
    internal_agent_overrides: dict[AgentKind, AgentConfigBase] = field(default_factory=dict)
    orchestration: OrchestrationSettings = field(default_factory=OrchestrationSettings)
```

`MainLoop` is the architecture overview orchestration flow: Query Analyst →
route by `ModeDecision` → Primary Agent directly, Information Digester + Worker
Mode, or Uncertain Mode handling. It coordinates internal wrapper classes by
calling their `run()` methods but does not expose them as separate user-facing
agents.

M2 must keep the internal agent wrapper classes and agent-calling tools
compatible with this future external wrapper. Config state and the internal
agent registry live on the `TinyCUA` wrapper instance, not inside SDK
`Agent.metadata`. TINYCUA's storage preference is SQLite-first for structured
session state, with optional filesystem-backed storage for artifacts, snapshots,
logs, attachments, or simple deployment needs. The executable MainLoop
implementation is deferred to the top-level orchestration milestone, after
session and worker orchestration foundations exist.

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

M2 does not persist this state yet, but each wrapper class's `save_state(store)` and `restore_state(store)` hooks accept a storage backend parameter and leave a clear contract for a SQLite-first session store, optional filesystem artifact/snapshot storage, and in-memory test/cache storage.

### Module Layout

```
src/tinycua/tinycua/
├── __init__.py
├── cli/
├── config/                           # NEW
│   ├── __init__.py
│   ├── types.py                        # AgentKind enum, TINYCUA_DEFAULT_MODEL
│   └── agents.py                       # AgentConfigBase + 7 per-agent config dataclasses
├── loops/                           # NEW — 1 shared ReAct + 3 custom loops
│   ├── __init__.py                  # Re-exports all loop types + SDK integration types
│   ├── react_agent.py               # ReActAgentLoop (extends BaseLoop) — shared ReAct loop for simple agents
│   ├── query_analyst_loop.py        # QueryAnalystLoop (extends BaseLoop) — classification
│   ├── information_digestion_loop.py # InformationDigestionLoop (extends BaseLoop) — iterative retrieval
│   ├── result_review_loop.py        # ResultReviewLoop (extends BaseLoop) — two-phase review
│   ├── schema_validator.py          # Output validation (uses SDK event/model infra)
│   ├── main_loop.py                  # FUTURE (M6): MainLoop low-level execution loop
│   └── errors.py                    # LoopError hierarchy (thin wrappers around SDK errors)
├── agents/                          # NEW
│   ├── __init__.py
│   ├── base.py                        # BaseAgentWrapper (abstract) — composes SDK Agent
│   ├── factory.py                      # create_agent(), create_all_agents() — creates wrapper instances
│   ├── prompts.py                      # System prompts derived from architecture docs
│   ├── query_analyst.py                # QueryAnalyst wrapper class
│   ├── information_digester.py         # InformationDigester wrapper class
│   ├── task_analyzer.py                # TaskAnalyzer wrapper class
│   ├── task_assessor.py                # TaskAssessor wrapper class
│   ├── task_executor.py                # TaskExecutor wrapper class
│   ├── result_reviewer.py              # ResultReviewer wrapper class
│   ├── primary_agent.py                # PrimaryAgent wrapper class
│   └── tinycua_agent.py                # FUTURE (M6): TinyCUA external wrapper class
├── tools/                           # Existing / expanded
│   └── agent_calls.py                # SDK Tool wrappers: call_query_analyst, etc.
├── state/                           # M1 (existing) + M2 extensions
│   ├── ...                            # Existing M1 state types
│   ├── information.py                 # NEW: StateInformation for wrapper context state
│   └── state_store.py                 # FUTURE (M6): MainLoop continuation state store
└── ...
```

**Note**: There is no `base.py` with custom `LoopBase`, `LLMBackend`, or `ToolDef` classes. There is also no `linear.py` / `LinearAgentLoop` / `SimpleLoop` wrapper. The canonical base class for loops is `tinycua_sdk.agent.loop.BaseLoop`. The canonical tool infrastructure is `tinycua_sdk.tools.decorators.Tool` and `tinycua_sdk.agent.executor.ToolExecutor`. Standard single-input/single-output agents use SDK `BaseLoop` directly. Each architecture agent is a wrapper class that composes an SDK `Agent` configured with the appropriate loop via `Agent(loop=...)`. The wrapper class exposes a domain-specific `run()` method and manages its runtime state through a `StateInformation` instance.

`tinycua/agents/base.py` provides `BaseAgentWrapper` — an abstract base for all internal agent wrappers. It stores the composed SDK `Agent`, config, and a `StateInformation` instance (`self.state`). Concrete wrappers (e.g., `QueryAnalyst`) extend it and implement domain-specific `run()`, `save_state()`, and `restore_state()`.

`tinycua/config/` holds the `AgentKind` enum, `TINYCUA_DEFAULT_MODEL`, and all seven per-agent config dataclasses — separate from the agent wrapper code so config types are importable without depending on loop or agent implementations.

`tinycua/state/information.py` defines `StateInformation` — the structured state object each wrapper uses instead of a raw `self.context: dict`. It holds fields like `session_id`, runtime context, and agent-specific data.

`tinycua/loops/main_loop.py` is the future home for `MainLoop`. `tinycua/agents/tinycua_agent.py` is the future home for the `TinyCUA` external wrapper class. `tinycua/state/state_store.py` is the future home for the continuation state store. None is implemented by M2 unless the top-level orchestration milestone is also in scope.

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/` | New | Custom loop strategies extending `tinycua_sdk.agent.loop.BaseLoop`; no custom wrapper for direct BaseLoop use |
| `tinycua/config/` | New | `AgentKind` enum, `TINYCUA_DEFAULT_MODEL`, 7 per-agent config dataclasses in `agents.py` |
| `tinycua/agents/base.py` | New | `BaseAgentWrapper` — abstract base for all internal agent wrapper classes |
| `tinycua/agents/<agent>.py` | New | Seven wrapper classes + `tinycua_agent.py` (future TinyCUA external wrapper) |
| `tinycua/agents/factory.py` | New | `create_agent()` / `create_all_agents()` — creates wrapper instances from config dataclasses |
| `tinycua/agents/prompts.py` | New | System prompts for all seven agents |
| `tinycua/tools/agent_calls.py` | New | Agent-to-agent SDK `Tool` wrappers that call wrapper `run()` methods |
| `tinycua/loops/main_loop.py` | Future | MainLoop low-level execution loop (M6) |
| `tinycua/state/state_store.py` | Future | MainLoop continuation state store (M6) |
| `tinycua/state/information.py` | New | `StateInformation` — structured runtime state for wrapper classes |
| `tinycua/state/` | Modified | Existing M1 state types; extended with `StateInformation` |
| `tinycua/agent/` | Remove | Existing stub directory; superseded by `tinycua/agents/` |
| `tinycua/__init__.py` | Modified | Re-export `tinycua.loops`, `tinycua.agents`, and `tinycua.config` submodules |
| `src/tinycua/docs/design/` | New (impl phase) | Design docs for all wrapper classes, configs, and loop strategies |
| `tinycua_sdk` | **No changes** | Used as-is; custom loops extend SDK classes, do not modify SDK |

---

## Agent Wrapper Classes

Each TinyCUA architecture agent is a wrapper class that composes an SDK `Agent`
internally. The wrapper owns the configured agent, context state, and
domain-specific methods. Loops stay focused on low-level execution; the wrapper
handles higher-level concerns.

### BaseAgentWrapper

```python
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from tinycua_sdk.agent import Agent
from tinycua.state.information import StateInformation

S = TypeVar("S", bound=StateInformation)


class BaseAgentWrapper(ABC, Generic[S]):
    """Abstract base for all TinyCUA internal agent wrappers.

    Composes (does not extend) an SDK Agent internally. Runtime state is
    stored in a typed `StateInformation` subclass (NOT a raw dict and
    NOT inside SDK Agent.metadata).

    Type parameter `S` is the concrete StateInformation subclass for this agent.
    """

    state: S

    def __init__(self, config: AgentConfigBase, state_factory: type[S]):
        self.config = config
        self.agent: Agent | None = None     # Built by _build_agent() in subclass
        self.state = state_factory()         # Agent-specific StateInformation instance

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Domain-specific execution. Subclasses override."""

    def save_state(self, store: Any) -> None:
        """Save wrapper state to a storage backend. No-op default."""
        pass

    def restore_state(self, store: Any) -> None:
        """Restore wrapper state from a storage backend. No-op default."""
        pass
```

### StateInformation (in `tinycua/state/information.py`)

`StateInformation` is an abstract base class that each agent wrapper subclasses with
its own agent-specific fields. This gives each agent typed, self-documenting state
instead of a generic dict.

```python
from abc import ABC
from dataclasses import dataclass, field
from tinycua.state import (
    ContextEnhancedQuery,
    ModeDecision,
    DigestedInformation,
    Task,
    TaskResult,
    ReviewerDecision,
    ReviewStatus,
)


@dataclass
class StateInformation(ABC):
    """Abstract base for per-agent structured runtime state.

    Each agent wrapper defines a concrete subclass with fields specific to
    that agent's domain, using M1 typed state objects (not raw dicts).
    Shared fields live here; agent-specific fields live on the subclass.
    """
    session_id: str | None = None
    chat_history: list[dict] = field(default_factory=list)
    last_query: dict[str, Any] = field(default_factory=dict)
    last_result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryAnalystState(StateInformation):
    """State for the Query Analyst agent."""
    mode_decision: ModeDecision | None = None
    context_enhanced_query: ContextEnhancedQuery | None = None
    classification_score: float | None = None


@dataclass
class InformationDigesterState(StateInformation):
    """State for the Information Digester agent."""
    digested_information: DigestedInformation | None = None
    retrieval_iterations: int = 0


@dataclass
class TaskAnalyzerState(StateInformation):
    """State for the Task Analyzer agent."""
    task_tree: Task | None = None


@dataclass
class TaskAssessorState(StateInformation):
    """State for the Task Assessor agent."""
    selected_task_ids: list[str] = field(default_factory=list)


@dataclass
class TaskExecutorState(StateInformation):
    """State for the Task Executor agent."""
    task_result: TaskResult | None = None
    execution_attempts: int = 0
    tool_results: list[dict] = field(default_factory=list)


@dataclass
class ResultReviewerState(StateInformation):
    """State for the Result Reviewer agent."""
    reviewer_decision: ReviewerDecision | None = None
    deterministic_failures: list[str] = field(default_factory=list)
    last_review_status: ReviewStatus | None = None


@dataclass
class PrimaryAgentState(StateInformation):
    """State for the Primary Agent agent."""
    final_response: dict[str, Any] = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
```

### Concrete Wrapper Example: QueryAnalyst

```python
from tinycua_sdk.agent import Agent
from tinycua.config.agents import QueryAnalystConfig
from tinycua.loops import QueryAnalystLoop, SchemaValidator
from tinycua.state.information import QueryAnalystState
from tinycua.tools import ClassificationTool

# Base tools — the tools this agent fundamentally needs.
# NOT part of config.extra_tools (which is for externally injected tools only).
QUERY_ANALYST_BASE_TOOLS = []  # ClassificationTool is built at init time from config


class QueryAnalyst(BaseAgentWrapper[QueryAnalystState]):
    """Query classification agent — Classification Loop."""

    state: QueryAnalystState  # typed state

    def __init__(self, config: QueryAnalystConfig):
        super().__init__(config, state_factory=QueryAnalystState)
        self.classification_tool = ClassificationTool(labels=config.classification_labels)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[
                self.classification_tool,          # agent's own tool
                *QUERY_ANALYST_BASE_TOOLS,         # module-level constant
                *self.config.extra_tools,          # externally injected (empty by default)
            ],
            loop=QueryAnalystLoop(),
        )

    async def run(
        self,
        user_query: str,
        chat_history: list[dict] | None = None,
        session_context: dict | None = None,
    ) -> dict[str, Any]:
        """Classify user query into mode decision + context enhanced query."""
        self.state.session_id = session_context.get("session_id") if session_context else None
        self.state.chat_history = chat_history or []
        input_msg = {"user_query": user_query, "chat_history": self.state.chat_history, "session_context": session_context or {}}
        raw = await self.agent.run(query=str(input_msg))
        result = SchemaValidator(validation_fn=validate_classification_output).validate(raw)
        self.state.mode_decision = ModeDecision(**result.get("mode_decision", {}))
        self.state.context_enhanced_query = ContextEnhancedQuery(**result.get("context_enhanced_query", {}))
        self.state.last_result = result
        return result
```

Every agent follows this pattern: `_build_agent()` merges three tool sources:

| Source | Purpose | Example |
|--------|---------|---------|
| Agent-initialized tools | Built at `__init__` from config (e.g., `ClassificationTool(labels=...)`) | `self.classification_tool` |
| `*_BASE_TOOLS` | Module-level constant — the agent's inherent tools | `[]` for QueryAnalyst, `[retrieval_tool]` for InformationDigester |
| `config.extra_tools` | Injected by caller / MainLoop — **empty list by default** | Extra logging, monitoring, or custom tools |

### Layer Separation: Wrapper vs Loop

| Concern | Managed By | Examples |
|---------|-----------|----------|
| LLM orchestration | SDK `BaseLoop` | Tool calling, message construction, streaming |
| Tool execution | SDK `ToolExecutor` | Invoke tools, normalize results |
| Domain control flow | Custom loop (`QueryAnalystLoop`, etc.) | Gap evaluation, two-phase review |
| Input preparation | Wrapper class `run()` | Building prompt messages from domain objects |
| Output parsing | Wrapper class `run()` | Parsing raw LLM output into typed objects |
| Context management | Wrapper `self.state` (StateInformation) | Storing last result, session state, tool results |
| Persistence hooks | Wrapper class `save_state()`/`restore_state()` | Delegating to SQLite/filesystem stores, saving/restoring StateInformation |
| Logging / verbosity | Wrapper class | Per-agent log level, progress callbacks |
| Config override | Agent config dataclass | Classification labels, deterministic rules, extra tools |

This separation ensures loops remain testable at the SDK level (mock `Agent`,
mock `LLMClient`) while wrapper classes are testable at the integration level
(mock LLM responses through the composed agent).

### Agent-to-Agent Calling Through Wrappers

Agent-calling tools receive a wrapper instance and delegate through its `run()`
method, preserving wrapper-managed context and validation:

```python
from tinycua_sdk.tools.decorators import Tool


def call_query_analyst(internal_agents: dict[AgentKind, BaseAgentWrapper]) -> Tool:
    """SDK Tool that delegates to the QueryAnalyst wrapper."""

    async def execute(
        user_query: str,
        chat_history: list[dict] | None = None,
        session_context: dict | None = None,
    ) -> dict[str, Any]:
        analyst = internal_agents[AgentKind.QUERY_ANALYST]
        # Goes through wrapper.run(), not raw SDK Agent.run()
        return await analyst.run(
            user_query=user_query,
            chat_history=chat_history or [],
            session_context=session_context or {},
        )

    return Tool(
        name="call_query_analyst",
        description="Classify user query into a mode decision",
        input_schema=...,  # accepted by SDK Tool
        execute=execute,
    )
```

---

## Loop Architecture

### Uniform Interface (SDK Integration)

Custom loop strategies extend `tinycua_sdk.agent.loop.BaseLoop` and are attached to the composed SDK agent inside the wrapper class through `Agent(loop=...)`. Standard single-input/single-output agents omit the `loop` parameter and use SDK `BaseLoop` directly:

```python
from tinycua_sdk.agent.loop import BaseLoop
from tinycua_sdk.agent import Agent
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.tools.decorators import Tool


class QueryAnalystLoop(BaseLoop):
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


# The loop is used inside the wrapper class, not standalone:
class QueryAnalyst(BaseAgentWrapper):
    def __init__(self, config: QueryAnalystConfig):
        super().__init__(config)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[
                ClassificationTool(self.config.classification_labels),
                *QUERY_ANALYST_BASE_TOOLS,
                *self.config.extra_tools,
            ],
            loop=QueryAnalystLoop(),  # loop is passed into Agent, not wrapping it
        )

    async def run(self, user_query: str, chat_history=None, session_context=None) -> dict:
        """Domain-specific execution — prepares input, delegates to composed SDK Agent."""
        input_msg = {"user_query": user_query, ...}
        raw = await self.agent.run(query=str(input_msg))
        return SchemaValidator(validation_fn=validate_classification).validate(raw)
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

**SDK integration**: Extends `BaseLoop` using the SDK's normal/default iteration behavior. It does **not** set `max_iterations=1` or otherwise force a true single-pass loop, because that can make the agent stop immediately before the SDK loop has room to complete normal execution. The `QueryAnalyst` wrapper class composes an SDK `Agent` with a structured classification system prompt, `ClassificationTool`, and `loop=QueryAnalystLoop()`. The SDK's `BaseLoop.run()` handles LLM calls, message construction, and response parsing.

**Implementation approach**:
1. Constructor receives only loop-specific options, if any. It does not receive or store an SDK `Agent`.
2. `run()` constructs the user message and delegates to `BaseLoop.run()`.
3. The `QueryAnalyst` wrapper configures `ClassificationTool(labels=config.classification_labels)` on the composed SDK `Agent`. The tool presents a list of classification labels to the agent; the agent selects an index (`classify(mode_index=0)`), and the tool returns the corresponding label.
4. `SchemaValidator` validates the parsed output against the classification schema.
5. The wrapper extracts and returns `{context_enhanced_query, mode_decision}`.
6. Result is stored on the wrapper's `self.state` for later use/diagnostics.

**ClassificationTool (configured at wrapper level, not loop level)**: The tool takes a `classification_labels` list at construction. The agent calls `classify(mode_index=N)` where N is the index of the chosen classification. The tool returns the label at that index. Changing classification labels only requires updating `QueryAnalystConfig.classification_labels` — no prompt edits needed.

**Key design decisions**:
- One structured output, not one forced loop iteration — Query Analyst is designed to be fast, but the loop must still use SDK `BaseLoop` default iteration behavior rather than `max_iterations=1`.
- Scoring is embedded in the LLM prompt as a rubric.
- `ClassificationTool` decouples classification labels from prompts; the agent picks an index, the tool resolves it.
- Uses SDK's `BaseLoop` for message handling and LLM orchestration — no custom LLM calling.

### 2. Exploration Loop

**Architecture reference**: `information-digestion.md`, `context-retrieval.md`

**Purpose**: Iterative gap identification + retrieval → DigestedInformation.

**SDK integration**: Extends `BaseLoop`. The `InformationDigester` wrapper class composes an SDK `Agent` with an `enhanced_context_retrieval` SDK `Tool` and `loop=InformationDigestionLoop()`. The SDK's `BaseLoop` handles the tool-calling iteration (LLM requests tool → tool executes → result returned → LLM evaluates). The Exploration loop adds gap-evaluation logic on top.

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

### 3. ReActAgentLoop (shared — TaskAnalyzer, TaskAssessor, TaskExecutor, PrimaryAgent)

**Purpose**: Single input → single output with SDK-provided ReAct/tool-calling internal iteration. Used by any agent whose execution strategy does not require custom routing, exploration, or deterministic review phases.

**SDK integration**: `ReActAgentLoop` extends `BaseLoop` and is imported from `tinycua.loops.react_agent`. Simple agents configure their composed SDK `Agent` with `loop=ReActAgentLoop()`. The wrapper's `run()` method prepares input, delegates to the composed agent, and handles post-processing (validation, formatting, state updates).

**Implementation approach**:
```python
from tinycua_sdk.agent.loop import BaseLoop


class ReActAgentLoop(BaseLoop):
    """Shared ReAct loop — extends SDK BaseLoop with no additional control flow.

    Used directly by TaskAnalyzer, TaskAssessor, TaskExecutor, and PrimaryAgent.
    The wrapper class provides agent identity; the loop provides execution strategy.
    Pre-processing and post-processing happen in the wrapper's run() method.
    """
    pass  # Inherits all BaseLoop behavior; no override needed
```

**Configuration (inside wrapper class)**:
```python
from tinycua_sdk.agent import Agent
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.loops import SchemaValidator
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import TaskAnalyzerConfig
from tinycua.state.information import TaskAnalyzerState

TASK_ANALYZER_BASE_TOOLS: list[Tool] = []


class TaskAnalyzer(BaseAgentWrapper[TaskAnalyzerState]):
    """Task decomposition agent — ReActAgentLoop."""

    state: TaskAnalyzerState

    def __init__(self, config: TaskAnalyzerConfig):
        super().__init__(config, state_factory=TaskAnalyzerState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[
                *TASK_ANALYZER_BASE_TOOLS,
                *self.config.extra_tools,
            ],
            loop=ReActAgentLoop(),
        )

    async def run(self, digested_information: dict) -> dict:
        self.state.last_query = {"digested_information": digested_information}
        input_msg = f"Analyze the following information:\n{json.dumps(digested_information)}"
        raw = await self.agent.run(query=input_msg)
        result = SchemaValidator(validation_fn=validate_task_tree).validate(raw)
        self.state.last_result = result
        return result
```

**Key distinction from custom loops**:
- No gap-iteration control (unlike InformationDigestionLoop) — ReAct handles tool iteration.
- No classification scoring (unlike QueryAnalystLoop) — the agent produces exactly one output.
- No deterministic pre-checks (unlike ResultReviewLoop).
- One input, one output — the agent may think internally via ReAct/tool loop but produces a single definitive result after the wrapper validates it.
- No `tinycua.loops.linear` module and no custom `LinearAgentLoop` type.

### 4. Result Review Loop

**Architecture reference**: `result-reviewer.md`

**Purpose**: Two-phase review: deterministic checks first, then LLM semantic review via SDK `Agent.run()` → ReviewerDecision.

**SDK integration**: Extends `BaseLoop`. The Agent Factory configures the Result Reviewer as an SDK `Agent` with review instructions, review tools, and `loop=ResultReviewLoop(deterministic_rules=...)`. Phase 1 runs custom deterministic rules. Phase 2 delegates to `super().run(agent, ...)` / SDK `BaseLoop` behavior for LLM semantic review. The SDK handles message construction, LLM calling, and response parsing.

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


RESULT_REVIEWER_BASE_TOOLS: list[Tool] = []  # no inherent tools; review criteria are in the prompt


class ResultReviewer(BaseAgentWrapper[ResultReviewerState]):
    """Result review agent — Hybrid Review Loop."""

    state: ResultReviewerState

    def __init__(self, config: ResultReviewerConfig):
        super().__init__(config, state_factory=ResultReviewerState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[
                *RESULT_REVIEWER_BASE_TOOLS,    # module-level constant
                *self.config.extra_tools,      # externally injected (empty by default)
            ],
            loop=ResultReviewLoop(
                deterministic_rules=self.config.deterministic_rules,
            ),
        )

    async def run(
        self, task: dict, task_result: dict, execution_log: list[dict] | None = None
    ) -> dict:
        self.state.last_query = {"task": task, "task_result": task_result}
        input_msg = json.dumps({"task": task, "task_result": task_result, "execution_log": execution_log or []})
        raw = await self.agent.run(query=input_msg)
        result = SchemaValidator(validation_fn=validate_reviewer_decision).validate(raw)
        self.state.last_result = result
        return result
```
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
    QueryAnalystLoop,
    InformationDigestionLoop,
    ResultReviewLoop,
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

### Public API: `tinycua.agents`, `tinycua.config`, and agent-calling tools

```python
# Config types (from tinycua.config)
from tinycua.config import (
    AgentKind,
    TINYCUA_DEFAULT_MODEL,
    AgentConfigBase,
    QueryAnalystConfig,
    InformationDigesterConfig,
    TaskAnalyzerConfig,
    TaskAssessorConfig,
    TaskExecutorConfig,
    ResultReviewerConfig,
    PrimaryAgentConfig,
)

# Agent wrapper classes
from tinycua.agents import (
    # Base
    BaseAgentWrapper,
    # Factory (creates wrapper instances, not raw SDK Agents)
    create_agent,
    create_all_agents,
    # Wrapper classes
    QueryAnalyst,
    InformationDigester,
    TaskAnalyzer,
    TaskAssessor,
    TaskExecutor,
    ResultReviewer,
    PrimaryAgent,
)

# Runtime state
from tinycua.state.information import StateInformation

from tinycua.tools.agent_calls import (
    call_query_analyst,
    call_information_digester,
    call_task_analyzer,
    call_task_assessor,
    call_task_executor,
    call_result_reviewer,
    call_primary_agent,
)

# Factory creates wrapper class instances
query_analyst = create_agent(AgentKind.QUERY_ANALYST)
assert isinstance(query_analyst, QueryAnalyst)
# The composed SDK Agent loop is QueryAnalystLoop
assert isinstance(query_analyst.agent.config.loop, QueryAnalystLoop)

# With config overrides
custom_qa = create_agent(
    AgentKind.QUERY_ANALYST,
    config=QueryAnalystConfig(classification_labels=["direct", "team", "unknown"]),
)
assert custom_qa.classification_tool.labels == ["direct", "team", "unknown"]

# create_all_agents returns all seven wrapper instances
agents = create_all_agents()
assert len(agents) == 7
assert isinstance(agents[AgentKind.QUERY_ANALYST], QueryAnalyst)
```

`create_agent()` returns a TinyCUA wrapper class instance (e.g., `QueryAnalyst`),
not a raw SDK `Agent`. The wrapper composes the SDK `Agent` internally —
callers interact through the wrapper's `run()` method. The factory is responsible
for building the correct wrapper from the agent's config dataclass and attaching
custom loops through `Agent(loop=...)` inside `_build_agent()`.

### Loop type → Agent Mapping (Wrapper Class Configuration)

| Architecture Agent | Wrapper Class | Composed SDK Agent Config | Loop | Input | Output |
|-------|-------|------------------|--------------------|------------|-------------|
| Query Analyst | `QueryAnalyst` | Classification prompt + `ClassificationTool` | `loop=QueryAnalystLoop()` | `(user_query, chat_history, session_context)` | `{context_enhanced_query, mode_decision}` |
| Information Digester | `InformationDigester` | Digestion prompt + `enhanced_context_retrieval` SDK Tool | `loop=InformationDigestionLoop()` | `ContextEnhancedQuery` | `DigestedInformation` |
| Task Analyzer | `TaskAnalyzer` | Task analysis prompt + optional info tools | `loop=ReActAgentLoop()` | `DigestedInformation` | `Task` tree |
| Task Assessor | `TaskAssessor` | Assessment prompt | `loop=ReActAgentLoop()` | `Task` tree + `WorkerConfig` | `list[task_id]` selection |
| Task Executor | `TaskExecutor` | Execution prompt + native benchmark SDK Tools | `loop=ReActAgentLoop()` | `Task` | `TaskResult` |
| Result Reviewer | `ResultReviewer` | Review prompt + pluggable deterministic rules | `loop=ResultReviewLoop(...)` | `(task, task_result, execution_log)` | `ReviewerDecision` |
| Primary Agent | `PrimaryAgent` | Synthesis prompt + formatting/verification SDK Tools | `loop=ReActAgentLoop()` | `ContextEnhancedQuery` or `WorkerResult` | final response |

### Agent-to-Agent Calling Tool Contract

Each `call_*` helper is exposed as an SDK `Tool`. The tool implementation receives the target wrapper class instance (e.g., `QueryAnalyst`), calls `wrapper.run(...)`, validates the target schema, and returns the normalized output. It must not call the composed SDK `Agent` directly or bypass the target wrapper's `run()` method.

### MainLoop / TinyCUA Wrapper Contract

The future external `TinyCUA` wrapper class stores its dependencies as instance
attributes, **not** inside `agent.config.metadata`:

| TinyCUA attribute | Purpose |
|--------------|---------|
| `self.internal_agents` | Mapping from `AgentKind` to wrapper class instances |
| `self.state_store` | Structured session/continuation state store; SQLite-backed by default |
| `self.artifact_store` | Optional filesystem-backed storage for artifacts, snapshots, logs, attachments, or large/unstructured payloads |
| `self.config.agent_overrides` | Per-agent config overrides (classification labels, extra tools, deterministic rules) passed from TinyCUA config down to internal agent wrappers |

Internal agent wrapper classes follow the same pattern: each stores context
(`self.state`), config (`self.config`), and exposes `save_state(store)` /
`restore_state(store)`. This avoids polluting SDK `Agent.metadata` which is
opaque and hard to trace.

---

## Future Documentation Sync

This PR is spec/design-only and should not edit `src/tinycua/docs/architecture/` or `src/tinycua/docs/design/` yet. During implementation, both documentation sets should be synchronized:

### Architecture Docs

| Architecture Doc | Future Change |
|------------------|---------------|
| `overview.md` | Update the Agent Loop Types table so Task Analyzer and Task Assessor are mapped to `ReActAgentLoop` instead of a separate input→output / Linear / Simple loop type. |
| `task-analysis.md` | Clarify that Task Analyzer is a wrapper class composing an SDK `Agent` with default SDK `BaseLoop`; any single-output guarantee comes from prompt/schema validation around the composed `Agent.run()`. |
| `task-assessor.md` | Clarify that Task Assessor is a wrapper class composing an SDK `Agent` with default SDK `BaseLoop`; decomposition-selection output is schema-validated outside the loop. |
| Any architecture docs mentioning "Linear", "Simple", or "input→output" loop semantics | Normalize wording to distinguish `ReActAgentLoop` from true custom loop strategies. |

### Design Docs (new during implementation)

Create `src/tinycua/docs/design/` as the canonical reference for TinyCUA's concrete agent design:

| Design Doc | Content |
|------------|---------|
| `overview.md` | All wrapper classes, config dataclasses, wrapper-loop layer separation, agent-calling contracts |
| `query-analyst.md` | `QueryAnalyst` class, `QueryAnalystConfig`, `QueryAnalystLoop`, `ClassificationTool` |
| `information-digester.md` | `InformationDigester` class, `InformationDigesterConfig`, `InformationDigestionLoop`, retrieval tool contract |
| `task-analyzer.md` | `TaskAnalyzer` class, `TaskAnalyzerConfig`, `ReActAgentLoop` |
| `task-assessor.md` | `TaskAssessor` class, `TaskAssessorConfig`, `ReActAgentLoop` |
| `task-executor.md` | `TaskExecutor` class, `TaskExecutorConfig`, native tool contract, `ReActAgentLoop` |
| `result-reviewer.md` | `ResultReviewer` class, `ResultReviewerConfig`, `ResultReviewLoop`, deterministic rules |
| `primary-agent.md` | `PrimaryAgent` class, `PrimaryAgentConfig`, `ReActAgentLoop` |
| `agent-calls.md` | Agent-to-agent calling tools, how they receive wrapper instances |
| `tinycua-agent.md` | `TinyCUA` external wrapper contract, `MainLoop` integration |

### SDK Cookbook

| Doc | Change |
|-----|--------|
| `src/tinycua-sdk/docs/cookbook/execution-and-reference/custom-execution-loops.md` | Correct custom loop examples so loop instances are passed to `Agent(loop=...)`; clarify that `agent.run()` uses `agent.config.loop` or default `BaseLoop()`, not an unattached local `loop` variable. |

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

1c. **Decision**: The external TinyCUA runtime is a `TinyCUA` wrapper class that composes an SDK `Agent` with `MainLoop`. Dependencies (internal agent registry, state stores) are stored as wrapper instance attributes, NOT inside SDK `Agent.metadata`.
   - **Reason**: TINYCUA should be exposed as one wrapped agent (`TinyCUA(...).run(...)`) while internal agents remain implementation details. Wrapper instance attributes are typed, traceable, and never obscured by the SDK's opaque metadata dict. Internal agent wrappers follow the same pattern (`self.state`, `self.config`).
   - **Alternatives Considered**: Store all state in `Agent.metadata["tinycua"]` — rejected because it's opaque, hard to trace, and tightly couples TinyCUA's design to SDK internal data structures. Expose internal agents directly to users — rejected because it leaks orchestration internals. Implement MainLoop inside M2 — deferred because full resume behavior depends on session and worker orchestration milestones.

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
