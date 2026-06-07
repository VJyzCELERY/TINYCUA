# Design Document: TinyCUA Node Base, DecisionNode, and ProcessNode

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-07

---

## Overview

This design introduces the base `Node` abstraction, `ProcessNode`, and `DecisionNode` into `tinycua.loops.node`. These classes define the shared contract for session attachment, message/instruction building, lifecycle hooks, and input dispatch that all future concrete TinyCUA nodes will inherit. The design follows the target architecture in `src/tinycua/docs/design/loops/node.md` and `src/tinycua/docs/design/config/node_config.md`.

---

## Architecture

### Component Overview

```
Node (base)
├── node_id: str
├── session: Session | None
├── parent: Node | None
├── config: NodeConfigBase
├── ensure_session()
├── build_instruction()
├── build_messages()
├── validate_output()
├── build_retry_continuation()
├── record_output()
├── propagate()
└── on_complete()

ProcessNode(Node)
├── _handle_input() — dispatch NodeInputLike to internal handlers
├── _call_llm() — invoke LLM with built messages
└── __call__(input) — orchestrates build → validate → call → retry → record → propagate → complete

DecisionNode(ProcessNode)
├── _analysis_call() — first LLM call for analysis
├── _classification_call() — second LLM call with classification tool
├── _dispatch_route() — map classification label to route
└── __call__(input) — orchestrates analysis → classification → dispatch
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/node.py` | New | Base `Node`, `ProcessNode`, `DecisionNode` classes |
| `tinycua/config/node_config.py` | Modified (if needed) | Ensure `NodeConfigBase` is importable by node module |
| `tinycua/config/types.py` | Referenced | Ensure `LLMResult` is importable by node module |
| `tinycua/models/node_input.py` | Referenced | `NodeInput`, `NodePayload`, `NodeInputLike` types |
| `tinycua/loops/node_queue.py` | Referenced | `NodeQueue` type for `on_complete()` lifecycle hook |

---

## Data Model

### Node Base Class

```python
class Node(ABC):
    node_id: str
    session: Session | None
    parent: Node | None
    config: NodeConfigBase
    is_terminal: bool

    def ensure_session(self, root_or_parent_session: Session) -> Session: ...
    def build_instruction(self, override_instructions: str | None = None) -> str: ...
    def build_messages(self, root_session: Session, input: NodeInputLike) -> list[dict]: ...
    def validate_output(self, response: LLMResult) -> ValidationResult: ...
    def build_retry_continuation(self, error: ValidationError, attempt: int) -> str: ...
    def record_output(self, response: LLMResult) -> None: ...
    def propagate(self) -> None: ...
    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None: ...
```

### ProcessNode

```python
class ProcessNode(Node):
    def __call__(self, input: NodeInputLike) -> LLMResult: ...
    # Internally: build messages → validate → call LLM → retry loop → record → propagate → on_complete
```

### DecisionNode

```python
class DecisionNode(ProcessNode):
    def __call__(self, input: NodeInputLike) -> DecisionResult: ...
    # Internally: analysis call → classification call → validate route → dispatch
```

### NodeInputLike Dispatch

```python
# Internal dispatch table
INPUT_HANDLERS = {
    str: _handle_string,         # external → user-role, internal → assistant-role
    NodeInput: _handle_node_input,
    NodePayload: _handle_node_payload,
    list[dict]: _handle_message_list,
}
```

---

## API / Interface Contracts

### Node Base Contract

```python
class Node(ABC):
    """
    Base class for all TinyCUA nodes.

    Concrete nodes must implement __call__(input: NodeInputLike) -> result.
    Lifecycle hooks are called automatically by ProcessNode.__call__.
    """

    def ensure_session(self, root_or_parent_session: Session) -> Session:
        """
        Create or adopt a session. If self.session is already set, return it.
        Otherwise, create a new session from root_or_parent_session context.
        Raises ValueError if root_or_parent_session is None and no parent exists.
        """
```

### ProcessNode Contract

```python
class ProcessNode(Node):
    """
    Primary node type for non-decision processing.

    __call__ orchestrates:
    1. build_messages(root_session, input)
    2. validate_output (pre-call check)
    3. LLM invocation with retry loop
    4. record_output(response)
    5. propagate()
    6. on_complete(queue, response)
    """
```

### DecisionNode Contract

