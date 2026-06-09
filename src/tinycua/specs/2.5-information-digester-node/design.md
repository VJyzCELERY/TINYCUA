# Design Document: TinyCUAInformationDigesterNode

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-09

---

## Overview

This design implements `TinyCUAInformationDigesterNode`, a concrete `ProcessNode` that gathers and digests context for downstream nodes (primarily ResponseNode) when direct accumulated context or tool access is insufficient. The node creates a fresh session, receives selected input messages from its parent, optionally uses `enhanced_context_retrieval` for lazy scoped context access, produces structured `DigestedInformation` via `digest_information`, and propagates the digest back to its suspended parent via selected-output propagation. This milestone defines the node, its config, the `DigestedInformation` model, and the `enhanced_context_retrieval` shared contract. ResponseNode suspension path is deferred to Milestone 3.6.

---

## Architecture

### Component Overview

```
[ResponseNode] ──suspends──> [InformationDigesterNode(parent=ResponseNode)]
       │                              │
       │                    ┌─────────┴─────────┐
       │                    │ Fresh Session      │
       │                    │ Selected Input     │
       │                    │ enhanced_context_  │
       │                    │   retrieval (lazy) │
       │                    │ digest_information │
       │                    └─────────┬─────────┘
       │                              │
       │                    ┌─────────┴─────────┐
       │                    │ DigestedInformation│
       │                    │ or fallback        │
       │                    └─────────┬─────────┘
       │                              │
       │                    selected-output propagation
       │                              │
       └──────────resumes─────────────┘
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.information_digester.TinyCUAInformationDigesterNode` | New | Concrete ProcessNode for context gathering and digestion |
| `tinycua.config.node_config.TinyCUAInformationDigesterNodeConfig` | New | Config extending NodeConfigBase with retrieval/digest settings |
| `tinycua.models.digested_information.DigestedInformation` | New | Data model for structured digest output |
| `tinycua.loops.__init__` | Modified | Export new node and model |

---

## Data Model

### New Entities

```python
from dataclasses import dataclass, field

@dataclass
class DigestedInformation:
    """Structured output from InformationDigesterNode.
    
    Captures the useful context gathered and summarized by the digester
    for downstream consumption (primarily ResponseNode).
    
    Attributes:
        context_summary: High-level summary of gathered context.
        key_points: Most important facts or findings.
        advisory_instructions: Guidance for downstream nodes on how to use the context.
        constraints: Limitations or caveats about the gathered context.
        known_gaps: Information that was sought but not found.
    """
    context_summary: str = ""
    key_points: list[str] = field(default_factory=list)
    advisory_instructions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    known_gaps: list[str] = field(default_factory=list)


@dataclass
class TinyCUAInformationDigesterNodeConfig(NodeConfigBase):
    """Configuration for InformationDigesterNode.
    
    Extends NodeConfigBase with retrieval and digest-specific settings.
    
    Attributes:
        retrieval_enabled: Whether enhanced_context_retrieval is available.
        max_digest_sources: Maximum number of context sources to process.
        digest_schema: Optional schema for digest_information tool output validation.
    """
    retrieval_enabled: bool = True
    max_digest_sources: int | None = None
    digest_schema: dict | None = None
```

### Session Scope Rules

InformationDigesterNode follows strict session isolation:

