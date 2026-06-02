# Design Document: M3 Agent Custom Loops

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Last Updated**: 2026-06-02

---

## Overview

This design defines the `tinycua.loops` package — a suite of custom SDK `BaseLoop` subclasses architected around a shared `ReActLoop` base. Each TinyCUA agent type (QueryAnalyst, InformationDigester, TaskAnalyzer, TaskAssessor, TaskExecutor, ResultReviewer, PrimaryAgent) gets its own loop subclass that enforces mandatory tool calls, captures structured `AgentState` output, and yields deterministic `tinycua.final_result` events. All loops follow a consistent `run()` signature, share retry helpers via `ReActLoop`, and keep agent instruction strings in a separate `constants/instructions.py` module.

**Subprojects affected**: `tinycua` (new `loops/` package, new `constants/` module)

**Key architectural decisions**:
- `ReActLoop(BaseLoop)` as the shared base, storing `session` and providing common retry/event-passthrough helpers.
- Seven agent-specific loops, each overriding only what differs (required tool enforcement, output formatting, termination rules).
- Agent instructions live in `tinycua.constants.instructions` — never embedded in loop code.

---

## Architecture

### Component Overview

```
tinycua.loops
├── react_loop.py                 ← ReActLoop(BaseLoop)
├── query_analyst_loop.py         ← QueryAnalystLoop(ReActLoop)
├── information_digestion_loop.py ← InformationDigestionLoop(ReActLoop)
├── task_analyzer_loop.py         ← TaskAnalyzerLoop(ReActLoop)
├── task_assessor_loop.py         ← TaskAssessorLoop(ReActLoop)
├── task_executor_loop.py         ← TaskExecutorLoop(ReActLoop)
├── result_review_loop.py         ← ResultReviewLoop(ReActLoop)
├── primary_agent_loop.py         ← PrimaryAgentLoop(ReActLoop)
└── __init__.py                   ← re-exports all loop classes

tinycua.constants
└── instructions.py               ← AGENT_INSTRUCTION string constants
```

### Loop-to-Session Data Flow

```
AgentNode creates:
    Agent(..., loop=SpecificLoop(session=self.session))

SDK Agent.run() calls:
    loop.run(agent, messages, tools, override_instructions, stream)

Inside loop.run():
    1. Delegate to SDK BaseLoop._run_sync / _run_stream
    2. Observe events: tool calls, text responses, errors
    3. Enforce mandatory tool calls via retry
    4. Build AgentState subclass
    5. self.session.agent_state = agent_state
    6. Yield tinycua.final_result event
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops` package | New | Package with `__init__.py` re-exporting all loops |
| `tinycua.loops.react_loop` | New | `ReActLoop(BaseLoop)` — shared base with session, retry helpers |
| `tinycua.loops.query_analyst_loop` | New | `QueryAnalystLoop` — classification enforcement |
| `tinycua.loops.information_digestion_loop` | New | `InformationDigestionLoop` — digest tool enforcement |
| `tinycua.loops.task_analyzer_loop` | New | `TaskAnalyzerLoop` — summary capture |
| `tinycua.loops.task_assessor_loop` | New | `TaskAssessorLoop` — verdict enforcement |
| `tinycua.loops.task_executor_loop` | New | `TaskExecutorLoop` — task inspection |
| `tinycua.loops.result_review_loop` | New | `ResultReviewLoop` — decision & open-question |
| `tinycua.loops.primary_agent_loop` | New | `PrimaryAgentLoop` — final response |
| `tinycua.constants.instructions` | New | `instructions.py` with all agent instruction strings |

---

## Data Model

### New / Referenced AgentState Subclasses

Each loop writes a corresponding `AgentState` subclass. These are already defined in `tinycua.state` (M2 deliverable) or will be created alongside the loops:

