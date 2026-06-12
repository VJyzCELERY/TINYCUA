# Design Document: TinyCUA ResponseNode — Optional Information Digestion Request

**Spec**: `./spec.md`
**Status**: Implemented
**Last Updated**: 2026-06-12

---

## Overview

This design formalizes the **TinyCUAResponseNode optional information digestion request** path — the integration contract between `TinyCUAResponseNode` and `TinyCUAInformationDigesterNode`. When `TinyCUAResponseNode` determines that accumulated context is insufficient for a quality final response, it suspends the queue, prepends an `InformationDigesterNode` (with `parent=TinyCUAResponseNode`), the digester gathers and digests additional context, propagates the digest back to the parent's `session_context`, and the queue advances so `TinyCUAResponseNode` resumes synthesis. The implementation already exists in `src/tinycua/tinycua/loops/response_node.py` and `src/tinycua/tinycua/loops/information_digester.py`; this design formally documents the contract.

---

## Architecture

### Component Overview

```
TinyCUALoop (queue iteration)
  │
  ├── ... previous nodes ...
  │
  ├── TinyCUAResponseNode.__call__(input)
  │     │
  │     ├── Phase 1: Build ResponseContext
  │     │     ├── Extract aggregated_result from session_context
  │     │     ├── Collect session_context messages
  │     │     └── Capture continuation_payload
  │     │
  │     ├── Phase 2: Context Sufficiency Check
  │     │     ├── Sufficient → skip to Phase 3
  │     │     ├── Insufficient + digester_enabled=True
  │     │     │     └── Set _needs_digestion=True
  │     │     │         Return placeholder LLMResult
  │     │     │         (Suspension deferred to on_complete)
  │     │     └── Insufficient + digester_enabled=False
  │     │           └── _gather_context_via_tools()
  │     │               → Phase 3
  │     │
  │     └── Phase 3: _synthesize_response(context)
  │           └── Return LLMResult (string content)
  │
  ├── on_complete(queue, response)
  │     ├── _needs_digestion=True?
  │     │     └── _suspend_for_digestion(context, queue)
  │     │           ├── Check max_digest_attempts
  │     │           ├── Create TinyCUAInformationDigesterNode(parent=self)
  │     │           └── queue.suspend_current_and_prepend([digester])
  │     └── _needs_digestion=False?
  │           └── No action (queue advances normally)
  │
  ├── TinyCUAInformationDigesterNode.__call__(input)
  │     ├── Ensure fresh Session()
  │     ├── Convert input to messages
  │     ├── Optionally invoke EnhancedContextRetrieval
  │     ├── _produce_digest(context) → LLMResult
  │     └── Return digest output
  │
  ├── on_complete(queue, response)
  │     ├── Propagate digest to parent.session_context
  │     └── queue.advance() → TinyCUAResponseNode resumes
  │
  └── `TinyCUAResponseNode` resumes
        ├── __call__ re-checks sufficiency
        └── Synthesizes final response
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `loops/response_node.py` | Modified (exists) | Three-phase execution, digester suspension, max-attempts guard |
| `loops/information_digester.py` | Modified (exists) | Fresh session, parent propagation, digest production |
| `loops/__init__.py` | Not Modified | Public exports unchanged |
| `config/node_config.py` | Not Modified | Metadata keys `digester_enabled`, `max_digest_attempts`, `sufficiency_threshold` already available via `NodeConfigBase` |
| `models/digested_information.py` | Not Modified | `DigestedInformation` dataclass already defined |
| `models/node_input.py` | Not Modified | `NodeInput`, `NodeInputLike` already defined |

---

## Data Model

### New Entities _(if applicable)_

No new entities. The existing `ResponseContext` (in `response_node.py`) and `DigestedInformation` (in `models/digested_information.py`) fully cover the data needs.

### Existing Entities (for reference)

```python
# `TinyCUAResponseNode` internal state
@dataclass
class ResponseContext:
    aggregated_result: AggregatedResult | None
    session_context: list[dict[str, Any]]
    latest_output: str | None
    continuation_payload: MandatoryPassthrough | None = None

