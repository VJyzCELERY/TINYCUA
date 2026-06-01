# Compaction Strategy

> **File:** `docs/design/utility/compaction.md`
> **Package:** `tinycua.utility.compaction`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`BaseCompaction` is a serializable, callable strategy for compressing session context
messages. It owns BOTH the policy for when to compact (`check_compaction`) and the
compression logic (`__call__`). Each agent config (`AgentConfigBase`) stores a concrete
compaction instance; Session inherits it via `agent_state.agent_config.compaction_strategy`.

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

## Extending

### `SimpleCompaction` (default)

```text
SimpleCompaction extends BaseCompaction
    Compress full session_context into a single summary via LLM.
    No persistent state beyond config.

    __call__(messages: list[dict]) → str
        · Single LLM call → "Summarize the following conversation..."
```

### `ParallelCompaction` (advanced)

```text
ParallelCompaction extends BaseCompaction
    Checkpoint-based compaction with snapshot accumulation.
    Compact at configured checkpoints instead of near full context.
    When compaction triggers, merge accumulated snapshots into a dense summary.

    · snapshots: list[dict] = [] — persistent compaction checkpoints

    __call__(messages: list[dict]) → str
        · Merge accumulated snapshots → produce summary
```

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


---


---

## See also

Prev : [Task Tools](../tools/task.md)


## Related

- [Stored on AgentConfigBase.compaction_strategy](../config/agents.md)
- [Context window from AgentState.agent_config](../state/agent_state.md)