```python
# Referenced state shapes (actual classes in tinycua.state.*)

@dataclass
class QueryAnalystState(AgentState):
    type: str = "query_analyst"           # agent identifier
    status: AgentStatus = "terminated"
    failure: int = 0                      # 1 if fallback was used
    classification: str | None = None     # selected label
    context: str = ""                     # first assistant response text
    query: str = ""                       # original user query

@dataclass
class InformationDigesterState(AgentState):
    type: str = "information_digester"
    status: AgentStatus = "terminated"
    failure: int = 0
    context_summary: str = ""
    key_points: list[str] = field(default_factory=list)
    advisory_instructions: str | None = None
    constraints: list[str] | None = None
    known_gaps: list[str] | None = None
    retrieval_iterations: int = 0

@dataclass
class TaskAnalyzerState(AgentState):
    type: str = "task_analyzer"
    status: AgentStatus = "terminated"
    failure: int = 0
    analysis_summary: str = ""

@dataclass
class TaskAssessorState(AgentState):
    type: str = "task_assessor"
    status: AgentStatus = "terminated"
    failure: int = 0
    verdict: str = ""                     # "analyze" | "stop"
    analysis: str = ""                    # first assistant response text

@dataclass
class TaskExecutorState(AgentState):
    type: str = "task_executor"
    status: AgentStatus = "running"       # non-terminal by default
    failure: int = 0
    task_id: str | None = None
    task_result: TaskResult | None = None
    execution_attempts: int = 0
    tool_results: list[dict] = field(default_factory=list)

@dataclass
class ResultReviewerState(AgentState):
    type: str = "result_reviewer"
    status: AgentStatus = "running"       # non-terminal until decision made
    failure: int = 0
    decision: str | None = None           # "accept" | "retry" | "replan"
    reason: str = ""
    context_updates: list[dict] = field(default_factory=list)
    retry_instructions: str | None = None

@dataclass
class PrimaryAgentState(AgentState):
    type: str = "primary_agent"
    status: AgentStatus = "terminated"
    failure: int = 0
    final_response: str = ""
    citations: list[str] = field(default_factory=list)
```

---

## API / Interface Contracts

### ReActLoop (base class)

```python
class ReActLoop(BaseLoop):
    """
    Shared base for all TinyCUA custom loops.

    Extends SDK BaseLoop, stores a Session reference, and provides
    common helpers for event passthrough, retry, and final-result emission.
    """

    def __init__(self, session: Session, max_iterations: int = 25):
        """
        Args:
            session: The TinyCUA session for this agent invocation.
            max_iterations: Max LLM iterations before forced termination.
        """
        super().__init__(max_iterations=max_iterations)
        self.session = session

    async def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]:
        """Delegates to SDK BaseLoop.run() for standard ReAct behavior.

        Subclasses override this method to add enforcement, observation,
        and state writing logic.
        """
        ...

    # --- Shared helpers for subclasses ---

    async def _retry_with_prompt(
        self,
        agent: Agent,
        working: list[dict],
        tools: list[Tool],
        retry_prompt: str,
        max_retries: int,
        is_valid_fn: Callable[[dict], bool],
    ) -> tuple[dict | None, int]:
        """Send an in-memory retry prompt, return the response.

        Loop-internal — retry messages are NOT appended to chat_history
        or session.context.

        Returns:
            Tuple of (valid_response_or_None, retries_used).
        """
        ...

    async def _emit_final_result(
        self,
        agent: Agent,
        agent_state: AgentState,
        stream: bool,
    ) -> dict:
        """Write agent_state to session and yield/normalize final-result event.

        Sets self.session.agent_state = agent_state, then yields
        {"type": "tinycua.final_result", "agent": ..., ...}.

        In non-streaming mode, returns the event dict instead.
        """
        ...

    @staticmethod
    def _observe_tool_call(
        events: list[dict],
        tool_name: str,
    ) -> dict | None:
        """Find the last tool call/result for *tool_name* in observed events.

        Returns the tool result dict, or None if not found.
        """
        ...

    @staticmethod
    def _first_assistant_text(working: list[dict]) -> str:
        """Get the first assistant message text from working messages."""
        ...
```

### Per-Loop Constructor Defaults

| Loop | Additional `__init__` params | Default |
|------|------------------------------|---------|
| `QueryAnalystLoop` | `max_classification_retries: int` | `3` |
| `InformationDigestionLoop` | `max_digest_retries: int` | `3` |
| `TaskAssessorLoop` | `max_verdict_retries: int` | `3` |
| `ResultReviewLoop` | `max_review_retries: int` | `3` |
| `TaskAnalyzerLoop` | *(none beyond session)* | — |
| `TaskExecutorLoop` | *(none beyond session)* | — |
| `PrimaryAgentLoop` | *(none beyond session)* | — |