```python
class DecisionNode(ProcessNode):
    """
    Node that performs analysis + classification + route dispatch.

    __call__ orchestrates:
    1. analysis call (first LLM invocation)
    2. classification call (second LLM invocation with classification tool)
    3. validate classification output
    4. dispatch route via RouteMap (or return label if no queue available)
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Empty input string | `ValueError("Empty input")` | Node rejects empty string |
| No session and no parent | `ValueError("No session available")` | `ensure_session()` requires root or parent |
| Retry exhausted (raise) | `NodeExecutionError` | Raised to loop |
| Retry exhausted (record_failure) | Recorded to session, propagated | Per `NodeRetryPolicy.on_retry_exhausted`. `PropagationRule` integration deferred to later milestone. |
| Invalid classification | Retried via `build_retry_continuation` | Per `NodeRetryPolicy` |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Define `Node` base class with core fields (`node_id`, `session`, `parent`, `config`, `is_terminal`)
- [ ] Implement `ensure_session()` with root/parent session adoption
- [ ] Implement `build_instruction()` merging hardcoded + configurable + dynamic fragments
- [ ] Implement `build_messages()` using `SystemPromptBuilder` and `NodeMessagePolicy`
- [ ] Implement `NodeInputLike` dispatch (`str`, `NodeInput`, `NodePayload`, `list[dict]`)
- [ ] Define `ProcessNode(Node)` with `__call__` orchestrating build → validate → LLM → retry → record → propagate → complete
- [ ] Define `DecisionNode(ProcessNode)` with `__call__` orchestrating analysis → classification → dispatch
- [ ] Implement `validate_output()` checking `required_tool_calls` and `required_output_schema`
- [ ] Implement `build_retry_continuation()` producing assistant-role retry messages
- [ ] Implement lifecycle hooks: `record_output()`, `propagate()`, `on_complete()`
- [ ] Write unit tests for all node types and input dispatch

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- None for this milestone. Concrete nodes are deferred.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: `DecisionNode` inherits from `ProcessNode`, not directly from `Node`.
   - **Reason**: Decision nodes share the same LLM call + retry + lifecycle contract as process nodes. The only addition is the two-step analysis + classification flow.
   - **Alternatives Considered**: `DecisionNode(Node)` — rejected because it would duplicate the LLM call and retry logic.

2. **Decision**: `NodeInputLike` dispatch is handled via a type-based dispatch table, not `isinstance` chains.
   - **Reason**: Cleaner separation, easier to extend, matches the design doc's `NodeInputLike = str | NodeInput | NodePayload | list[dict]` definition.
   - **Alternatives Considered**: `isinstance` cascade — rejected for maintainability.

3. **Decision**: `is_terminal` is a class-level `bool` field on `Node`, not a `@property`.
   - **Reason**: Terminal status is an immutable attribute of the node type — `ResponseNode` is always terminal, `DecisionNode` is never terminal. A plain field makes this a data-level declaration that cannot be accidentally overridden by subclasses (a `@property` can be shadowed by assigning to the instance, silently breaking the contract). Field access also allows direct mutation in tests and mock scenarios without needing a setter or `_is_terminal` backing variable.
   - **Alternatives Considered**: `@property is_terminal` — rejected because it introduces indirection over what is fundamentally a static boolean, invites accidental override by subclasses, and adds complexity with no corresponding flexibility for this milestone.

4. **Decision**: Session attachment uses `ensure_session()` rather than constructor injection.
   - **Reason**: Nodes may be created before sessions exist (e.g., during queue construction). Session attachment happens at execution time when the root session is available.
   - **Alternatives Considered**: Constructor injection — rejected because it couples node creation to session lifecycle.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `SystemPromptBuilder` integration complexity | Medium | Medium | Use existing `SystemPromptBuilder` from design docs; test with mock prompts |
| `DecisionNode` two-step flow adds latency | Low | Low | Acceptable for prototype; future optimization can combine calls |
| `NodeInputLike` dispatch edge cases | Low | Medium | Comprehensive unit tests for each input type including edge cases |
| Session lifecycle coupling | Medium | Medium | `ensure_session()` defers session creation; test with both fresh and existing sessions |

---

## Open Questions _(optional)_

_(None — all questions resolved. See spec.md:130 for DecisionResult resolution.)_

---

## References

- Spec: `./spec.md`
- Design docs:
  - `src/tinycua/docs/design/loops/node.md` — node hierarchy, system prompt categories, input types
  - `src/tinycua/docs/design/config/node_config.md` — `NodeConfigBase`, policies, per-node configs
  - `src/tinycua/docs/design/models/node_input.md` — `NodeInput`, `NodePayload`, `NodeInputLike`
- Issue: [#87](https://github.com/VJyzCELERY/TINYCUA/issues/87) — Milestone 1.5