# Digester output
@dataclass
class DigestedInformation:
    context_summary: str
    key_points: list[str] = field(default_factory=list)
    advisory_instructions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    known_gaps: list[str] = field(default_factory=list)
```

### Schema Changes _(if applicable)_

- `NodeConfigBase.metadata` accepts `digester_enabled` (bool), `max_digest_attempts` (int), and `sufficiency_threshold` (int, optional) — no schema changes needed, these are dynamic metadata keys.

---

## API / Interface Contracts

### Existing / Modified Functions

```python
# TinyCUAResponseNode (response_node.py)

def __call__(self, input: NodeInputLike) -> LLMResult:
    """
    Three-phase response generation.
    Phase 1: Build ResponseContext.
    Phase 2: Check sufficiency → digest request or tools or direct synthesis.
    Phase 3: Normalize and return.
    Returns LLMResult with string content.
    When context insufficient + digester enabled: sets _needs_digestion=True,
    returns placeholder LLMResult with metadata{"needs_digestion": True}.
    """

def on_complete(self, queue: NodeQueue, response: LLMResult | Any) -> None:
    """
    Post-completion hook.
    If _needs_digestion: calls _suspend_for_digestion to prepend digester.
    Otherwise: no-op (queue advances normally).
    """

def _suspend_for_digestion(self, context: ResponseContext, queue: NodeQueue) -> None:
    """
    Creates TinyCUAInformationDigesterNode(parent=self) and
    calls queue.suspend_current_and_prepend([digester]).
    Guards: max_digest_attempts (default 3) prevents infinite loops.
    """

def _check_context_sufficiency(self, context: ResponseContext) -> bool:
    """
    Returns True if:
    - aggregated_result is present with task_summaries or final_context, OR
    - session_context size >= configured sufficiency_threshold.
    """
```

```python
# TinyCUAInformationDigesterNode (information_digester.py)

def __init__(self, node_id="information_digester",
             config: NodeConfigBase | None = None,
             parent: ProcessNode | None = None) -> None:
    """
    Initialize with optional parent reference.
    Creates fresh session in __call__, never inherits parent's session.
    """

def __call__(self, input: NodeInputLike) -> LLMResult:
    """
    Context gathering and digestion.
    1. Ensure fresh Session().
    2. Convert input to messages.
    3. Optionally invoke EnhancedContextRetrieval.
    4. Produce structured digest via _produce_digest.
    5. Return LLMResult with digested information.
    """