### Common Error Handling

| Error Case | Response |
|------------|----------|
| Missing mandatory tool call (classification, digest, verdict, review decision) | Retry up to budget, then fallback with `failure=1` |
| All retries exhausted | AgentState with `failure=1`, terminal final-result event emitted |
| LLM stream error / cancellation | `asyncio.CancelledError` propagated; caller handles |
| Tool execution error | Observed for failure accounting; loop continues unless error blocks progress |
| No active task (TaskExecutor) | `status="running"` — non-terminal |

---

## Instruction Architecture

Agent instructions are **not embedded** in loop code. They live in a dedicated module:

```
tinycua/constants/instructions.py
```

```python
QUERY_ANALYST_INSTRUCTION = """You are a query analyst. Your job is to classify
the user's request into one of the available modes using the classification tool.
..."""

INFORMATION_DIGESTER_INSTRUCTION = """You are an information digester. Your job
is to gather and digest context from the session. ..."""

TASK_ANALYZER_INSTRUCTION = """You are a task analyzer. Your job is to decompose
the user's request into tasks. ..."""

TASK_ASSESSOR_INSTRUCTION = """You are a task assessor. Your job is to determine
whether task analysis should continue or stop. ..."""

TASK_EXECUTOR_INSTRUCTION = """You are a task executor. Use tools to complete
your assigned task. ..."""

RESULT_REVIEWER_INSTRUCTION = """You are a result reviewer. Your job is to review
task results and decide: accept, retry, or replan. ..."""

PRIMARY_AGENT_INSTRUCTION = """You are the primary agent. Synthesize all worker
results into a final response for the user. ..."""
```

Each AgentNode references the instruction by constant name when constructing the SDK Agent:

```python
Agent(
    instructions=QUERY_ANALYST_INSTRUCTION,
    tools=[classification_tool],
    loop=QueryAnalystLoop(session=self.session),
)
```

### Loop Output Parsing and Validation

A shared `helpers` module (`tinycua.loops.helpers`) provides parsing and validation utilities used across loops:

```python
# tinycua.loops.helpers

def parse_classification_result(
    events: list[dict],
    valid_labels: list[str],
) -> str | None:
    """Extract the classification label from tool result events.

    Returns the label if it matches a valid label, else None.
    """

def parse_verdict_result(
    events: list[dict],
) -> str | None:
    """Extract the assessor verdict ('analyze' or 'stop') from tool results."""

def parse_digest_result(
    events: list[dict],
) -> DigestedInformation | None:
    """Parse a digest_information tool result into DigestedInformation."""

def collect_tool_results(
    events: list[dict],
) -> list[dict]:
    """Collect all tool result dicts from a stream of events."""
```

---

## Loop Behavior Summary

### QueryAnalystLoop

1. Run SDK pass with `messages`, `tools`, `override_instructions`.
2. If `stream=True`, yield every SDK event outward.
3. Preserve first assistant text as `context`.
4. Detect `ClassificationTool` result — extract label.
5. Label found → write `QueryAnalystState(failure=0)`, emit final-result.
6. Label missing + retry budget → send in-memory retry prompt.
7. Still missing after retries → fallback to `config.classification_labels[0]`, `failure=1`.

### InformationDigestionLoop

1. Run SDK pass.
2. Observe `enhanced_context_retrieval` calls (count as iterations).
3. Parse `digest_information` tool output into `latest_digest`.
4. Digest exists → write `InformationDigesterState(failure=0)`.
5. Missing + retry budget → retry with in-memory prompt.
6. Still missing → partial state with `failure=1`, known gaps noted.

### TaskAnalyzerLoop

1. Run SDK pass with task tools.
2. Observe task tool failures → increment `failure`.
3. Capture final assistant text as `analysis_summary`.
4. Append summary + tool metadata to session per policy.
5. Write `TaskAnalyzerState`, emit final-result.

### TaskAssessorLoop

