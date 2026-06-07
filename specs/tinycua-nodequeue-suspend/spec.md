# Feature Specification: NodeQueue Suspension and Prepend

**Status**: Draft
**Created**: 2026-06-07
**Last Updated**: 2026-06-07
**Subproject(s) Affected**: tinycua (loops/node_queue)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide `suspend_current_and_prepend()` capability so that nodes can temporarily suspend execution, delegate subtasks to prepended helper nodes, and resume after the helper completes — enabling the ResponseNode → InformationDigesterNode handoff pattern.
- **Gaps**: Today `NodeQueue` supports `advance()`, `spawn_after_current()`, and `clear_after_current()`, but has no mechanism to suspend the current node while keeping it queued, then prepend new nodes before it. The ResponseNode cannot delegate information digestion to a helper node and resume after the helper completes.
- **Non-Goals**: This spec does NOT cover route map dispatch, concrete TinyCUA nodes (QueryAnalyst, Worker, ResponseNode, InformationDigesterNode), or propagation rules. Those are handled by their respective milestones.
- **Constraints**: Must integrate with existing `NodeQueue` methods (`advance()`, `spawn_after_current()`, `clear_after_current()`, `ensure_terminal()`). Must work with the existing `Node` base class and `ProcessNode`/`DecisionNode` hierarchy. Must not modify `tinycua-sdk` public APIs. Must preserve backward compatibility with M1.6 behavior.

> **Important**: The `on_complete()` acceptance scenarios describe the intended usage pattern,
> but passing the real `NodeQueue` to `on_complete()` requires TinyCUALoop orchestrator
> integration (M1.8+). In the current codebase, `on_complete()` receives a placeholder
> `object()` as queue. This milestone (M1.7) focuses on the queue-level method only;
> concrete node usage is deferred to M1.8+.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A `TinyCUALoop` executes a `NodeQueue` with a ResponseNode as the current node. The ResponseNode determines it needs additional information before producing a final response. It calls `queue.suspend_current_and_prepend([InformationDigesterNode])` to suspend itself while keeping it queued, and prepend the InformationDigesterNode before it. The loop then executes the InformationDigesterNode, which processes information and propagates its output back to the suspended ResponseNode. The ResponseNode resumes execution with the digested information.

### Acceptance Scenarios

1. **Given** a queue with `[NodeA, NodeB]`, **When** `NodeA.on_complete()` calls `queue.suspend_current_and_prepend([NodeC])`, **Then** the queue becomes `[NodeC, NodeA, NodeB]` and `NodeC` is the new current node.
2. **Given** a queue with `[NodeA]`, **When** `NodeA.on_complete()` calls `queue.suspend_current_and_prepend([NodeB])`, **Then** the queue becomes `[NodeB, NodeA]` and `NodeB` is the new current node.
3. **Given** a queue with `[NodeA, NodeB]`, **When** `NodeA.on_complete()` calls `queue.suspend_current_and_prepend([NodeC, NodeD])`, **Then** the queue becomes `[NodeC, NodeD, NodeA, NodeB]` and `NodeC` is the new current node.
4. **Given** a queue with `[NodeA]`, **When** `NodeA.on_complete()` calls `queue.suspend_current_and_prepend([])`, **Then** the queue remains `[NodeA]` and `NodeA` remains current (no-op).
5. **Given** an empty queue, **When** `queue.suspend_current_and_prepend([NodeA])` is called, **Then** the system MUST raise `ValueError` (cannot suspend nothing).
6. **Given** a queue with `[NodeA, NodeB]`, **When** `NodeA` completes and `NodeB` becomes current via `advance()`, **Then** `NodeA` is removed from the queue and its session is not preserved (standard advance behavior).
7. **Given** a suspended node (e.g., `NodeA` at `queue[1]`), **When** `queue.current` is read, **Then** it returns the first prepended node, not the suspended node.
8. **Given** a queue with `[NodeC, NodeA, NodeB]` where `NodeA` is suspended, **When** `NodeC` completes and `queue.advance()` is called, **Then** `NodeC` is removed and `NodeA` becomes current (resumes execution).
9. **Given** a queue with `[NodeA]`, **When** `NodeA` calls `suspend_current_and_prepend([NodeB])` and then `NodeB` calls `suspend_current_and_prepend([NodeC])`, **Then** the queue becomes `[NodeC, NodeB, NodeA]` and `NodeC` is current.
10. **Given** a queue with `[NodeA]`, **When** `NodeA` calls
    `suspend_current_and_prepend([NodeB])` and `NodeB` completes via `advance()`,
    **Then** `NodeA` resumes as current. The caller is responsible for wiring
    NodeB's output to NodeA's input (see FR-009).

### Edge Cases

