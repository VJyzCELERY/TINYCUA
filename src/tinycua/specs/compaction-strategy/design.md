# Design Document: CompactionStrategy Contract (Milestone 1.3)

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Last Updated**: 2026-06-06

---

## Overview

This design defines the `CompactionStrategy` class contract and `SimpleCompaction` default implementation for TinyCUA context compaction. When a node's session context exceeds limits, the session delegates to the configured strategy, which compacts messages into one assistant-role summary. The strategy owns its own configuration and may use an internal Agent — the explicit exception to the "no internal Agents" rule.

---

## Architecture

### Component Overview

```
SessionConfig
  · compaction_strategy: CompactionStrategy | None

Session
  · compact_context(window: list[dict] | None = None) → dict | None
      ↓
CompactionStrategy (abstract)
  · compact(messages: list[dict]) → dict
      ↓
SimpleCompaction (default implementation)
  · Inherits parent Agent config when available
  · Runs tool-less compaction Agent
  · Returns one assistant-role summary message
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/config/session_config.py` | Modified | Update `compaction_strategy` field type from `Any | None` to `CompactionStrategy | None` |
| `tinycua/models/session.py` | Modified | Add `compact_context()` method |
| `tinycua/compaction/__init__.py` | New | Package for compaction strategy classes |
| `tinycua/compaction/strategy.py` | New | `CompactionStrategy` abstract base class |
| `tinycua/compaction/simple.py` | New | `SimpleCompaction` default implementation |

---

## Data Model

### New Entities

```python
# Conceptual data shape (not necessarily the final class)
CompactionStrategy (ABC):
    @abstractmethod
    compact(messages: list[dict]) -> dict
        """Compact a list of messages into one assistant-role summary."""

SimpleCompaction(CompactionStrategy):
    parent_config: AgentConfigSnapshot | None  # inherited from parent Agent
    fallback_config: CompactionFallbackConfig   # documented defaults

    compact(messages: list[dict]) -> dict
        """Run tool-less compaction Agent and return summary."""
```

### Schema Changes

- `SessionConfig.compaction_strategy` type changes from `Any | None` to `CompactionStrategy | None`.
- `Session` gains `compact_context()` method.
- No migration needed; existing `SessionConfig` instances with `compaction_strategy=None` remain valid.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
from abc import ABC, abstractmethod
from typing import Any

class CompactionStrategy(ABC):
    """Abstract base class for context compaction strategies."""

    @abstractmethod
    def compact(self, messages: list[dict]) -> dict:
        """
        Compact a list of messages into one assistant-role summary.

        Args:
            messages: List of message dicts (typically session_context or
                     a node-selected subset).

        Returns:
            Exactly one assistant-role message:
            {"role": "assistant", "content": "<summary of compacted context>"}

        Raises:
            CompactionError: If compaction fails.
        """
        ...


