# Design Document: Agent Factory Contract (Milestone 1.1)

**Spec**: `./spec.md`
**Status**: Reviewed
**Last Updated**: 2026-06-05

---

## Overview

This design implements the `create_tinycua_agent(...)` factory function and the `TinyCUALoop` class that extends the SDK `BaseLoop`. The factory constructs an SDK `Agent` with a `TinyCUALoop` attached, enabling the full TinyCUA node-based execution flow. No SDK public API modifications are required — TinyCUALoop consumes the existing `Agent._call_llm()` interface and `BaseLoop` contract.

---

## Architecture

### Component Overview

```
create_tinycua_agent(session, session_config, **agent_kwargs)
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
        ├── M1.1 passthrough (if queue is empty):
        │     result = agent._call_llm(messages, tools)
        │     return result["content"] or stream events
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
| `tinycua.config.session_config` | New | `SessionConfig` dataclass (defined in M1.1) |
| `tinycua.models.session` | New | `Session` class (defined in M1.1) |
| `tinycua-sdk` | No change | SDK public APIs remain untouched |

---

## Data Model

### New Entities

```python
# Conceptual data shapes — final classes defined in implementation

SessionConfig:
    compaction_strategy: Any | None = None
    max_context_messages: int | None
    max_context_tokens: int | None
    metadata: dict

Session:
    session_id: str  # Generated via uuid.uuid4().hex for M1.1; structured IDs (ULID, etc.) are a future concern
    parent_id: str | None  # None for root sessions; set for child sessions
    session_context: list[SessionContextEntry]
    chat_history: list[ChatRecord]
    task: Task | None
    todo: Todo | None
    session_config: SessionConfig
    # ... additional fields from design docs

    def compact_context(self) -> None:  # Stub for M1.1 — returns None
        """Placeholder — compaction is a Phase 2 concern."""
        return None

TinyCUALoop:
    root_session: Session
    queue: NodeQueue  # placeholder for now — concrete nodes in later milestones
    session_config: SessionConfig | None

# Minimal type stubs for M1.1 — these are placeholder shapes; concrete
# implementations may evolve in later milestones.
ChatRecord: dict[str, Any]       # {"role": str, "content": str}
SessionContextEntry: dict[str, Any]  # {"key": str, "value": Any}
Task: dict[str, Any] | None      # placeholder for future task model
Todo: dict[str, Any] | None      # placeholder for future todo model
```

### Schema Changes

- None. This milestone creates new modules; no existing schemas are modified.

### Relationship to Canonical Design Docs

This M1.1 data model is a minimal subset of the target architecture defined in
`src/tinycua/docs/design/models/session.md`. Fields and methods deferred to later
milestones: `agent_state` (M1.x), `compact_context(window)` full signature (Phase 2).
Type aliases (`SessionContextEntry`, `ChatRecord`) are M1.1 convenience aliases;
the canonical types use plain `dict`.

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

    Note:
        If session_config is provided, it is applied to the session
        (or the newly created session when session=None).
        Config application is non-fatal — last-write-wins.
    """
    # 1. Create or validate session
    if session is None:
        session = Session()
    # 2. Apply session_config if provided
    if session_config is not None:
        session.session_config = session_config
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

        M1.1: When queue is empty, calls agent._call_llm() once with incoming
        messages (passthrough mode) and returns its output. This verifies the
        factory → agent → loop → LLM wiring without node implementations.
        Full node execution deferred to Milestones 1.5-1.7.

        1. Merge SDK messages into root session input context.
        2. Initialize/ensure NodeQueue with terminal node.
        3. If queue is empty (M1.1): call agent._call_llm() once with messages, return its output.
        4. While queue is not empty: run current node, record history, advance.
        5. Return final string (stream=False) or async iterator (stream=True).
        """
        ...
```

### `agent._call_llm()` Return Contract (M1.1)

