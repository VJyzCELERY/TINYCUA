# Design Document: TinyCUAResponseNode

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-12 (review fixes applied)

---

## Overview

Implement the full `TinyCUAResponseNode` as the terminal `ProcessNode` for the TinyCUALoop. The current `ResponseNode` is a basic stub that captures LLM output but lacks context sufficiency analysis, digester suspension, direct tool access, and consolidated continuation routing. This design fills those gaps to produce a hardened terminal node.

**Subproject(s) affected**: `tinycua` — `tinycua/loops/response_node.py` and related config/policy files.

**Key architectural decision**: ResponseNode processes in three phases — (1) context sufficiency analysis, (2) optional context gathering (digester or tools), (3) final response synthesis — before returning terminal output.

---

## Architecture

### Component Overview

```
AggregatedResult ─┐
PropagatedOutput ─┤
Session Context ──┤
                  ▼
         ┌─────────────────┐
         │  ResponseNode    │
         │  (ProcessNode)   │
         │  is_terminal=True│
         └────────┬────────┘
                  │
        ┌─────────▼──────────┐
        │ Context Sufficiency │
        │ Check               │
        └─────────┬──────────┘
                  │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
  Sufficient   Insufficient  Insufficient
               + Digester    - Digester
     │            │            │
     ▼            ▼            ▼
  Synthesize  Suspend &     Direct Tool
  Response    Prepend       Fallback
              Digester
                  │
        ┌─────────▼──────────┐
        │ Terminal Output     │
        │ (normalized string) │
        └────────────────────┘
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/response_node.py` | Modified | Full implementation of TinyCUAResponseNode |
| `tinycua/loops/node.py` | Modified (if needed) | May need ProcessNode hooks for suspension |
| `tinycua/config/node_config.py` | Modified (if needed) | May need response-specific config options |
| `tinycua/loops/node_queue.py` | Unchanged | Suspension already implemented in M1.7 |
| `tinycua/loops/tinycua_loop.py` | Modified (if needed) | Loop may need to handle ResponseNode suspension |
| Tests | New | Unit + integration tests for ResponseNode |

---

## Data Model

### New Entities

```python
# ResponseContext: Aggregated context fed into ResponseNode
ResponseContext:
    aggregated_result: AggregatedResult | None  # from ResultAggregationNode
    session_context: list[dict[str, Any]]        # propagated context
    latest_output: str | None                    # latest node output
    continuation_payload: dict | None            # user continuation data
```

### Schema Changes

No schema changes to existing entities. The existing `AggregatedResult`, `NodeInput`, and `NodePayload` data models are sufficient.

---

## API / Interface Contracts

### ResponseNode

```python
class TinyCUAResponseNode(ProcessNode):
    """
    Terminal ProcessNode that produces final user-facing response.
    
    Three-phase execution:
      1. Context sufficiency check
      2. Optional context gathering (digester/tools)
      3. Final response synthesis
    """
    
    def __init__(
        self,
        node_id: str = "response",
        config: NodeConfigBase | None = None,
    ) -> None:
        """
        Args:
            node_id: Identifier for this node (default: "response").
            config: Node configuration. Digester enable/disable is configured via
                    config.metadata["digester_enabled"] (default: True).
        """
    
    def __call__(self, input: NodeInputLike) -> LLMResult: ...
    
    def _check_context_sufficiency(self, context: ResponseContext) -> bool: ...
    
    def _suspend_for_digestion(self, context: ResponseContext) -> None: ...
    
    def _gather_context_via_tools(self, context: ResponseContext) -> ResponseContext: ...
    
    def _synthesize_response(self, context: ResponseContext) -> LLMResult: ...
    
    def on_complete(self, queue: NodeQueue, response: LLMResult | DecisionResult) -> None:
        """Called by queue after execution with the response for queue mutations."""
```

### Error Handling

| Error Case | Exception / Behavior | Notes |
|------------|---------------------|-------|
| Retry exhaustion | Falls through per NodeRetryPolicy | Returns last error message or fallback |
| Empty context | Falls back to digester or tools | Never silently returns empty |
| Digester unavailable | Falls back to direct tools | Graceful degradation |
| Digester returns no context | Proceeds with available context | Logs warning, synthesizes what it has |

---

### Tool Policy Configuration

ResponseNode integrates with `NodeToolPolicy` (defined in `tinycua/config/node_config.py`) to satisfy FR-009. The policy is configured as follows:

```python
from tinycua.config.node_config import NodeConfigBase, NodeToolPolicy

config = NodeConfigBase()
config.tool_policy = NodeToolPolicy(
    node_tools=[],              # No response-specific tools yet
    include_agent_tools="all",  # Share same toolset as TaskExecutor
)
```