1. Run SDK pass.
2. Preserve first assistant text as `analysis`.
3. Observe classification tool result as `verdict` (`analyze` | `stop`).
4. Verdict missing → retry (do NOT replace `analysis`).
5. Still missing → fallback to `stop`, `failure=1`.
6. Write `TaskAssessorState`, emit final-result.

### TaskExecutorLoop

1. Run SDK pass with TaskExecutor tools.
2. Observe tool results for audit + failure accounting.
3. After SDK pass, inspect `session.get_active_task()` / `session.task`.
4. Active task `TaskResult.status`:
   - `completed` → `status="terminated"` (terminal)
   - `failed` → `status="terminated"`, increment `failure`
   - `blocked` → `status="blocked"` (terminal)
   - `inprogress` / `not_started` / missing → `status="running"` (non-terminal)
5. Write `TaskExecutorState`. Emit final-result only when terminal.

### ResultReviewLoop

1. Run SDK pass with reviewer tools.
2. Observe reviewer classification tool → `decision` (`accept` | `retry` | `replan`).
3. Observe `ReviewContextUpdateTool` and `UpdateActiveTaskResult`.
4. Decision present:
   - `accept` → terminal, record context updates.
   - `retry` → terminal, ensure retry instructions present.
   - `replan` → terminal, signal orchestrator to re-route.
5. No decision + open question → non-terminal, no final event.
6. No decision + no open question → retry up to budget, then fallback.

### PrimaryAgentLoop

1. Run SDK pass.
2. Capture final assistant response text.
3. Extract citations from tool results / response metadata.
4. Append final response to session history/context.
5. Write `PrimaryAgentState`, emit final-result.

---

## No-HITL Semantics

All loops operate in No-HITL mode — they never wait for human input. The possible terminal outcomes are:

| Outcome | Meaning |
|---------|---------|
| `failure=0`, `status="terminated"` | Success — agent completed its task |
| `failure=1`, `status="terminated"` | Degraded — fallback was used (e.g., default classification, partial digest) |
| `status="blocked"` | Agent determined work cannot proceed (e.g., missing prerequisite) |
| `status="running"` | Non-terminal — agent is still active (TaskExecutor mid-execution, ResultReviewer with open question) |

When retries are exhausted, the loop **must** produce a terminal event with `failure=1` rather than looping indefinitely or awaiting human input.

---

## Implementation Phases

### Phase 1 — Core Infrastructure

- [x] Design docs for all 8 loops exist (`docs/design/loops/`)
- [ ] Create `tinycua.loops` package with `__init__.py`
- [ ] Implement `ReActLoop` base class with retry helpers and final-result emission
- [ ] Create `tinycua.constants.instructions` module with all instruction strings
- [ ] Implement loop output parsing helpers (`tinycua.loops.helpers`)

### Phase 2 — Agent-Specific Loops

- [ ] Implement `QueryAnalystLoop`
- [ ] Implement `InformationDigestionLoop`
- [ ] Implement `TaskAnalyzerLoop`
- [ ] Implement `TaskAssessorLoop`
- [ ] Implement `TaskExecutorLoop`
- [ ] Implement `ResultReviewLoop`
- [ ] Implement `PrimaryAgentLoop`

### Phase 3 — Testing & Integration

- [ ] Unit tests for `ReActLoop` base
- [ ] Unit tests for each agent-specific loop
- [ ] Integration tests with mock LLM
- [ ] Streaming integration tests
- [ ] Retry/fallback boundary tests

> **Note**: Phase 2 and 3 must NOT begin until Phase 1 is complete and reviewed. Phases 2 and 3 may run partially in parallel (implement one loop, test it, move to the next).

---

## Technical Decisions

1. **Decision**: `ReActLoop` as shared base rather than each loop extending `BaseLoop` directly.
   - **Reason**: Avoids duplicating session storage, retry helpers, and final-result emission logic across 7 loops. Gives a single place to update common behavior.
   - **Alternatives Considered**: Mixin class — rejected because Python MRO with SDK `BaseLoop` is simpler with explicit inheritance. Standalone utility functions — rejected because loops need access to `self.session` and shared state.