1. **Fresh session**: Creates a new `Session` with its own `session_id`. Does not copy or inherit parent/root session.
2. **Selected input only**: Receives only `NodeInput.messages` from the parent. Does not receive full parent `session_context`.
3. **Lazy context access**: Accesses root/parent context lazily through `enhanced_context_retrieval` when needed.
4. **Own output only**: Stores only its own new local output (the digest). Does not re-store copied input messages.
5. **Forward to parent**: On termination, forwards output to the suspended parent via selected-output propagation.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
class TinyCUAInformationDigesterNode(ProcessNode):
    """ProcessNode that gathers and digests context for downstream nodes.
    
    Creates a fresh session, receives selected input from parent, optionally
    uses enhanced_context_retrieval for lazy context access, produces
    DigestedInformation via digest_information, and propagates digest to
    parent via selected-output propagation.
    
    Attributes:
        node_id: Always "information_digester" by default.
        parent: Suspended parent node (typically ResponseNode).
    """
    
    def __init__(
        self,
        node_id: str = "information_digester",
        config: NodeConfigBase | None = None,
        parent: Node | None = None,
    ) -> None:
        """Initialize InformationDigesterNode.
        
        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses TinyCUAInformationDigesterNodeConfig defaults if None.
            parent: Suspended parent node for session adoption and propagation targeting.
        """
    
    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute the context gathering and digestion.
        
        Lifecycle:
        1. Ensure fresh session (not inherited from parent).
        2. Convert NodeInput to messages for LLM context.
        3. Optionally invoke enhanced_context_retrieval for lazy context.
        4. Invoke digest_information to produce structured DigestedInformation.
        5. Return digest as LLMResult for propagation.
        
        Args:
            input: NodeInput with selected parent session_context messages
                   and optional digest request payload.
        
        Returns:
            LLMResult containing digested information or fallback continuation.
        """
    
    def _should_use_enhanced_retrieval(self) -> bool:
        """Check if enhanced_context_retrieval should be invoked.
        
        Returns:
            True if retrieval_enabled is True and context is insufficient.
        """
    
    def _invoke_enhanced_retrieval(self, messages: list[dict]) -> list[dict]:
        """Invoke enhanced_context_retrieval for lazy scoped context access.
        
        Lazily creates a scoped context cache file and runs a limited
        ReAct-style search over that cache. Search/read operations are
        limited to the cache.
        
        Args:
            messages: The selected input messages to search within.
        
        Returns:
            Additional context messages from the cache, or empty list.
        """
    
    def _produce_fallback(self, user_query: str) -> LLMResult:
        """Produce the no-useful-context fallback continuation.
        
        Args:
            user_query: The original user query from the input.
        
        Returns:
            LLMResult with fallback continuation message.
        """
    
    def _produce_digest(self, context: list[dict]) -> LLMResult:
        """Produce structured DigestedInformation from gathered context.
        
        Calls digest_information tool to produce structured output with
        context_summary, key_points, advisory_instructions, constraints,
        and known_gaps.
        
        Args:
            context: The gathered context messages.
        
        Returns:
            LLMResult containing digested information.
        """
    
    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Post-completion hook for queue mutations.
        
        Propagates digest output to the suspended parent node's session
        via selected-output propagation rule, then advances the queue
        so the parent resumes.
        
        Args:
            queue: The node queue (current node is InformationDigesterNode).
            response: The digest output or fallback continuation.
        """
```

### Enhanced Context Retrieval Contract

```python
def enhanced_context_retrieval(
    session_context: list[dict],
    *,
    max_sources: int | None = None,
) -> list[dict]:
    """Search scoped context and read-only exploration surfaces.
    
    Lazily creates a scoped session-context cache file and runs a
    limited ReAct-style search over that cache using grep/search
    and paginated read tools.
    
    Args:
        session_context: The selected context messages to cache and search.
        max_sources: Maximum number of context sources to process.
    
    Returns:
        Additional context messages found through retrieval, or empty list.
    
    Behavior:
        1. Receives the current session or selected session_context.
        2. Lazily creates a scoped context cache file when called.
        3. Cache contains only selected context for that session/tool call.
        4. Retrieval runs as ReAct-style search over the cache.
        5. Search/read tools limited to grep/search within cache and
           paginated cache reads.
    """
```

### Fallback Continuation Format

```python
def _build_fallback_message(user_query: str) -> str:
    """Build the no-useful-context fallback continuation.
    
    Args:
        user_query: The original user query.
    
    Returns:
        Fallback continuation message preserving the user query.
    """
    return (
        f"The user asked {user_query!r}. No useful extra information was found. "
        "Downstream should proceed with the user request and plan carefully "
        "before action."
    )
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Enhanced retrieval disabled | Proceed with available input only | No cache created; digest from input alone |
| Empty/null input messages | Return no-useful-context fallback | Fallback preserves user query from input |
| `digest_information` tool failure | Retry per `NodeRetryPolicy`, then fallback | Exhaustion produces fallback continuation |
| Cache creation failure | Log error, proceed with available context | Partial digest from input messages |
| `max_digest_sources` exceeded | Limit sources to configured max | Digest from allowed sources only |
| No session attached | `NodeExecutionError` | Consistent with ProcessNode behavior |
| Queue propagation failure | `NodeExecutionError` | Standard queue error handling |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `TinyCUAInformationDigesterNodeConfig` dataclass (FR-017)
- [ ] Create `DigestedInformation` dataclass (FR-010)
- [ ] Implement `TinyCUAInformationDigesterNode.__init__()` with parent parameter (FR-001, FR-018)
- [ ] Implement `__call__()` with fresh session creation (FR-002, FR-003, FR-004)
- [ ] Implement `_should_use_enhanced_retrieval()` (FR-006)
- [ ] Implement `_invoke_enhanced_retrieval()` with cache behavior (FR-007, FR-008)
- [ ] Implement `_produce_digest()` calling `digest_information` (FR-009, FR-010)
- [ ] Implement `_produce_fallback()` with user query preservation (FR-011, FR-013)
- [ ] Implement `on_complete()` with selected-output propagation (FR-005, FR-012)
- [ ] Verify tool scope: only `enhanced_context_retrieval` and `digest_information` (FR-013)
- [ ] Add to `tinycua/loops/__init__.py` exports
- [ ] Write unit tests for all acceptance scenarios
- [ ] Write integration tests for response node suspension flow

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Implement ResponseNode suspension path to request InformationDigester **(deferred: Milestone 3.6)**
- [ ] Implement full `enhanced_context_retrieval` tool **(deferred: Milestone 4.2 Tool Scoping)**
- [ ] Implement `digest_information` as full LLM tool **(deferred: Milestone 4.2)**

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: InformationDigesterNode creates a fresh session rather than inheriting parent/root session
   - **Reason**: Isolates the digester's context from the parent, preventing pollution of either session. The digester's only output is the digest, which propagates back to the parent.
   - **Alternatives Considered**: Inherit parent session — rejected because it creates bidirectional context coupling and risks session state corruption.

