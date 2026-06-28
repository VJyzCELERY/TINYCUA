# Feature Specification: TinyCUA Runtime Context

**Status**: Complete
**Created**: 2026-06-19
**Last Updated**: 2026-06-19
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Give every TinyCUA node basic current date/time context so time-sensitive prompts have a useful reference.
- **Gaps**: Node prompts currently do not include the current date or timezone.
- **Non-Goals**: Location inference, calendars, clock tools, or user-specific locale settings.
- **Constraints**: Use Python stdlib only; keep the prompt addition short.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A user asks a time-sensitive question and every TinyCUA node sees the current local date/time in its system prompt.

### Acceptance Scenarios

1. **Given** any TinyCUA node, **When** it builds messages, **Then** the system message includes current date/time and timezone.

### Edge Cases

- If the timezone has no display name, the numeric offset is still present.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST include current local date/time in node system prompts.
- **FR-002**: System MUST include timezone information.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [x] **Nodes receive runtime context**: system messages include date/time and timezone.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Node system prompt includes runtime context.

### Integration Tests

- Covered by existing TinyCUA run paths.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