- What happens when `suspend_current_and_prepend()` is called on an empty queue? The system MUST raise `ValueError`.
- What happens when `suspend_current_and_prepend()` is called with an empty list? The system MUST be a no-op.
- What happens when multiple suspensions occur in sequence? The system MUST handle nested suspends correctly, with the most recently suspended node becoming current after helpers complete.
- What happens when a suspended node's input needs to be preserved? The system MUST preserve the `NodeInputLike` mapping for the suspended node.
- What happens when `clear_after_current()` is called with suspended nodes? The system clears all nodes after the current node (`items[0]`). If a suspended node is at `items[1]` (directly after current), it WILL be cleared. Suspended nodes are only preserved if they are NOT in the clear zone.
- What happens when a prepended node fails during execution (throws an exception)? The behavior depends on the loop's error handling policy. The queue itself does not provide failure recovery — the suspended parent remains queued at `items[1]`, and the loop must decide whether to skip the failed node, retry, or abort. This is deferred to M1.8+ (TinyCUALoop orchestrator integration).

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST implement `suspend_current_and_prepend(nodes)` that keeps the current node queued, inserts the new nodes before it, and makes the first prepended node the new `current`.
- **FR-002**: System MUST preserve the `NodeInputLike` mapping for the suspended node (the node that was current before suspension).
- **FR-003**: System MUST raise `ValueError` when `suspend_current_and_prepend()` is called on an empty queue.
- **FR-004**: System MUST be a no-op when `suspend_current_and_prepend()` is called with an empty list.
- **FR-005**: System MUST NOT call `propagate()` on the suspended node during suspension (unlike `advance()` which propagates before removal).
- **FR-006**: System MUST allow the suspended node to resume execution when the prepended nodes complete and `advance()` is called on them.
- **FR-007**: System MUST support multiple sequential suspensions, with each suspension prepending new nodes before the currently suspended node.
- **FR-008**: System MUST preserve the relative order of suspended nodes when multiple nodes are prepended.
- **FR-009**: System MUST ensure correct ordering so that the suspended parent node
  resumes as `items[0]` after all prepended children complete. Output propagation from
  prepended child to suspended parent is caller-established — the caller wires data flow
  between nodes (e.g., via `queue.set_input()` or node parent session).

### Key Entities _(include if feature involves data)_

- **NodeQueue**: Sequential execution structure. Now supports `suspend_current_and_prepend()` in addition to existing methods.
- **Suspended Node**: A node that remains queued but is no longer at `queue[0]`. No dedicated persisted state is required — suspension is implicit via queue position.
- **Node**: Base class with `is_terminal: bool`, `propagate()`, `on_complete(queue, response)`, `parent: Node | None`.
- **NodeInputLike**: Union type accepted by nodes for input data. Preserved for suspended nodes.

### Parent Relationship Contract

Parent-child node relationships for prepended nodes are **caller-established**, not queue-managed. The caller constructs prepended nodes and sets `parent` appropriately (e.g., `digester.parent = response_node`). `suspend_current_and_prepend()` only manages queue ordering — it does not modify `Node.parent`. This aligns with the M1.7 milestone contract (issue #87) which requires "parent node relationship for prepended child" — satisfied by the caller-establishing pattern.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Suspension works**: `suspend_current_and_prepend()` keeps current node queued, inserts new nodes before it, and makes first prepended node current.
- [ ] **Input preservation works**: Suspended node's `NodeInputLike` mapping is preserved after suspension.
- [ ] **Empty queue safety**: `suspend_current_and_prepend()` on empty queue raises `ValueError`.
- [ ] **Empty list safety**: `suspend_current_and_prepend([])` is a no-op.
- [ ] **No propagation during suspend**: `propagate()` is NOT called on the suspended node during suspension.
- [ ] **Resume works**: Suspended node resumes execution when prepended nodes complete and `advance()` is called.
- [ ] **Multiple suspensions work**: Sequential suspensions handle nested suspension correctly.
- [ ] **Order preservation works**: Relative order of suspended nodes is preserved when multiple nodes are prepended.
- [ ] **Backward compatibility**: Existing M1.6 tests pass without modification.
- [ ] **Caller-established data flow works**: Queue ordering ensures suspended parent
      resumes after prepended children complete; data flow between them is
      caller-established (see FR-009).

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_node_queue_suspend.py`: Comprehensive tests organized by scenario:
  - Basic suspension (`test_suspend_keeps_current_queued_and_prepends_before_it`)
  - Single/multiple prepend (`test_suspend_with_single_node`, `test_suspend_with_multiple_nodes`)
  - Edge cases (`test_suspend_empty_list_is_noop`, `test_suspend_empty_queue_raises_value_error`)
  - Input preservation (`test_suspend_preserves_input_mapping`, `test_suspend_prepended_node_input_lifecycle`)
  - No propagation (`test_suspend_does_not_call_propagate`)
  - Resume (`test_suspend_resume_after_advance`)
  - Nested suspension (`test_suspend_nested_suspension_queue_state`)
  - Clear interaction (`test_clear_after_current_with_suspended_node`)
  - Output propagation (`test_suspend_preserves_suspended_input_after_prepended_advance`)

### Integration Tests

- Integration testing with concrete nodes (`ProcessNode`, `DecisionNode`, `TinyCUALoop`) is deferred to the respective concrete node milestones (M1.8+). This milestone focuses on `NodeQueue` unit-level behavior only.

### Manual Tests _(if applicable)_

- None required for this milestone.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| suspend_current_and_prepend() | DONE | Core implementation |
| Input preservation | DONE | |
| Empty queue safety | DONE | |
| Empty list safety | DONE | |
| No propagation during suspend | DONE | |
| Resume mechanism | DONE | |
| Multiple suspensions | DONE | |
| Order preservation | DONE | |
| Unit tests | DONE | 12 tests passing |
| Backward compatibility | DONE | Existing M1.6 tests pass |

---

## Open Questions _(optional)_

1. **Should suspended nodes have a dedicated state flag?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-07
   - **Status**: Resolved
   - **Resolution**: No — suspension is implicit via queue position. The target architecture states: "A node is suspended when it remains queued but is no longer at queue[0]. No dedicated persisted suspended state is required." See design.md Data Model section — no flag is defined.

2. **How should nested suspensions handle input propagation?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-07
   - **Status**: Resolved
   - **Resolution**: Each suspended node retains its own `NodeInputLike` mapping. Prepended nodes have their inputs set via `set_input()` before/after suspension. `advance()` cleans up prepended node inputs automatically. See design.md "Input Lifecycle During Suspension" section.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
