# Compaction Strategy

> **File:** `docs/design/utility/compaction.md`
> **Package:** `tinycua.utility.compaction`
> **Last Updated:** 2026-06-02
> **Status:** Draft

---

## Role

`BaseCompaction` is a serializable, callable strategy for compressing session context
messages. It owns BOTH the policy for when to compact (`check_compaction`) and the
compression logic (`__call__`). Each agent config (`AgentConfigBase`) stores a concrete
compaction instance; Session inherits it via `agent_state.agent_config.compaction_strategy`.

The initial concrete implementation should be intentionally simple: create a small
summarizer agent using the `tinycua-sdk` `Agent` object, pass the current
`session_context` messages to that agent, and replace the context with the returned
summary. This summarizer agent is an implementation detail of the background compaction
strategy, not a TINYCUA architecture agent and not a tool available to other agents.

Subclasses can store persistent data (snapshots, checkpoints, intermediate summaries)
alongside the strategy itself.

---

## Class Contract

**File:** `tinycua/utility/compaction.py`

```text
BaseCompaction extends StateObject — callable, serializable, extensible compression strategy
    Stored on AgentConfigBase.compaction_strategy. Session accesses via
    self.agent_state.agent_config.compaction_strategy.

    · config: dict[str, Any] = {} — model, prompt template, context window threshold, etc.

    check_compaction(session: Session) → None
        · Called by Session._check_compaction() after every session_context mutation
        · context_window → self._get_context_window(session)
        · if context_window is None: return
        · estimated_tokens → self._estimate_tokens(session.session_context)
        · if estimated_tokens > context_window: session.compact()
        · Override in subclasses for custom policies (e.g., checkpoint-based thresholds)

    _get_context_window(session: Session) → int | None
        · Derive context window from session's agent config
        · if session.agent_state or agent_config is None: return None
        · return getattr(session.agent_state.agent_config.model, "context_window", None)

    _estimate_tokens(messages: list[dict[str, Any]]) → int
        · Estimate token count from messages (sum of content lengths // 4)
        · Override for accurate counting

    __call__(messages: list[dict[str, Any]]) → str
        · Compress messages into a single summary string
        · Override in subclasses (default raises NotImplementedError)

SimpleAgentCompaction extends BaseCompaction — initial concrete implementation
    · config: dict[str, Any]
        · name: str = "tinycua-context-compactor"
        · instructions: str = SIMPLE_COMPACTION_INSTRUCTION
        · model: LanguageModel | None = None
        · max_summary_chars: int | None = None

    _build_agent() → tinycua_sdk.Agent
        · Create a tinycua-sdk Agent configured as a context summarizer
        · Use no architecture-internal tools
        · Use config.model when provided, otherwise use the agent/session default model

    __call__(messages: list[dict[str, Any]]) → str
        · Convert session_context messages into a compact summarization prompt
        · Invoke the summarizer Agent
        · Return the final assistant text as the compacted context summary
        · If max_summary_chars is configured, request/validate a summary within that size
```

---

## Integration with Session

`Session` accesses the strategy through its `agent_state.agent_config`:

```text
AgentConfigBase field:
    · compaction_strategy: BaseCompaction | None = None

Session methods (no dedicated field — derived from agent_state.agent_config):

    _check_compaction() → None
        · strategy → self.agent_state.agent_config.compaction_strategy
        · if strategy is not None: strategy.check_compaction(self)

    compact() → None
        · strategy → self.agent_state.agent_config.compaction_strategy
        · summary → strategy(self.session_context)
        · self.session_context → [{"role": "user", "content": summary}]
        · self.compaction_count += 1
```

The strategy owns the full compaction lifecycle:
- `check_compaction(session)` — decides IF compaction should happen, calls `session.compact()`
- `__call__(messages)` — compresses messages into summary
- `config` — stores thresholds, model settings
- Subclass fields — persistent data (snapshots, history)

The strategy is stored per-agent via `AgentConfigBase.compaction_strategy`.
Each agent can have its own compaction policy; Session derives it automatically.

---

## Extensibility

`BaseCompaction` is designed to be subclassed. Implementations may vary in:

- Compression strategy (simple SDK Agent summarizer, checkpoint-based, parallel, etc.)
- When to trigger compaction (token threshold, message count, etc.)
- What to preserve during compaction (snapshots, summaries, etc.)

The `__call__` method must return a compressed summary string. The `check_compaction`
method controls when compaction triggers.

### Initial concrete strategy: `SimpleAgentCompaction`

The first implementation should be `SimpleAgentCompaction` (or an equivalently named
concrete subclass) and should do only one thing: summarize the current `session_context`
with a tinycua SDK `Agent` configured as a summarizer.

Required behavior:

- Build a tinycua SDK `Agent` object with summarization-focused instructions.
- Provide the current `session_context` as the summarization input.
- Preserve the architectural rule from `session-architecture.md`: compact the current
  `Context`, not raw `chat_history` from scratch.
- Return one summary string suitable for replacing `session.session_context`.
- Keep `chat_history`, `execution_log`, and token totals unchanged.
- Do not expose the summarizer as an architecture agent, AgentNode, graph node, or tool.
- Do not perform multi-stage, parallel, checkpoint, retrieval, or semantic-cache compaction
  in the initial implementation.

The summarizer prompt should instruct the SDK Agent to preserve:

- durable facts and constraints needed by downstream agents;
- unresolved questions or known gaps;
- important task/result context;
- source/provenance markers when present in the existing context;
- enough structure that Enhanced Context Retrieval can still search the compacted context.

The initial strategy may be synchronous or async depending on the SDK call path selected by
the implementation, but the public compaction contract remains callable and returns a
summary string.

---

## Serialization

`BaseCompaction` extends `StateObject` — its fields (`config`, subclass fields like
`snapshots`) are automatically serialized/deserialized via `to_dict()`/`from_dict()`.
Since the strategy lives on `AgentConfigBase`, it is serialized as part of the agent
state (`agent_state.agent_config`), which is stored on the session.

```text
Save:
    · session.to_dict()
    · → {"agent_state": {"agent_config": {"compaction_strategy": {"config": {...}, "snapshots": [...]}}}, ...}

Restore:
    · session → Session.from_dict(data)
    · session.agent_state.agent_config.compaction_strategy is a ParallelCompaction instance
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Callable + StateObject | `BaseCompaction(StateObject)` with `__call__` | Serializes alongside agent config; callable as summarize_fn |
| Strategy on AgentConfigBase | `AgentConfigBase.compaction_strategy` | Per-agent compaction policy; Session derives via `agent_state.agent_config` |
| Strategy owns compaction policy | `check_compaction(session)` on strategy | Strategy decides WHEN to compact; Session just delegates |
| Token estimation on strategy | `_estimate_tokens()` on BaseCompaction | Override for accurate counting or custom policies |
| Session derives strategy | `session.agent_state.agent_config.compaction_strategy` | No dedicated field on Session; naturally available via agent_state |
| Extensible via subclass | `BaseCompaction` can add persistent data | Supports advanced patterns like snapshot accumulation |
| Initial implementation | `SimpleAgentCompaction` using tinycua SDK `Agent` | Smallest useful implementation: a dedicated summarizer agent compresses current session context without adding graph/orchestration complexity |

---

## See also

Prev : [Task Tools](../tools/task.md)


## Related

- [Stored on AgentConfigBase.compaction_strategy](../config/agents.md)
- [Context window from AgentState.agent_config](../state/agent_state.md)
