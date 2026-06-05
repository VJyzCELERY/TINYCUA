# Design Document: Agent Factory Contract (Milestone 1.1)

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Last Updated**: 2026-06-05

---

## Overview

This design defines the `create_tinycua_agent()` factory function, which is the entry point for constructing a TinyCUA `Agent`. The factory composes an SDK `Agent` with a `TinyCUALoop` and handles session creation/config application. This is the first milestone toward the full TinyCUA architecture.

---

## Architecture

### Component Overview

```
Caller
  |
  v
create_tinycua_agent(session, agent_config, session_config)
  |
  +---> [Session Setup]
  |       If session is None: create new Session
  |       Apply SessionConfig to session
  |
  +---> [Loop Setup]
  |       Instantiate TinyCUALoop(session=session, ...)
  |
  +---> [Agent Setup]
  |       Instantiate SDK Agent(loop=tinycua_loop, **agent_config)
  |
  v
  Returns: Agent (ready for agent.run())
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `create_tinycua_agent()` | New | Factory function in `src/tinycua/` |
| `TinyCUALoop` | New | Loop class extending SDK `BaseLoop` |
| `Session` | Existing (SDK) | Used as-is, not modified |
| `SessionConfig` | Existing (design) | Applied to session per policy |
| `Agent` | Existing (SDK) | Used as-is, not modified |

---

## Data Model

### New Entities

```python
# Conceptual shapes (not final implementation)

def create_tinycua_agent(
    session: Session | None = None,
    agent_config: dict | None = None,
    session_config: SessionConfig | None = None,
) -> Agent:
    """Factory function signature."""
```

### SessionConfig Application Policy

- If `session_config` is provided and `session is None`: create session, apply config.
- If `session_config` is provided and `session is provided`: apply config to provided session.
- If `session_config` is None and `session is None`: create session with defaults.
- If `session_config` is None and `session is provided`: use session as-is.

---

## API / Interface Contracts

### Factory Function

```python
def create_tinycua_agent(
    session: Session | None = None,
    agent_config: dict | None = None,
    session_config: SessionConfig | None = None,
) -> Agent:
    """
    Create a TinyCUA Agent with TinyCUALoop attached.

    Args:
        session: Existing session to use. If None, a new session is created.
        agent_config: Forwarded to SDK Agent constructor.
        session_config: Applied to the session. If None, defaults are used.

    Returns:
        Agent with TinyCUALoop as agent.loop.

    Raises:
        ValueError: If configuration is invalid or incompatible.
    """
```

### Error Handling

| Error Case | Exception | Notes |
|------------|-----------|-------|
| Invalid session_config | `ValueError` | Descriptive message |
| Incompatible session + config | `ValueError` | When config conflicts with session state |
| SDK Agent creation fails | Propagated SDK exception | Wrapped with context |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Define `SessionConfig` dataclass (minimal fields for M1.1)
- [ ] Implement `TinyCUALoop` extending SDK `BaseLoop`
- [ ] Implement `create_tinycua_agent()` factory function
- [ ] Write unit tests for factory behavior
- [ ] Write integration test with stub nodes

### Phase 2 — Enhancements _(post-MVP)_

- [ ] Full SessionConfig with all policy fields
- [ ] CompactionStrategy integration
- [ ] Node queue setup

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Factory function pattern rather than class-based builder.
   - **Reason**: Simpler API, matches SDK conventions, spec requires `create_tinycua_agent()`.
   - **Alternatives Considered**: AgentBuilder class — rejected as over-engineering for current scope.

2. **Decision**: TinyCUALoop extends SDK `BaseLoop` directly.
   - **Reason**: Spec mandates this; preserves SDK API contract.
   - **Alternatives Considered**: Wrapper around BaseLoop — rejected because it breaks the loop type hierarchy.

3. **Decision**: SessionConfig application as a separate step from session creation.
   - **Reason**: Allows reuse when session already exists.
   - **Alternatives Considered**: Merged into session constructor — rejected because it couples config to creation.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SDK API changes break factory | Low | High | Pin SDK version; test against SDK contracts |
| SessionConfig scope creep | Medium | Medium | Strictly bound to M1.1; defer complex policies |
| Loop initialization failures | Low | Medium | Comprehensive error messages; fallback defaults |

---

## Open Questions _(optional)_

1. Should `agent_config` be a typed dataclass or a plain dict?
2. What are the exact default values for SessionConfig when none is provided?
3. Should the factory support async session creation in future milestones?

---

## References

- Spec: `./spec.md`
- Design docs: `src/tinycua/docs/design/loops/overview.md`, `src/tinycua/docs/design/loops/base_loop.md`
- Roadmap: `src/tinycua/docs/roadmap/tinycua_architecture_implementation/`
- SDK contract: `src/tinycua-sdk/` (existing SDK Agent and BaseLoop)