class SimpleCompaction(CompactionStrategy):
    """Default simple compaction strategy using a tool-less compaction Agent."""

    def __init__(
        self,
        parent_config: dict[str, Any] | None = None,
        fallback_config: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize SimpleCompaction.

        Args:
            parent_config: Parent SDK Agent configuration snapshot (model,
                          provider, etc.). Used when available.
            fallback_config: Documented default fallback configuration when
                           no parent config exists.
        """
        ...

    def compact(self, messages: list[dict]) -> dict:
        """
        Run a tool-less compaction Agent over the messages and return
        the final response as one assistant-role summary.

        Behavior:
        1. Use parent_config when available, fallback_config otherwise.
        2. Create a small compaction Agent with no tools.
        3. Use system instruction: "You are a compaction agent."
        4. Use continuation prompt: "Summarize the session into one compact summary."
        5. Return Agent's final response as:
           {"role": "assistant", "content": response}
        """
        ...


# Session.compact_context() signature
class Session:
    def compact_context(
        self, window: list[dict] | None = None
    ) -> dict | None:
        """
        Compact session context using the configured strategy.

        Args:
            window: Explicit message window to compact. If None, the session
                   selects a compactable window from session_context.

        Returns:
            The assistant-role summary message if compaction occurred,
            or None if no strategy is configured or no compaction needed.
        """
        ...


# SessionConfig field type change
@dataclass
class SessionConfig:
    compaction_strategy: CompactionStrategy | None = None  # was Any | None
    max_context_messages: int | None = 100
    max_context_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `compact()` fails internally | `CompactionError("Compaction failed: ...")` | Wrapped exception from strategy |
| `SimpleCompaction` Agent unreachable | `CompactionError("Compaction Agent connection failed")` | Propagated from Agent |
| `compact()` called with empty list | Returns assistant message with empty/minimal content | Strategy responsibility |
| `compact_context()` with no strategy | Returns `None` | No compaction occurs |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Define `CompactionStrategy` abstract base class in `tinycua/compaction/strategy.py`
- [ ] Define `SimpleCompaction` default implementation in `tinycua/compaction/simple.py`
- [ ] Update `SessionConfig.compaction_strategy` field type from `Any | None` to `CompactionStrategy | None`
- [ ] Implement `Session.compact_context()` method
- [ ] Write unit tests for `CompactionStrategy` contract
- [ ] Write unit tests for `SimpleCompaction` behavior
- [ ] Write unit tests for `Session.compact_context()` integration
- [ ] Write integration test: end-to-end compaction with mocked LLM

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Advanced compaction strategies (e.g., token-aware, sliding window, hierarchical)
- [ ] Compaction metrics and logging
- [ ] Compaction-triggered events for nodes

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

Document key decisions and the reasoning behind them:

1. **Decision**: Use ABC with `@abstractmethod` for `CompactionStrategy` rather than Protocol.
   - **Reason**: Enforces the contract at class definition time; implementation errors are caught early. ABC is more explicit for a contract that must be implemented.
   - **Alternatives Considered**: Protocol — rejected because it allows structural typing which could lead to silent contract violations.

2. **Decision**: `SimpleCompaction` receives parent config snapshot during initialization, not during `compact()`.
   - **Reason**: Strategy does not need the live Agent object during compaction; a snapshot is sufficient and keeps the strategy decoupled from the Agent lifecycle.
   - **Alternatives Considered**: Pass Agent reference to `compact()` — rejected because it couples strategy to Agent lifetime and complicates testing.

3. **Decision**: `Session.compact_context()` returns `None` when no strategy is configured rather than raising an error.
   - **Reason**: Compaction is optional; nodes should be able to handle the case gracefully without try/except for a normal configuration state.
   - **Alternatives Considered**: Raise `CompactionNotConfiguredError` — rejected because it forces error handling for a valid configuration.

4. **Decision**: System-role message exclusion is the caller's responsibility, not the strategy's.
   - **Reason**: Different nodes may have different needs for what context to compact. The strategy should be generic and process whatever messages it receives.
   - **Alternatives Considered**: Strategy automatically filters system messages — rejected because it removes caller control and complicates the strategy contract.

5. **Decision**: Create a new `tinycua/compaction/` package rather than placing classes in `tinycua/config/`.
   - **Reason**: Compaction is a behavior/algorithm concern, not a configuration concern. The package separation reflects the architectural distinction between "selecting a strategy" (config) and "implementing a strategy" (compaction).
   - **Alternatives Considered**: Place in `tinycua/config/compaction.py` — rejected because it conflates configuration with implementation.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SimpleCompaction Agent fails or is slow | Med | Med | Implement timeout and fallback behavior; document error propagation |
| Compaction produces poor summaries | Low | Med | SimpleCompaction uses clear instructions; advanced strategies in Phase 2 |
| Session.compact_context() race conditions | Low | Low | compaction is node-initiated and sequential in TinyCUALoop |
| Breaking change from `Any | None` to `CompactionStrategy | None` | Low | Low | Existing `None` values remain valid; only explicit non-None values need to conform |

---

## Open Questions _(optional)_

1. **CompactionFallbackConfig defaults**: What model/endpoint should `SimpleCompaction` use when no parent config exists?
   - **Current thinking**: Use SDK default model/endpoint configuration. Document the specific defaults in implementation.

2. **CompactionError hierarchy**: Should `CompactionError` be a single exception or have subclasses?
   - **Current thinking**: Start with single `CompactionError`; add subclasses if needed in Phase 2.

---

## References

- Spec: `./spec.md` — relative path from this design.md to its spec.md
- Design docs: `src/tinycua/docs/design/utility/compaction.md` — target architecture for compaction
- Design docs: `src/tinycua/docs/design/config/session_config.md` — SessionConfig target architecture
- Design docs: `src/tinycua/docs/design/models/session.md` — Session target architecture
- Related designs: `src/tinycua/specs/session-config/` — SessionConfig milestone 1.2