For M1.1 (mocked LLM), `_call_llm()` is expected to return a dict with:
- `content: str` — the LLM output text
- `tool_calls: list | None` — tool call requests (None in M1.1)
- `usage: dict | None` — token usage stats (None in M1.1)
- `finish_reason: str | None` — completion reason
- `model: str | None` — model identifier (None in M1.1)

`TinyCUALoop.run()` extracts `content` for non-streaming string output.
The real `_call_llm()` contract is defined by the SDK and may evolve — this M1.1
contract mirrors the minimum shape needed for factory/loop testing.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `session=None` and session creation fails | `RuntimeError("Failed to create session")` | Unexpected — session has no external deps |
| `session_config` conflicts with session | Warning logged, config applied | Non-fatal — last-write-wins |
| LLM endpoint unreachable | Propagated from `agent._call_llm()` | Node retry policy handles retries |
| Queue exhausted without terminal node | `RuntimeError("No terminal node in queue")` | `ensure_terminal()` should prevent this |
| Empty NodeQueue (no nodes) | Call agent._call_llm() once (passthrough), return its output | Expected for M1.1 — no concrete nodes yet; verifies wiring |

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

4. **Decision**: Use `max_iterations=50` (10x SDK BaseLoop default of 5).
   - **Reason**: TinyCUA's multi-node architecture may require multiple LLM calls per query. The SDK default of 5 is too low for node queue execution. `TinyCUALoop` overrides the BaseLoop default to prevent premature iteration termination.
   - **Alternatives Considered**: Keep SDK default of 5 — rejected because it would cause the loop to abort before completing a full node queue traversal.

5. **Decision**: `CompactionStrategy` is a placeholder type for Milestone 1.1.
   - **Reason**: Compaction strategy is a Phase 2 concern (see Implementation Phases). For M1.1, `SessionConfig.compaction_strategy` should use `Any | None = None` as a placeholder type until the compaction subsystem is implemented.
   - **Alternatives Considered**: Define a full `CompactionStrategy` enum/protocol now — rejected because it adds unnecessary scope to the factory milestone.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SDK `BaseLoop` interface changes between versions | Low | High | Pin SDK version in pyproject.toml; loop extension is minimal surface area |
| SDK renames or changes `_call_llm()` signature | Medium | High | Pin SDK version; `_call_llm` is the documented extension point for custom loops per SDK design docs |
| Empty NodeQueue causes infinite loop in `TinyCUALoop.run()` | Medium | Medium | Add guard: if queue is empty or has no terminal node, return empty string and log warning |
| Session model drift from SDK conventions | Low | Medium | Follow SDK Session patterns documented in `docs/design/models/session.md` |

---

## Open Questions _(optional)_

1. **Empty queue behavior**: Should `TinyCUALoop.run()` return an empty string or raise when the queue has no nodes? This is relevant until concrete nodes are added in later milestones.
   - **Status**: Decided
   - **Decision**: Call `agent._call_llm()` once with incoming messages (passthrough mode) and return its output. This verifies the factory → agent → loop → LLM wiring without node implementations and matches spec.md edge case (line 38). **(M1.1 only)**

2. **Async vs sync factory**: Should `create_tinycua_agent()` be async? Currently designed as sync since session creation and loop setup are synchronous.
   - **Status**: Decided
   - **Decision**: Keep sync. Async is only needed for `run()`. The factory signature in spec.md (line 46) is already sync.

---

## References

- Spec: `./spec.md`
- Implementation Plan: `./implementation-plan.md`
- Tasks: `./task.md`
- SDK BaseLoop: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- SDK Agent: `src/tinycua-sdk/tinycua_sdk/agent/agent.py`
- Design: `src/tinycua/docs/design/loops/overview.md`
- Design: `src/tinycua/docs/design/loops/base_loop.md`
- Design: `src/tinycua/docs/design/loops/tinycua_loop.md`
- Design: `src/tinycua/docs/design/config/session_config.md`
- Issue: https://github.com/VJyzCELERY/TINYCUA/issues/87
