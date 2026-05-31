# Compaction Strategy

> **File:** `docs/design/utility/compaction.md`
> **Package:** `tinycua.utility.compaction`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`BaseCompaction` is a serializable, callable strategy for compressing session context
messages. Each Session stores a concrete compaction instance. When context-window
pressure is detected, `_check_compaction()` calls the stored strategy, which compresses
`session_context` into a single summary turn.

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

    Stored on Session.compaction_strategy. Passed as the summarize_fn
    to Session.compact(). Implements __call__ so it can be invoked
    directly.

    Subclasses can add persistent fields for intermediate data storage.
    For example, ParallelCompaction might store compaction snapshots that
    accumulate over multiple compaction cycles.
    """

    config: dict[str, Any] = field(default_factory=dict)
    # Configuration for the compaction algorithm (model, prompt template, etc.)

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

`Session` stores the compaction strategy instance:

```python
# In Session:
compaction_strategy: BaseCompaction | None = None

def _check_compaction(self) -> None:
    """Check if session_context exceeds the context window."""
    if self.compaction_strategy is None:
        return
    context_window = getattr(
        self.agent_state.agent_config.model, "context_window", None
    )
    if context_window is None:
        return

    estimated_tokens = sum(
        len(msg.get("content", "")) for msg in self.session_context
    ) // 4

    if estimated_tokens > context_window:
        self.compact(self.compaction_strategy)
```

`compact()` already accepts a `summarize_fn` parameter, and `BaseCompaction` is
callable — the instance is passed directly:

```python
self.compact(self.compaction_strategy)
# Equivalent to: self.compaction_strategy(self.session_context)
```

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
This means a Session with a compaction strategy can be persisted and restored with
strategy state intact.

```python
# Save:
session.to_dict()
# → {"compaction_strategy": {"config": {...}, "snapshots": [...]}, ...}

# Restore:
session = Session.from_dict(data)
# session.compaction_strategy is a ParallelCompaction with its snapshots
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Callable + StateObject | `BaseCompaction(StateObject)` with `__call__` | Passed as `summarize_fn`; persists alongside session |
| Strategy on Session | `Session.compaction_strategy` | Per-session configurable; serialized with session |
| No default summarizer stub | Removed `_default_summarize` from Session | Stub had no real logic; strategy injection is the contract |
| Extensible via subclass | `BaseCompaction` can add persistent data | Supports advanced patterns like snapshot accumulation |


---


---

## See also

Prev : [Orchestrator-Call Tools](../tools/agent_calls.md)
