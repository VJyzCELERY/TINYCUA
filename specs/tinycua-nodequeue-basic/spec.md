# Feature Specification: NodeQueue Basic Execution and Terminal Safety

**Status**: Approved
**Created**: 2026-06-07
**Last Updated**: 2026-06-07
**Subproject(s) Affected**: tinycua (loops/node_queue)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a functional `NodeQueue` with sequential execution semantics so that `TinyCUALoop` can execute nodes in order, manage queue transitions via `on_complete()`, and guarantee a terminal response path at all times.
- **Gaps**: Today `NodeQueue` is a M1.1 stub that always reports empty and has no real execution logic. There is no sequential queue semantics, no `advance()`, no `spawn_after_current()`, no `clear_after_current()`, and no `ensure_terminal()` for queue bootstrap safety. `TinyCUALoop` cannot execute nodes through the queue.
- **Non-Goals**: This spec does NOT cover suspension/prepend semantics (`suspend_current_and_prepend()`), route map dispatch, concrete TinyCUA nodes (QueryAnalyst, Worker, ResponseNode), or propagation rules. Suspension/prepend is deferred to Milestone 1.7.
- **Constraints**: Must integrate with existing `Node.on_complete(queue, response)` lifecycle hook. Must work with the existing `Node` base class and `ProcessNode`/`DecisionNode` hierarchy. Must not modify `tinycua-sdk` public APIs. Must preserve backward compatibility with M1.1 placeholder behavior when queue is empty.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A `TinyCUALoop` initializes a `NodeQueue` with a sequence of nodes (e.g., QueryAnalyst → Worker → ResponseNode). The loop calls `queue.current` to get the active node, executes it, and the node calls `on_complete(queue, result)` to mutate the queue (advance, spawn, or clear). The loop continues until the queue is empty or a terminal node completes.

### Acceptance Scenarios

1. **Given** a queue with `[NodeA, NodeB, NodeC]`, **When** `queue.current` is read, **Then** it returns `NodeA` (queue[0]).
2. **Given** a queue with `[NodeA, NodeB]`, **When** `NodeA.on_complete()` calls `queue.advance()`, **Then** `NodeA` is removed, `NodeB` becomes current, and `NodeA.propagate()` is called before removal.
3. **Given** a queue with `[NodeA, NodeB]`, **When** `NodeA.on_complete()` calls `queue.spawn_after_current([NodeC])`, **Then** the queue becomes `[NodeA, NodeC, NodeB]` and `NodeA` remains current.
4. **Given** a queue with `[NodeA, NodeB, NodeC]`, **When** `NodeA.on_complete()` calls `queue.clear_after_current()`, **Then** the queue becomes `[NodeA]` and `NodeB`, `NodeC` are removed without session mutation.
5. **Given** a queue with no terminal node, **When** `queue.ensure_terminal(default_response_node)` is called, **Then** the default response node is appended to the end.
6. **Given** a queue with a terminal node at the end, **When** `queue.ensure_terminal(default_response_node)` is called, **Then** no node is appended (no duplicate terminal).
7. **Given** an empty queue, **When** `queue.is_empty()` is called, **Then** it returns `True`.
8. **Given** a queue with `[NodeA]`, **When** `queue.is_empty()` is called, **Then** it returns `False`.

### Edge Cases

