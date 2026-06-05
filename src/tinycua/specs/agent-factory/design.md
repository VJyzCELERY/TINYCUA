# Design Document: Agent Factory Contract (Milestone 1.1)

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-05

---

## Overview

This design implements the `create_tinycua_agent(...)` factory function and the `TinyCUALoop` class that extends the SDK `BaseLoop`. The factory constructs an SDK `Agent` with a `TinyCUALoop` attached, enabling the full TinyCUA node-based execution flow. No SDK public API modifications are required — TinyCUALoop consumes the existing `Agent._call_llm()` interface and `BaseLoop` contract.

---

## Architecture

### Component Overview

```
create_tinycua_agent(session, agent_config, session_config, ...)
  │
  ├── creates Session (if session=None)
  ├── applies SessionConfig to Session
  └── returns Agent(loop=TinyCUALoop(session, session_config, ...))

Agent.run(query)
  │
  └── TinyCUALoop.run(agent, messages, tools, instructions, stream)
        │
        ├── merges SDK messages into root session input context
        ├── initializes NodeQueue (placeholder — concrete nodes in later milestones)
        ├── while queue is not empty:
        │     node = queue.current
        │     node_session = node.ensure_session(...)
        │     node_input = queue.input_for_current()
        │     input_messages = node.build_messages(root_session, node_input)
        │     instructions = node.build_instruction(override_instructions)
        │     scoped_tools = node.tool_policy.resolve(node_tools, outer_agent_tools=tools)
        │     result = agent._call_llm(input_messages, scoped_tools)
        │     validate/retry according to node retry policy
        │     record chat history and selected session context
        │     node.on_complete(queue, result)
        └── return final string or stream events
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.factory` (new module) | New | `create_tinycua_agent()` factory function |
| `tinycua.loops.tinycua_loop` (new module) | New | `TinyCUALoop` extending SDK `BaseLoop` |
| `tinycua.config.session_config` | Existing | `SessionConfig` dataclass (already defined) |
| `tinycua.models.session` | Existing | `Session` class (already defined) |
| `tinycua-sdk` | No change | SDK public APIs remain untouched |

---

## Data Model

### New Entities

```python
# Conceptual data shapes — final classes defined in implementation

SessionConfig:
    compaction_strategy: CompactionStrategy | None
    max_context_messages: int | None
    max_context_tokens: int | None
    metadata: dict

Session:
    session_id: str
    session_context: list[SessionContextEntry]
    chat_history: list[ChatRecord]
    task: Task | None
    todo: Todo | None
    config: SessionConfig
    # ... additional fields from design docs

TinyCUALoop:
    root_session: Session
    queue: NodeQueue  # placeholder for now — concrete nodes in later milestones
    session_config: SessionConfig | None
```

### Schema Changes

- None. This milestone creates new modules; no existing schemas are modified.

---

## API / Interface Contracts

### `create_tinycua_agent(...)` Factory

```python
def create_tinycua_agent(
    session: Session | None = None,
    session_config: SessionConfig | None = None,
    **agent_kwargs,
) -> Agent:
    """
    Create a TinyCUA agent backed by the SDK Agent and TinyCUALoop.

    Args:
        session: Existing root session. If None, a new session is created.
        session_config: Session-level configuration (compaction, limits, metadata).
        **agent_kwargs: Additional kwargs passed to SDK Agent constructor
                        (name, instructions, tools, llm_model, etc.).

    Returns:
        SDK Agent instance with TinyCUALoop attached.

    Raises:
        ValueError: If session_config is provided but session is None and
                    config cannot be applied.
    """
    # 1. Create or validate session
    if session is None:
        session = Session()
    # 2. Apply session_config if provided
    if session_config is not None:
        session.config = session_config
    # 3. Create TinyCUALoop with session
    loop = TinyCUALoop(root_session=session, session_config=session_config)
    # 4. Create and return SDK Agent with loop
    return Agent(loop=loop, **agent_kwargs)
```

### `TinyCUALoop` Class