This configuration:
- Passes all outer agent tools through to ResponseNode via `resolve_tools()`
- Allows the loop to apply the same tool filtering (allow/deny lists) as TaskExecutor
- Uses the same `NodeToolPolicy.include_agent_tools` mechanism already tested in M3.x nodes (see InformationDigesterNode for the inverse pattern — `include_agent_tools="none"`)

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] **ResponseContext helper**: Build context aggregation from NodeInput
- [ ] **Context sufficiency check**: Implement analysis logic with configurable thresholds
- [ ] **Direct synthesis path**: When context is sufficient, build LLM input and produce final response
- [ ] **Digester suspension path**: When enabled and context insufficient, suspend and prepend InformationDigesterNode; resume after digest returns
- [ ] **Direct tool fallback**: When digester unavailable, allow ResponseNode to use tools directly
- [ ] **Terminal normalization**: Ensure output is always a normalized string
- [ ] **Retry compliance**: Integrate with existing NodeRetryPolicy
- [ ] **Continuation routing**: Handle MandatoryPassthrough for continuation delivery

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] **Streaming output mode**: Wire `NodeStreamPolicy` configuration into ResponseNode to emit streamed output. The config infrastructure (`NodeStreamPolicy` on `NodeConfigBase`) already exists, but ResponseNode-specific stream event wiring and user-facing stream output are deferred until a future milestone.
- [ ] Information-digester suspension path to gather additional context mid-response (deferred to milestone 3.6 per roadmap)

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Three-phase execution (sufficiency check → gather → synthesize)
   - **Reason**: Clean separation of concerns matches the design doc. Sufficiency check is a lightweight analysis before any expensive LLM or tool calls.
   - **Alternatives Considered**: Single-phase "just call LLM with all context" — rejected because it doesn't support the suspension/fallback patterns required by the architecture.

2. **Decision**: Digester suspension uses existing `suspend_current_and_prepend` from M1.7
   - **Reason**: No new queue machinery needed. The suspension API is already implemented and tested.
   - **Alternatives Considered**: Custom suspension logic in ResponseNode — rejected to avoid duplicating queue infrastructure.

3. **Decision**: ResponseNode uses same base toolset as TaskExecutor via `NodeToolPolicy`
   - **Reason**: FR-009 requires ResponseNode to share the same tool scope as TaskExecutor. The existing `NodeConfigBase.tool_policy: NodeToolPolicy` already provides the resolution mechanism.
   - **Implementation**: Configure `NodeToolPolicy(include_agent_tools="all")` on the ResponseNode config. This passes all outer agent tools through (subject to any deny list), giving ResponseNode the same tool access as TaskExecutor. The `resolve_tools()` method on `NodeToolPolicy` handles the filtering, and the result is passed to the LLM as available tools.
   - **Alternatives Considered**: Dedicated response-only toolset — rejected per spec requirement.

4. **Decision**: Context sufficiency thresholds are configurable via NodeConfig
   - **Reason**: Different use cases may require different sufficiency criteria. Making it configurable avoids hardcoding a brittle heuristic.
   - **Alternatives Considered**: Hardcoded threshold — simpler but not flexible enough for research prototyping.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Digester suspension may produce infinite loops (digester → response → digester) | Low | High | Guard with max-digest-attempts counter in NodeConfig; reset on tool-gathered context |
| Context sufficiency heuristic may be wrong | Medium | Medium | Make thresholds configurable; log sufficiency decisions for tuning |
| Continuation routing may conflict with existing MandatoryPassthrough | Low | Medium | Test continuation paths thoroughly; existing M3.3 tests provide baseline |
| Tool use during response may have side effects | Low | Low | Same tools as TaskExecutor, already designed for safe execution |

---

## Open Questions _(optional)_

1. **What exactly constitutes "sufficient" context?**
   - **Decided**: Sufficiency = `aggregated_result is not None` AND (`task_summaries` is non-empty OR `final_context` is non-empty). This provides a clear, testable criterion for implementation.
   - **Rationale**: This definition aligns with the spec's proposed answer and ensures we have meaningful data to synthesize a response from.
   - **Implementation**: `_check_context_sufficiency()` checks `aggregated_result.task_summaries` and `aggregated_result.final_context` for non-emptiness.
   - Status: Decided

2. **Should retry exhaustion during synthesis return a fallback message or raise?**
   - **Decided**: Return a configurable fallback message (e.g., "I encountered an error generating the final response.") rather than raising, to maintain graceful terminal behavior as the terminal node.
   - **Rationale**: As the terminal node, ResponseNode must always produce output. Raising `NodeExecutionError` would break the queue and leave the user with no response. A fallback message (configurable via `NodeConfig.metadata["fallback_message"]`) is the safer, user-friendly choice.
   - **Implementation**: Set `NodeRetryPolicy.on_retry_exhausted = "record_failure"` so the last response is preserved. If that response is empty or invalid, synthesize the fallback message as the final `LLMResult.content`.
   - **Status**: Decided

---

## References

- Spec: `./spec.md`
- Design doc: [`src/tinycua/docs/design/loops/response.md`](src/tinycua/docs/design/loops/response.md)
- Related designs:
  - [`src/tinycua/docs/design/loops/node.md`](src/tinycua/docs/design/loops/node.md)
  - [`src/tinycua/docs/design/loops/node_queue.md`](src/tinycua/docs/design/loops/node_queue.md)
  - [`src/tinycua/docs/design/loops/result_aggregation.md`](src/tinycua/docs/design/loops/result_aggregation.md)
  - [`src/tinycua/docs/design/loops/information_digester.md`](src/tinycua/docs/design/loops/information_digester.md)
  - [`src/tinycua/docs/design/loops/tinycua_loop.md`](src/tinycua/docs/design/loops/tinycua_loop.md)
- Issue: https://github.com/VJyzCELERY/TINYCUA/issues/87 (Milestone 3.5)
