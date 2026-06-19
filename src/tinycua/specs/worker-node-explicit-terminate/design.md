# Design Document: Worker Node Explicit Terminate

**Spec**: `./spec.md`
**Status**: In Progress
**Last Updated**: 2026-06-19

---

## Overview

Add an explicit runtime `terminate()` tool for TinyCUA worker lifecycle nodes. The runtime keeps node completion validation authoritative: `terminate()` is accepted only after each node's existing required conditions are satisfied.

---

## Architecture

### Component Overview

```
Worker lifecycle node -> required tool calls -> runtime exposes terminate -> terminate accepted -> on_complete
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.tools` | New | Add `TerminateTool` |
| `ValidationRetryMixin` | Modified | Require terminate for worker lifecycle nodes and gate exposure |
| `tool_scopes` | Modified | Keep terminate out of static scopes |

---

## Data Model

### New Entities _(if applicable)_

`TerminateTool`: returns a small success payload when called.

### Schema Changes _(if applicable)_

None.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

`terminate() -> {"success": true, "terminated": true}` signals the model is done with the current node.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Missing required node work | Validation error | Retry continues |
| Missing terminate after ready | Validation error | Retry exposes terminate |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Add unit tests for reviewer terminate gating.
- [ ] Add `TerminateTool`.
- [ ] Add worker lifecycle termination validation and retry tool exposure.

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] None.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Make terminate dynamic, not statically scoped.
   - **Reason**: Models should only see terminate after runtime conditions are met.
   - **Alternatives Considered**: Always expose terminate — rejected because it invites premature completion.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Extra LLM turn per worker node | High | Medium | Limit to worker lifecycle nodes only |
| Terminate loops | Medium | Medium | Retry narrows/guides to terminate when ready |

---

## References

- Spec: `./spec.md` — relative path from this design.md to its spec.md