```python
class TinyCUALoop(BaseLoop):
    """
    SDK-compatible execution loop for TinyCUA node-based architecture.

    Extends BaseLoop without modifying SDK public APIs.
    Owns the root session and NodeQueue.
    """

    def __init__(
        self,
        root_session: Session,
        session_config: SessionConfig | None = None,
        max_iterations: int = 50,
    ) -> None:
        super().__init__(max_iterations=max_iterations)
        self.root_session = root_session
        self.session_config = session_config
        self.queue = NodeQueue()  # placeholder — populated by concrete nodes later

    async def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]:
        """
        Execute the TinyCUA node queue flow.

        1. Merge SDK messages into root session input context.
        2. Initialize/ensure NodeQueue with terminal node.
        3. While queue is not empty: run current node, record history, advance.
        4. Return final string (stream=False) or async iterator (stream=True).
        """
        ...
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `session=None` and session creation fails | `RuntimeError("Failed to create session")` | Unexpected — session has no external deps |
| `session_config` conflicts with session | Warning logged, config applied | Non-fatal — last-write-wins |
| LLM endpoint unreachable | Propagated from `agent._call_llm()` | Node retry policy handles retries |
| Queue exhausted without terminal node | `RuntimeError("No terminal node in queue")` | `ensure_terminal()` should prevent this |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `tinycua/config/session_config.py` with `SessionConfig` dataclass (if not already present)
- [ ] Create `tinycua/models/session.py` with `Session` class skeleton
- [ ] Create `tinycua/loops/tinycua_loop.py` with `TinyCUALoop` extending `BaseLoop`
- [ ] Create `tinycua/factory.py` with `create_tinycua_agent()` function
- [ ] Write unit tests for factory function
- [ ] Write unit tests for TinyCUALoop construction and basic run path
- [ ] Verify `Agent(loop=TinyCUALoop(...)).run(...)` works with mocked LLM

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Local model endpoint configuration with connection validation
- [ ] Default compaction strategy (`SimpleCompaction`) integration

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use `**agent_kwargs` pass-through instead of a separate `AgentConfig` object.
   - **Reason**: Keeps factory flexible — any future SDK Agent constructor changes are automatically supported without factory API changes.
   - **Alternatives Considered**: Separate `AgentConfig` dataclass — rejected because it would require maintaining a parallel config schema that duplicates SDK Agent kwargs.

2. **Decision**: `TinyCUALoop` stores `root_session` directly rather than creating it internally.
   - **Reason**: Allows session reuse across factory calls and external session management. The factory handles creation when `session=None`.
   - **Alternatives Considered**: Loop creates its own session — rejected because it couples session lifecycle to loop lifecycle, making session reuse harder.

3. **Decision**: `NodeQueue` is initialized as empty in the loop, with concrete nodes added in later milestones.
   - **Reason**: Milestone 1.1 focuses on the factory contract and loop skeleton. Concrete node implementations are deferred to Milestones 1.5–1.7.
   - **Alternatives Considered**: Stub nodes with no-op behavior — rejected because it adds complexity without testing the real factory contract.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SDK `BaseLoop` interface changes between versions | Low | High | Pin SDK version in pyproject.toml; loop extension is minimal surface area |
| Empty NodeQueue causes infinite loop in `TinyCUALoop.run()` | Medium | Medium | Add guard: if queue is empty or has no terminal node, return empty string and log warning |
| Session model drift from SDK conventions | Low | Medium | Follow SDK Session patterns documented in `docs/design/models/session.md` |

---

## Open Questions _(optional)_

1. **Empty queue behavior**: Should `TinyCUALoop.run()` return an empty string or raise when the queue has no nodes? This is relevant until concrete nodes are added in later milestones.
   - **Current thinking**: Return empty string with a warning log. This keeps the factory testable without requiring node implementations.

2. **Async vs sync factory**: Should `create_tinycua_agent()` be async? Currently designed as sync since session creation and loop setup are synchronous.
   - **Current thinking**: Keep sync. Async is only needed for `run()`.

---

## References

- Spec: `./spec.md` — relative path from this design.md to its spec.md
- SDK BaseLoop: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- SDK Agent: `src/tinycua-sdk/tinycua_sdk/agent/agent.py`
- Design: `src/tinycua/docs/design/loops/overview.md`
- Design: `src/tinycua/docs/design/loops/base_loop.md`
- Design: `src/tinycua/docs/design/loops/tinycua_loop.md`
- Design: `src/tinycua/docs/design/config/session_config.md`
- Issue: https://github.com/VJyzCELERY/TINYCUA/issues/87
