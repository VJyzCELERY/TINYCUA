# Design Document: TinyCUA Handoff Isolation

**Spec**: [./spec.md](./spec.md)
**Status**: In Progress
**Last Updated**: 2026-06-17

---

## Overview

This design makes TinyCUA node activation explicit and isolated. `TinyCUALoop` becomes queue/transport infrastructure: it creates fresh node sessions, routes nodes, and passes only scoped `NodeInput`/`NodeHandoff` data. Concrete nodes own prompt/message building, validation, retry semantics, and handoff extraction. Tool invocation uses SDK `ToolExecutor`.

---

## Architecture

### Component Overview

```text
SDK Agent.run(query)
  -> TinyCUALoop root session                # durable task/audit state
  -> QueryAnalyst fresh session              # external user input boundary
  -> NodeHandoff / NodeInput                 # explicit transport only
  -> Digester / Worker / Task nodes          # fresh sessions, node-owned prompts
  -> ResponseNode                            # explicit aggregation handoff
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `NodeHandoff` | New | Generic typed envelope for explicit inter-node instruction/payload. |
| `node_handoff` tool | New | Lets selected nodes emit explicit handoffs. |
| `Node` | Modified | Owns message building, validation, retry, and handoff extraction. |
| `TinyCUALoop` | Modified | Shrinks to scoped transport, queue routing, trace aggregation, and SDK calls. |
| `NodeQueue` | Modified | Delivers explicit handoffs only; no automatic output forwarding. |
| `TaskAssessor` | Modified | Read-only: `task_inspect` + `node_handoff`. |
| Tool execution | Modified | Calls SDK `ToolExecutor.execute`. |

---

## Data Model

### New Entities

```python
NodeHandoff:
    source_node: str
    target_node: str | None
    instruction: str
    payload: dict[str, Any]
    constraints: list[str]
    metadata: dict[str, Any]
```

### Schema Changes

- `NodeInput` conversion accepts `NodeHandoff` and renders it as one assistant-role message.
- Root `Session` remains durable state/audit. Per-node `Session` objects are fresh message containers that share durable `task_store`.

---

## API / Interface Contracts

### New / Modified Functions

```python
def Node.build_messages(input: NodeInputLike) -> list[dict[str, Any]]:
    """Build this node's LLM messages from explicit input only."""

async def ToolExecutor.execute(tool: Tool, arguments: dict, agent: Agent) -> Any:
    """SDK-owned permission, approval, and invocation path used by TinyCUA."""
```

Node messages consist of one system message, explicit handoff/input messages, and node-owned continuation messages.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Empty handoff instruction | Validation failure | Do not create blank downstream prompts. |
| No explicit handoff | Empty node input | Never fall back to global `session_context` automatically. |
| Denied/approval-required tool | SDK `ToolExecutor` result | TinyCUA records result but does not bypass SDK policy. |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Add failing tests for explicit handoff-only prompts, no controller leakage, no duplicate digest, TaskAssessor read-only scope, and SDK ToolExecutor permission handling.
- [ ] Add generic `NodeHandoff` model and `node_handoff` tool.
- [ ] Stop automatic `session_context`/output forwarding in `NodeQueue`.
- [ ] Create fresh per-node sessions that share durable task state.
- [ ] Delegate message building to concrete nodes.
- [ ] Make TaskAssessor read-only and handoff-producing.
- [ ] Route TinyCUA tool execution through SDK `ToolExecutor`.

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Move remaining node-specific validation out of `TinyCUALoop`.
- [ ] Prune obsolete propagation/dedupe helpers once explicit handoff tests are green.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use a generic `NodeHandoff` envelope.
   - **Reason**: Every node can hand off different payloads without making the base model task-specific.
   - **Alternatives Considered**: Task-specific handoff fields — rejected because handoffs are cross-node infrastructure.
2. **Decision**: Fresh node sessions share durable task state but not message context.
   - **Reason**: Isolation prevents prompt leaks while preserving the global task tree.
   - **Alternatives Considered**: Continue root session sharing — rejected because it leaks controller/digest/retry context.
3. **Decision**: Nodes own prompt building and validation.
   - **Reason**: `TinyCUALoop` should be transport/routing infrastructure, not a god object for every node's semantics.
   - **Alternatives Considered**: Make `TinyCUALoop` the only runtime owner — rejected because it centralizes node internals.
4. **Decision**: Use SDK `ToolExecutor`.
   - **Reason**: Permission and approval checks already exist there.
   - **Alternatives Considered**: Direct `Tool.__call__` — rejected because it bypasses SDK behavior.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Internal nodes lose needed request context | Medium | High | QueryAnalyst/Digester/Worker handoffs preserve focused request semantics. |
| Fresh sessions lose task state | Low | High | Share `task_store` and workspace/session config explicitly. |
| Existing tests depend on context replay | Medium | Medium | Update tests to assert explicit handoff input. |
| Async ToolExecutor migration touches many call sites | Medium | Medium | Change one TinyCUA tool execution helper first, then update callers. |

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