2. **Decision**: `enhanced_context_retrieval` lazily creates a scoped cache rather than eagerly loading context
   - **Reason**: Lazy creation avoids unnecessary overhead when the tool is not called. Scoped cache ensures search operations are isolated and bounded.
   - **Alternatives Considered**: Eager context loading — rejected because it loads potentially large context into memory before the LLM decides what to search for.

3. **Decision**: Fallback continuation preserves the original user query
   - **Reason**: Downstream nodes (especially ResponseNode) need to know what the user asked to make informed decisions about proceeding without additional context.
   - **Alternatives Considered**: Generic fallback message — rejected because it loses the user intent context needed for downstream decision-making.

4. **Decision**: `digest_information` is an LLM-assisted tool call, not deterministic
   - **Reason**: Producing a structured summary from gathered context requires understanding and synthesis, which is best handled by the LLM.
   - **Alternatives Considered**: Deterministic extraction — rejected because raw extraction loses the summarization value that makes the digest useful.

5. **Decision**: InformationDigesterNode is optional and invoked only when direct context is insufficient
   - **Reason**: The architecture explicitly states the node is optional. ResponseNode and TaskExecutor should first evaluate whether accumulated context is enough before spawning the digester.
   - **Alternatives Considered**: Always spawn InformationDigesterNode — rejected because it adds unnecessary latency and LLM cost when context is already sufficient.

6. **Decision**: Tool scope limited to `enhanced_context_retrieval` and `digest_information`
   - **Reason**: The digester's role is context gathering and summarization. Access to outer Agent tools (web, shell, files) would exceed its responsibility and create security concerns.
   - **Alternatives Considered**: Include outer Agent tools — rejected because it violates the principle of least privilege and the architecture's tool scoping design.

7. **Decision**: `TinyCUAInformationDigesterNodeConfig` extends `NodeConfigBase`
   - **Reason**: Consistent with the per-node config pattern established by other nodes (QueryAnalyst, Worker, etc.). Additional fields control retrieval and digest behavior.
   - **Alternatives Considered**: Standalone config — rejected because it breaks the established config hierarchy pattern.

8. **Decision**: ResponseNode suspension path deferred to Milestone 3.6
   - **Reason**: The roadmap explicitly separates InformationDigesterNode implementation (Milestone 2.5) from ResponseNode's ability to request it (Milestone 3.6). This milestone focuses on the node itself.
   - **Alternatives Considered**: Implement suspension path in this milestone — rejected because it violates the milestone boundary and depends on ResponseNode behavior not yet implemented.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Fresh session creation could lose important parent context | Medium | High | Selected-input messages explicitly carry parent context; enhanced retrieval provides lazy access |
| `enhanced_context_retrieval` cache could grow unbounded | Low | Medium | `max_digest_sources` config limits sources; cache is scoped per tool call |
| Fallback continuation could confuse downstream nodes | Low | Medium | Fallback message is clearly formatted and preserves user query for context |
| LLM-assisted `digest_information` could produce inconsistent output | Medium | Medium | `digest_schema` config enables output validation; retry per NodeRetryPolicy |
| InformationDigesterNode could be spawned unnecessarily | Low | Low | Architecture requires ResponseNode/TaskExecutor to evaluate context sufficiency first |
| Tool scope enforcement could be bypassed | Low | High | NodeToolPolicy resolution in NodeConfigBase enforces tool restrictions at config level |

---

## References

- Spec: `./spec.md` — relative path from this design.md to its spec.md
- Related designs:
  - `src/tinycua/docs/design/loops/information_digester.md` — Target architecture design (baseline)
  - `src/tinycua/docs/design/tools/digester.md` — Tool design for enhanced context retrieval and digest
  - `src/tinycua/docs/design/models/digested_information.md` — DigestedInformation model spec
  - `src/tinycua/docs/design/loops/response.md` — ResponseNode design (suspension path, deferred to 3.6)
  - `src/tinycua/docs/design/loops/node_queue.md` — NodeQueue suspend_current_and_prepend pattern
  - `src/tinycua/docs/design/config/node_config.md` — TinyCUAInformationDigesterNodeConfig definition
  - `src/tinycua/docs/design/constants/tools.md` — Tool scope for InformationDigesterNode
  - `src/tinycua/docs/design/constants/instructions.md` — Instruction constants
  - `src/tinycua/specs/2.4-analysis-effort-node/spec.md` — Milestone 2.4 spec (prerequisite)
  - `src/tinycua/specs/2.4-analysis-effort-node/design.md` — Milestone 2.4 design (prerequisite)