2. **Decision**: Agent instructions in `constants/instructions.py`, not embedded in loop code.
   - **Reason**: Instructions are prompt-engineering artifacts that evolve independently from loop logic. Separating them avoids recompiling/re-testing loop code when prompts change. Also allows different configurations (e.g., worker effort levels) to reference different instruction sets.
   - **Alternatives Considered**: Instructions as class attributes on loops — rejected because it couples prompt content to code structure. Instructions in config files — rejected because they are strings that need Python-constant import by AgentNode.

3. **Decision**: Retry prompts are in-memory only by default.
   - **Reason**: Retry nudges are technical corrections, not user-facing conversation turns. Appending them to `chat_history` would pollute the session record and confuse downstream agents. The loop may choose to persist them for specific agents (e.g., debug mode), but the default is no persistence.
   - **Alternatives Considered**: Always persist — rejected because it pollutes history. Never retry — rejected because it would cause unnecessary failures.

4. **Decision**: Each loop has its own `max_*_retries` parameter with a default, rather than a single global retry count.
   - **Reason**: Different agents have different tolerance for missing tool calls. Classification (QueryAnalyst) is cheap to retry; review decisions (ResultReviewer) may need more leeway. Per-loop defaults let each agent be tuned independently.
   - **Alternatives Considered**: Single global `max_iterations` — rejected because it conflates LLM iteration limits with tool-specific retry budgets.

5. **Decision**: `TaskExecutorLoop` inspects `session.get_active_task()` after the SDK pass rather than parsing task tool results from events.
   - **Reason**: The authoritative task state is in `session.task` after `UpdateActiveTaskResult` executes. Parsing tool call/result pairs from events would be less reliable and would duplicate state that already exists.
   - **Alternatives Considered**: Event-based tracking — rejected because it's fragile and duplicates the canonical state.

6. **Decision**: `ResultReviewLoop` supports non-terminal open-question behavior.
   - **Reason**: The reviewer may ask clarifying questions that require the user to respond. The loop stays active (no terminal event) until a decision is made. This is the one exception to "always terminate" — but it still never blocks (the orchestrator decides when to resume).
   - **Alternatives Considered**: Force a decision every time — rejected because it would force the reviewer to guess when information is insufficient.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SDK `BaseLoop` internal methods change between SDK versions | Low | High | Limit coupling to the public `run()` contract and documented helpers (`build_system_message`, `process_tool_calls`). Pin SDK version in tests. |
| Loops silently swallow streaming events | Medium | High | Each loop must be tested with a streaming mock to verify all SDK events are yielded. Add integration test that captures and asserts the full event sequence. |
| Retry logic causes infinite loops | Low | High | Hard cap on retries per loop (configurable default). Max iterations on the SDK loop itself. Both safeguards must be tested. |
| `TaskExecutorLoop` misses a terminal task status due to race conditions | Low | Medium | The authoritative read of `session.task` happens synchronously after the SDK pass completes — no race possible within a single `run()` call. |
| Agent instructions become outdated vs loop enforcement (e.g., instruction says one tool, loop enforces another) | Medium | Low | Instructions and loop enforcement reference the same tool names. Code review must verify alignment. Add a unit test that checks instruction text references the expected tool names. |

---

## References

- Spec: [./spec.md](./spec.md)
- Loop design docs: `docs/design/loops/`
  - [Overview](../../docs/design/loops/overview.md)
  - [ReActLoop](../../docs/design/loops/react_agent.md)
  - [QueryAnalystLoop](../../docs/design/loops/query_analyst_loop.md)
  - [InformationDigestionLoop](../../docs/design/loops/information_digestion_loop.md)
  - [TaskAnalyzerLoop](../../docs/design/loops/task_analyzer_loop.md)
  - [TaskAssessorLoop](../../docs/design/loops/task_assessor_loop.md)
  - [TaskExecutorLoop](../../docs/design/loops/task_executor_loop.md)
  - [ResultReviewLoop](../../docs/design/loops/result_review_loop.md)
  - [PrimaryAgentLoop](../../docs/design/loops/primary_agent_loop.md)
- SDK: `tinycua_sdk.agent.loop.BaseLoop`
- State objects: `tinycua.state.*`
