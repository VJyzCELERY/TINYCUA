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

```python
from dataclasses import dataclass, field
from typing import Any

from tinycua.state.base import StateObject


@dataclass
class BaseCompaction(StateObject):
    """Compression strategy — callable, serializable, extensible.

    Stored on AgentConfigBase.compaction_strategy. Session accesses it through
    self.agent_state.agent_config.compaction_strategy.

    Implements __call__ so it can be invoked directly.
    check_compaction(session) is called by Session._check_compaction()
    to decide whether to compact.

    Subclasses can add persistent fields for intermediate data storage.
    For example, ParallelCompaction might store compaction snapshots that
    accumulate over multiple compaction cycles.
    """

    config: dict[str, Any] = field(default_factory=dict)
    # Configuration for the compaction algorithm (model, prompt template,
    # context window threshold, etc.).

    def check_compaction(self, session: "Session") -> None:
        """Check if the session's context exceeds the threshold and compact.

        Called by Session._check_compaction() after every session_context
        mutation. Derives the context window from session.agent_state and
        applies the strategy's policy for when compaction should trigger.

        Override in subclasses for custom policies (e.g., checkpoint-based
        thresholds instead of raw token counts).
        """
        context_window = self._get_context_window(session)
        if context_window is None:
            return

        estimated_tokens = self._estimate_tokens(session.session_context)
        if estimated_tokens > context_window:
            session.compact()

    def _get_context_window(self, session: "Session") -> int | None:
        """Derive context window from the session's agent config."""
        if session.agent_state is None or session.agent_state.agent_config is None:
            return None
        return getattr(
            session.agent_state.agent_config.model, "context_window", None
        )

    def _estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Estimate token count from messages. Override for accurate counting."""
        return sum(
            len(msg.get("content", "")) for msg in messages
        ) // 4

    def __call__(self, messages: list[dict[str, Any]]) -> str:
        """Compress messages into a single summary string.

        Override in subclasses. The default uses an LLM call to produce
        a concise summary of the conversation context.
        """
        raise NotImplementedError(
            "Subclasses must implement __call__"
        )
```

---

## Integration with Session

`Session` accesses the strategy through its `agent_state.agent_config`:

```python
# In AgentConfigBase:
compaction_strategy: BaseCompaction | None = None

# In Session:
# No dedicated compaction_strategy field — derived from agent_state.agent_config

def _check_compaction(self) -> None:
    """Delegate compaction check to the strategy from agent config."""
    strategy = self.agent_state.agent_config.compaction_strategy
    if strategy is not None:
        strategy.check_compaction(self)

def compact(self) -> None:
    """Replace session_context by delegating to the compaction strategy."""
    strategy = self.agent_state.agent_config.compaction_strategy
    summary = strategy(self.session_context)
    self.session_context = [{"role": "user", "content": summary}]
    self.compaction_count += 1
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

```python
@dataclass
class SimpleCompaction(BaseCompaction):
    """Compress the full session_context into a single summary via LLM.
    No persistent state beyond config.
    """

    def __call__(self, messages: list[dict]) -> str:
        # Single LLM call: "Summarize the following conversation..."
        ...
```

### `ParallelCompaction` (advanced)

```python
@dataclass
class ParallelCompaction(BaseCompaction):
    """Checkpoint-based compaction with snapshot accumulation.

    Instead of compacting near the full context, compact at configured
    checkpoints. When compaction triggers, merge accumulated snapshots
    into a dense summary.
    """

    snapshots: list[dict] = field(default_factory=list)
    # Persistent compaction checkpoints

    def __call__(self, messages: list[dict]) -> str:
        # Merge accumulated snapshots, produce summary
        ...
```

---

## Serialization

`BaseCompaction` extends `StateObject` — its fields (`config`, subclass fields like
`snapshots`) are automatically serialized/deserialized via `to_dict()`/`from_dict()`.
Since the strategy lives on `AgentConfigBase`, it is serialized as part of the agent
state (`agent_state.agent_config`), which is stored on the session.

```python
# Save:
session.to_dict()
# → {"agent_state": {"agent_config": {"compaction_strategy": {"config": {...}, "snapshots": [...]}}}, ...}

# Restore:
session = Session.from_dict(data)
# session.agent_state.agent_config.compaction_strategy is a ParallelCompaction
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
