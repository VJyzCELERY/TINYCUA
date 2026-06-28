# Design Document: TinyCUA Runtime Context

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-06-19

---

## Overview

Add one dynamic system-prompt fragment during node system message construction. The fragment contains current local date/time and timezone.

---

## Architecture

### Component Overview

```
Node.build_system_message -> SystemPromptBuilder -> runtime context fragment
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.config.system_prompt` | Modified | Adds runtime context helper. |
| `tinycua.loops.node` | Modified | Adds helper output to every node system message. |

---

## Data Model

No schema changes.

---

## API / Interface Contracts

No public API changes.

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [x] Add runtime context helper.
- [x] Include helper output in node system messages.
- [x] Add unit test.

---

## Technical Decisions

1. **Decision**: Use local `datetime.now().astimezone()`.
   - **Reason**: Stdlib, no config, enough for general useful context.
   - **Alternatives Considered**: User-configured timezone — rejected as unnecessary now.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Prompt bloat | Low | Low | Keep fragment to two lines. |

---

## References

- Spec: `./spec.md`