- What happens when `advance()` is called on an empty queue? The system MUST raise `ValueError`.
- What happens when `advance()` is called and the current node has not propagated? The system MUST call `propagate()` before removal.
- What happens when `spawn_after_current()` is called on an empty queue? The system MUST raise `ValueError` (cannot spawn after nothing).
- What happens when `clear_after_current()` is called and there are no nodes after current? The system MUST be a no-op.
- What happens when `ensure_terminal()` is called and the queue is empty? The system MUST append the default terminal node.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a `NodeQueue` class with `items: list[Node]` and `current: Node | None` properties.
- **FR-002**: System MUST implement `current` as a property returning `items[0]` when present, `None` when empty.
- **FR-003**: System MUST implement `is_empty()` returning `True` when `items` is empty, `False` otherwise.
- **FR-004**: System MUST implement `input_for_current()` returning the `NodeInputLike` assigned to the current node.
- **FR-005**: System MUST implement `advance()` that removes `items[0]` after calling `propagate()` on it, then returns the new current node or `None`.
- **FR-006**: System MUST implement `spawn_after_current(nodes)` that inserts nodes after `items[0]` without changing current.
- **FR-007**: System MUST implement `clear_after_current()` that removes all nodes after `items[0]` without mutating their sessions.
- **FR-008**: System MUST implement `ensure_terminal(default_response_node)` that appends the default terminal node when no terminal node exists at the end of the queue.
- **FR-009**: System MUST track `NodeInputLike` per node for `input_for_current()` via an internal mapping.
- **FR-010**: System MUST raise `ValueError` when `advance()` is called on an empty queue.
- **FR-011**: System MUST raise `ValueError` when `spawn_after_current()` is called on an empty queue.
- **FR-012**: System MUST call `propagate()` on a node before removing it in `advance()` if it has not already propagated.

### Key Entities _(include if feature involves data)_

- **NodeQueue**: Sequential execution structure. Holds `items: list[Node]`, provides `current`, `advance()`, `spawn_after_current()`, `clear_after_current()`, `ensure_terminal()`.
- **Node**: Base class (from M1.5) with `is_terminal: bool`, `propagate()`, `on_complete(queue, response)`.
- **NodeInputLike**: Union type accepted by nodes for input data.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Queue current works**: `queue.current` returns `items[0]` when present, `None` when empty.
- [ ] **Advance works**: `advance()` removes current node after calling `propagate()`, returns new current.
- [ ] **Spawn works**: `spawn_after_current(nodes)` inserts nodes after current without changing current.
- [ ] **Clear works**: `clear_after_current()` removes all nodes after current.
- [ ] **Ensure terminal works**: `ensure_terminal()` appends terminal node when none exists, no-ops when one exists.
- [ ] **Empty queue safety**: `advance()` on empty queue raises `ValueError`.
- [ ] **Spawn on empty safety**: `spawn_after_current()` on empty queue raises `ValueError`.
- [ ] **Input tracking works**: `input_for_current()` returns correct input for current node.
- [ ] **Propagation on advance**: `propagate()` is called before node removal in `advance()`.
- [ ] **Terminal detection works**: `ensure_terminal()` correctly detects terminal nodes by `is_terminal` flag.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_node_queue_basic.py`: Test `NodeQueue` initialization, `current`, `is_empty()`, `input_for_current()`.
- `test_node_queue_advance.py`: Test `advance()` with single and multiple nodes, propagation call, empty queue error.
- `test_node_queue_spawn.py`: Test `spawn_after_current()` with single and multiple nodes, empty queue error.
- `test_node_queue_clear.py`: Test `clear_after_current()` with nodes after current, no nodes after current.
- `test_node_queue_ensure_terminal.py`: Test `ensure_terminal()` with no terminal, with existing terminal, empty queue.

### Integration Tests

- Test that `NodeQueue` integrates with `ProcessNode` and `DecisionNode` for full execution flow.
- Test that `TinyCUALoop.run()` uses `NodeQueue` correctly with bootstrap invariants.

### Manual Tests _(if applicable)_

- None required for this milestone.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| NodeQueue class | TODO | Replace M1.1 stub |
| current property | TODO | |
| advance() | TODO | |
| spawn_after_current() | TODO | |
| clear_after_current() | TODO | |
| ensure_terminal() | TODO | |
| Input tracking | TODO | |
| Unit tests | TODO | |

---

## Decisions Log _(optional)_

1. **Terminal detection**: Should `ensure_terminal()` detect terminal nodes by checking `node.is_terminal` attribute, or by checking node type?
   - **Decision**: Use `node.is_terminal` attribute. This is consistent with the `Node` base class design from M1.5 and allows flexible terminal node definitions.

2. **Input tracking**: Should `NodeInputLike` be stored per-node in a dict, or as a wrapper around each node in the items list?
   - **Decision**: Use a dict mapping `node_id` to `NodeInputLike`. This keeps the items list clean and allows input reassignment.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
