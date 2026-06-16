# Design Document: TinyCUA Handoff Isolation

**Spec**: [./spec.md](./spec.md)
**Status**: In Progress
**Last Updated**: 2026-06-16

---

## Overview

This design enforces TinyCUA's documented assistant-continuation message contract inside the current flat `TinyCUALoop`. It does not introduce full sub-session isolation. Instead, it prevents raw SDK/user messages from being replayed into every internal node, makes `NodeInput` the primary LLM-bound handoff channel, appends node-specific assistant continuation prompts, and keeps durable session context bounded and deduplicated.

---

## Architecture

### Component Overview

```text
SDK Agent.run(query)
  -> TinyCUALoop.root_session.input_context  # external boundary only
  -> QueryAnalyst prompt                     # may include role=user
  -> NodeInput assistant handoff             # internal continuation
  -> Digester / Worker / Task nodes          # assistant context + continuation
  -> ResponseNode                            # assistant aggregated result + continuation
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `NodeMessagePolicy` | Modified | Add explicit input-context inclusion policy. |
| `TinyCUALoop._build_node_messages` | Modified | Include raw input only when policy allows; append node continuations; suppress duplicated handoffs. |
| `Node` | Modified | Provide node continuation construction. |
| `QueryAnalyst` | Modified | Convert routes into assistant-role `NodeInput` handoffs. |
| `NodeQueue` | Modified | Forward outputs as compact assistant messages with source record metadata. |
| Worker task nodes | Modified | Add focused continuation prompts and task-state context. |
| Streaming execution | Modified | Use sync-like finalization evidence and resolved-tool tracing. |

---

## Data Model

### Schema Changes _(if applicable)_

- `NodeMessagePolicy.include_input_context: bool = False` controls whether SDK input context is appended to a node's LLM messages.
- `NodeInput.metadata["source_record_ids"]` identifies session records already represented in direct node input so session context can skip them.

---

## API / Interface Contracts

### New / Modified Functions

```python
def Node.build_continuation(session: Session | None = None) -> str:
    """Return the assistant-role continuation prompt for this node."""
```

The continuation is appended after any previous handoff/context and before provider tool feedback/retry continuations.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Empty continuation | Omitted message | Nodes may opt out only when no continuation is defined. |
| Duplicate forwarded output | Skipped session-context entry | Direct `NodeInput` copy remains authoritative. |
| Missing structured digest | Bounded fallback | Task lifecycle may fall back to raw input only after structured options fail. |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Add failing message-contract tests for entry-only user input, assistant handoffs, continuations, and duplicate suppression.
- [ ] Add `include_input_context` policy and enable it only for QueryAnalyst.
- [ ] Append node-specific assistant continuation prompts.
- [ ] Convert QueryAnalyst route handoffs to assistant-role `NodeInput`.
- [ ] Forward structured outputs through compact assistant messages and suppress duplicates.
- [ ] Align task lifecycle title fallback with digest/task state.

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Bring streaming tool continuation behavior to full sync parity.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Enforce handoff isolation inside the flat loop first.
   - **Reason**: It fixes the immediate design drift while minimizing runtime churn.
   - **Alternatives Considered**: Full sub-session isolation — rejected for this change because it is larger and riskier.
2. **Decision**: Treat `NodeInput` as the primary LLM-bound handoff.
   - **Reason**: Queue handoffs are explicit and target-specific; session context remains durable reusable state.
   - **Alternatives Considered**: Continue replaying root/session context — rejected because it repeats raw user input and pollutes prompts.
3. **Decision**: Use assistant role for internal session context at LLM boundary.
   - **Reason**: Design docs state only actual external user input uses role `user`.
   - **Alternatives Considered**: Preserve prior/input as user role — rejected because internal context is not a fresh user turn.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Internal nodes lose needed request context | Medium | High | QueryAnalyst handoff and DigestedInformation preserve focused request semantics. |
| Existing tests depend on input replay | Medium | Medium | Update tests to assert entry-only input and explicit passthrough handoff. |
| Streaming behavior remains divergent | Medium | Medium | Add streaming trace/tool tests and keep Phase 2 scoped. |

---

## References

- Spec: `./spec.md`
- `src/tinycua/specs/design-simplification/design.md`
- `src/tinycua/docs/architecture/information-digestion.md`
- `src/tinycua/docs/architecture/worker-orchestration.md`
- `src/tinycua/docs/architecture/task-creation.md`
- `src/tinycua/docs/architecture/task-analysis.md`
- `src/tinycua/docs/architecture/task-execution.md`
- `src/tinycua/docs/architecture/result-reviewer.md`
