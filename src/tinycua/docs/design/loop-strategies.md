# Loop Strategies

> **File:** `docs/design/loop-strategies.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **See also:** [`overview.md`](overview.md), [`base-agent-wrapper.md`](base-agent-wrapper.md)

---

## Overview

Every agent uses exactly one loop strategy. Loops extend SDK `BaseLoop` and are passed
into the composed SDK `Agent` via `Agent(loop=...)`. The wrapper class handles
pre-processing and post-processing; the loop handles execution strategy.

---

## Loop Hierarchy

```
tinycua_sdk.agent.loop.BaseLoop         (SDK — tool calling, streaming, cancellation)
├── ReActAgentLoop                      (shared — default ReAct behavior)
├── QueryAnalystLoop                    (classification control flow)
├── InformationDigestionLoop            (iterative retrieval + gap evaluation)
├── ResultReviewLoop                    (two-phase: deterministic + LLM review)
└── MainLoop                            (FUTURE M6 — full orchestration)
```

---

## ReActAgentLoop

**File:** `tinycua/loops/react_agent.py`
**Used by:** TaskAnalyzer, TaskAssessor, TaskExecutor, PrimaryAgent

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

**Why not use SDK `BaseLoop` directly?** `ReActAgentLoop` gives TinyCUA a single point
to add common behavior (logging hooks, telemetry, common overrides) across all simple
agents without touching each wrapper or depending on SDK `BaseLoop` internals.

---

## QueryAnalystLoop

**File:** `tinycua/loops/query_analyst_loop.py`
**Used by:** QueryAnalyst

Classification loop: high-level context scan → multi-dimensional scoring → one validated
`ModeDecision` output.

**Key behaviors:**
- Extends SDK `BaseLoop` with default iteration behavior (does NOT set `max_iterations=1`)
- The composed SDK `Agent` is configured with `ClassificationTool` (from `QUERY_ANALYST_BASE_TOOLS`)
- `SchemaValidator` validates the output against `ContextEnhancedQuery` + `ModeDecision`
- One structured classification result — the agent may iterate internally but produces one definitive output

**Why not `max_iterations=1`?** Forcing a one-pass loop can make the agent stop immediately
before the SDK loop has room to complete normal execution. Classification relies on prompt design
and schema validation to produce one result.

---

## InformationDigestionLoop

**File:** `tinycua/loops/information_digestion_loop.py`
**Used by:** InformationDigester

Iterative retrieval loop: identify information gaps → invoke Enhanced Context Retrieval →
evaluate relevance → retrieve again or stop.

**Key behaviors:**
- Extends SDK `BaseLoop`, overriding `run()` to add gap-evaluation between iterations
- Accepts optional `max_iterations` override at construction
- Primary stop condition: LLM judges sufficiency (parsed from output)
- Hard safety cap: `BaseLoop.max_iterations` (default 5, configurable)
- Empty retrieval results → `known_gaps` recorded in `DigestedInformation`

**Flow:**
```
Input CEQ → Identify gaps (LLM) → Retrieve (SDK Tool) → Evaluate (LLM)
                                                              │
                                        ┌─────────────────────┘
                                        │ Sufficient? → Yes → Output DigestedInformation
                                        │ No → loop back (up to max_iterations)
```

---

## ResultReviewLoop

**File:** `tinycua/loops/result_review_loop.py`
**Used by:** ResultReviewer

Two-phase review: deterministic checks first, then LLM semantic review.

**Key behaviors:**
- Constructor accepts `deterministic_rules: list[DeterministicRule]`
- **Phase 1:** Evaluate all deterministic rules. Any failure with severity `escalate` or `replan` → return immediately (skip Phase 2)
- **Phase 2:** Delegate to SDK `BaseLoop` for LLM semantic review
- Produces `ReviewerDecision` with status: `accepted`, `retry`, `replan`, `escalate_user`

**Deterministic rule contract:**
```python
@dataclass
class DeterministicRule:
    name: str
    check: Callable[[task, task_result, execution_log], DeterministicRuleResult]

@dataclass
class DeterministicRuleResult:
    passed: bool
    reason: str | None = None
    severity: str | None = None  # "escalate" | "replan"
```

Default rules provided: `SchemaValidity`, `RequiredFields`. Extensible via `ResultReviewerConfig.deterministic_rules`.

---

## MainLoop (Future M6)

**File:** `tinycua/loops/main_loop.py` (future)
**Used by:** `TinyCUA` external wrapper

Full orchestration loop: Query Analyst → route by `ModeDecision` → Primary Agent directly,
Information Digester + Worker Mode, or Uncertain Mode handling.

M2 defines the contract only. Implementation deferred to the top-level orchestration milestone
after session and worker orchestration foundations exist.

---

## Loop Input/Output

| Loop | Input | Output |
|------|-------|--------|
| ReActAgentLoop | Agent-specific (via wrapper `run()`) | Agent-specific (validated by wrapper `run()`) |
| QueryAnalystLoop | `{user_query, chat_history, session_context}` | `{context_enhanced_query, mode_decision}` |
| InformationDigestionLoop | `ContextEnhancedQuery` | `DigestedInformation` |
| ResultReviewLoop | `{task, task_result, execution_log}` | `ReviewerDecision` |

---

## Error Handling

All loops rely on SDK infrastructure — no custom retry logic:

| Error Case | SDK Behavior | Loop Responsibility |
|------------|-------------|---------------------|
| Transient LLM error | `LLMClient` handles retry/backoff | Propagate as `LoopTransientError` if exhausted |
| Permanent LLM error | SDK raises immediately | Propagate as `LoopPermanentError` |
| Output validation failure | `SchemaValidator` retries with error context | Raise `LoopOutputValidationError` after max retries |
| Invalid input | — | Raise `ValueError` before any LLM call |
| Tool call failure | `ToolExecutor` returns error as observation | LLM decides next action |

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Shared ReAct loop | `ReActAgentLoop`, not per-agent subclasses | Prevents unnecessary class hierarchy; wrapper provides identity |
| Custom loops extend BaseLoop directly | Not through ReActAgentLoop | Custom control flow is incompatible with plain ReAct |
| Classification no max_iterations=1 | Default SDK iteration | Single-pass can prematurely stop the agent |
| Pluggable deterministic rules | Constructor parameter | Different reviewer configs can use different rule sets without subclassing |
| Stop on sufficiency + hard cap | Both LLM-judged and count-based | LLM context-awareness + safety against infinite loops |
