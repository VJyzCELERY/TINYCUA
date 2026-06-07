# Design Document: TinyCUALoop SDK Integration

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-08
**Milestone**: 1.8 — TinyCUALoop SDK Integration

---

## Overview

This design implements TinyCUALoop as an SDK-compatible execution loop that extends BaseLoop. The loop owns a root session and NodeQueue, processes nodes sequentially, and calls agent._call_llm() for LLM interactions. This milestone establishes the foundational loop infrastructure without concrete node implementations.

---

## Architecture

### Component Overview

```
SDK Agent
└── TinyCUALoop (extends BaseLoop)
    ├── Root Session (owns input context, chat history)
    └── NodeQueue
        └── [StubNode] → [Terminal ResponseNode]
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| tinycua.loops.tinycua_loop | New | TinyCUALoop class extending BaseLoop |
| tinycua.models.session | Modified | Session class for root session |
| tinycua.loops.node_queue | Modified | Queue bootstrapping logic |
| tinycua.loops.node | Modified | Base Node interfaces |

---

## Data Model

### Conceptual Data Shapes

> Shapes below are conceptual overview; see implementation-plan.md for concrete Python definitions.

```python
# Conceptual data shape
TinyCUALoop:
    root_session: Session
    node_queue: NodeQueue
    
Session:
    input_context: list[dict]  # merged SDK messages
    chat_history: list[dict]   # append-only audit
    session_context: list[SessionContextEntry]
```

### Schema Changes

- Session class gains input_context, chat_history, session_context fields.
- NodeQueue gains ensure_terminal() method for ResponseNode guarantee.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
class TinyCUALoop(BaseLoop):
    """
    TinyCUA SDK-compatible execution loop.
    Extends BaseLoop without SDK API modifications.
    """
    
    def __init__(self, session: Session | None = None):
        """
        Create TinyCUALoop with optional existing session.
        If session is None, creates a new root session.
        """
    
    def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None,
        stream: bool
    ) -> str | AsyncIterator[dict]:
        """
        Execute the TinyCUA node queue.
        
        Args:
            agent: SDK Agent instance for _call_llm()
            messages: SDK-provided input messages
            tools: Outer tool pool for NodeToolPolicy
            override_instructions: Optional override instructions
            stream: Whether to stream events
            
        Returns:
            str when stream=False (final response)
            AsyncIterator[dict] when stream=True
        """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Empty queue after terminal | LoopError("No nodes to execute") | Should not happen with proper bootstrapping |
| LLM call failure | Propagate to node retry policy | Per NodeRetryPolicy.max_attempts |
| Invalid node output | Validation error, retry | Per node validation hooks |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create TinyCUALoop class extending BaseLoop
- [ ] Implement run() method with stream=False support
- [ ] Implement run() method with stream=True support
- [ ] Create root session with input_context, chat_history, session_context
- [ ] Implement message merging into root session
- [ ] Implement queue bootstrapping with terminal node guarantee
- [ ] Add node execution loop with agent._call_llm() integration
- [ ] Record chat history per node LLM call
- [ ] Record selected session context

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Monitor hook integration (optional, per design doc)
- [ ] Advanced error handling and recovery

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use a stub ProcessNode as placeholder entry node
   - **Reason**: QueryAnalyst is not implemented until Milestone 2.1; need minimal working queue
   - **Alternatives Considered**: Skip entry node — rejected because queue would be empty

2. **Decision**: Preserve BaseLoop.run() signature exactly
   - **Reason**: SDK compatibility requirement; no API modifications allowed
   - **Alternatives Considered**: Extend signature — rejected due to constraint

3. **Decision**: Agent._call_llm() for all LLM calls
   - **Reason**: Must use SDK-compatible execution path; cannot bypass agent
   - **Alternatives Considered**: Direct LLM calls — rejected due to SDK contract

4. **Decision**: TinyCUALoop accepts optional session, creates root session if None
   - **Reason**: Allows flexibility for testing and composition
   - **Alternatives Considered**: Always create internally — rejected; always require external — rejected

5. **Decision**: Stub entry node named "StubNode", advances immediately
   - **Reason**: Minimal working queue placeholder until QueryAnalyst in Milestone 2.1
   - **Alternatives Considered**: Skip entry node — rejected because queue would be empty

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| BaseLoop contract changes in SDK | Low | High | Pin SDK version; document contract assumptions |
| agent._call_llm() interface mismatch | Medium | High | Verify SDK version compatibility before implementation |
| Stream mode compatibility issues | Medium | Medium | Test both stream=True and stream=False thoroughly |
| Session context propagation complexity | Low | Medium | Keep session model simple; defer advanced propagation to later milestones |

---

## Open Questions — Resolved

1. **Should TinyCUALoop own session creation or accept it externally?**
   - **Status: Resolved** — Accept optional session, create if None. Allows flexibility for testing and composition.

2. **How should the stub entry node be named/identified?**
   - **Status: Resolved** — Use a simple "StubNode" that advances immediately. Will be replaced by QueryAnalyst in Milestone 2.1.

---

## References

- Spec: `./spec.md`
- SDK BaseLoop contract: `src/tinycua/docs/design/loops/base_loop.md`
- TinyCUALoop target architecture: `src/tinycua/docs/design/loops/tinycua_loop.md`
- Loop system overview: `src/tinycua/docs/design/loops/overview.md`
- Node design: `src/tinycua/docs/design/loops/node.md`
- NodeQueue design: `src/tinycua/docs/design/loops/node_queue.md`