def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
    """
    Post-completion hook.
    1. Propagate digest to parent.session_context.
     2. queue.advance() so parent (`TinyCUAResponseNode`) resumes.
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `max_digest_attempts` exceeded | No exception — logs warning, returns without suspending | Graceful degradation |
| Digester returns empty digest | ResponseNode resumes, attempts next cycle up to max | Configurable via metadata |
| `queue` is `None` in `on_complete` | Logs warning, no queue mutation | Defensive guard |
| LLM client unavailable in `_synthesize_response` | Returns `fallback_message` from metadata | Configurable fallback |
| LLM client unavailable in digester | Returns `"No LLM client configured."` | Default response |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [x] **TinyCUAResponseNode three-phase execution**: `__call__` builds context, checks sufficiency, branches to digest/tools/synthesis.
- [x] **Context sufficiency check**: `_check_context_sufficiency` with primary (aggregated result) and secondary (threshold) heuristics.
- [x] **Digester suspension in `on_complete`**: When `_needs_digestion=True`, delegates to `_suspend_for_digestion`.
- [x] **`_suspend_for_digestion` implementation**: Creates `TinyCUAInformationDigesterNode(parent=self)`, calls `queue.suspend_current_and_prepend`.
- [x] **`max_digest_attempts` guard**: Configurable limit (default 3) to prevent infinite suspend/resume loops.
- [x] **`digester_enabled=False` fallback**: Falls through to `_gather_context_via_tools` placeholder.
- [x] **InformationDigesterNode integration**: Accepts parent, creates fresh session, produces digest, propagates to parent.
- [x] **Digest propagation**: `on_complete` appends digest to parent's `session_context`, calls `queue.advance()`.
- [x] **Resumption**: TinyCUAResponseNode re-evaluates context on next `__call__`, synthesizes if sufficient.
- [x] **Integration tests**: Digester suspension flow tested in `test_response_node_integration.py`.

### Phase 2 — Enhancements _(post-MVP, deferred to Milestones 4.x)_

- [ ] **Full `EnhancedContextRetrieval` implementation** (Milestone 4.2): Replace placeholder with actual ReAct-style search over scoped context cache.
- [ ] **Tool scoping**: Restrict digester tool access to `enhanced_context_retrieval` and `digest_information` only (Milestone 4.2).
- [ ] **Streaming/transcript events**: Expose digestion events in the loop transcript (Milestone 4.4).
- [ ] **Propagation dedupe**: Avoid re-appending duplicate digest entries on repeated cycles (Milestone 4.1).

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Defer suspension from `__call__` to `on_complete`.
   - **Reason**: Separates concerns — `__call__` determines *whether* digestion is needed, `on_complete` handles the queue mutation. This keeps `__call__` idempotent and testable without a queue dependency.
   - **Alternatives Considered**: Suspending directly in `__call__` — rejected because it would require passing the queue to `__call__` and make unit testing more complex.

2. **Decision**: Digester creates a **fresh session** rather than inheriting the parent's session.
   - **Reason**: Prevents context pollution — the digester should operate on a scoped, clean context without accidentally modifying the parent's session data. The parent passes selected context via `NodeInput`.
   - **Alternatives Considered**: Inheriting parent session — rejected because it violates separation of concerns and risks accidental cross-contamination.

3. **Decision**: Use `max_digest_attempts` (default 3) as a simple counter, not a time-based or quality-based threshold.
   - **Reason**: Simple, testable, predictable. Keeps the MVP straightforward. Quality-based thresholds (e.g., "stop when digest quality score > 0.8") are deferred to post-MVP.
   - **Alternatives Considered**: TTL-based, quality-based — rejected for MVP complexity.

4. **Decision**: `ResponseContext` is built fresh in `_build_response_context` rather than cached across calls.
   - **Reason**: Context may change between calls (e.g., after digestion, new entries appear in `session_context`). Fresh construction ensures the sufficiency check always operates on the latest data.
   - **Alternatives Considered**: Caching `ResponseContext` — rejected because it risks stale data.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Infinite suspend/resume loop (digester → insufficient → digester → ...) | Low | High | `max_digest_attempts` guard (default 3) prevents looping. |
| Digester pollutes parent session context | Low | Medium | Digester creates a fresh session; only the final digest output is propagated to the parent. |
| Queue mutation (`suspend_current_and_prepend`) fails | Low | High | `on_complete` handles `queue=None` gracefully; all mutation is in a single call. |
| `_gather_context_via_tools` is a placeholder | Medium | Low | Falls back to existing context; synthesis produces a warning-logged response with whatever context is available. |
| Digest is empty/malformed on propagation | Low | Medium | ResponseNode re-evaluates sufficiency; if still insufficient, another digestion cycle may be attempted (up to max). |

---

## Open Questions _(optional)_

1. **Should `TinyCUAResponseNode` select a subset of `session_context` for the digester's input, or pass the full context?**
   - Current implementation passes messages via `NodeInput` (built in `_build_response_context`) per FR-005/FR-006. Selection refinement deferred to Milestone 4.1.

---

## References

- Spec: `./spec.md`
- Design docs: `src/tinycua/docs/design/loops/response.md`, `src/tinycua/docs/design/tools/digester.md`, `src/tinycua/docs/design/loops/node_queue.md`
- Implementation: `src/tinycua/tinycua/loops/response_node.py`, `src/tinycua/tinycua/loops/information_digester.py`
- Config: `src/tinycua/tinycua/config/node_config.py`
- Tests: `src/tinycua/tests/integration/test_response_node_integration.py`, `src/tinycua/tests/unit/test_response_node.py`
- Issue: [#87](https://github.com/VJyzCELERY/TINYCUA/issues/87) — Roadmap: TinyCUA Prototype for WildClawBench Harness Evaluation (Milestone 3.6)
