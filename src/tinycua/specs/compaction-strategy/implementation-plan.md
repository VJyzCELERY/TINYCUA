# Implementation: CompactionStrategy Contract (Milestone 1.3)

Defines the `CompactionStrategy` class contract and `SimpleCompaction` default implementation, enabling context compaction for TinyCUA sessions when context limits are exceeded. Replaces the current `Any | None` placeholder on `SessionConfig` with a typed strategy contract.

## Context

- **Spec Reference**: [`./spec.md`](./spec.md)
- **Design Reference**: [`./design.md`](./design.md)
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed (integration tests use mocked LLM)

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/integration/test_compaction_integration.py
"""Integration tests for CompactionStrategy (Milestone 1.3)."""

import pytest
from unittest.mock import AsyncMock, patch

from tinycua.compaction.simple import SimpleCompaction
from tinycua.compaction.strategy import CompactionStrategy
from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.models.session import Session


class TestCompactionStrategyContract:
    """Verify the CompactionStrategy ABC enforces the contract."""

    def test_compaction_strategy_is_abstract(self):
        """CompactionStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CompactionStrategy()

    def test_compaction_strategy_requires_compact(self):
        """Subclass without compact() cannot be instantiated."""
        class IncompleteStrategy(CompactionStrategy):
            pass

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_concrete_strategy_compact_returns_assistant_message(self):
        """A valid strategy returns exactly one assistant-role message."""
        class DummyStrategy(CompactionStrategy):
            def compact(self, messages):
                return {"role": "assistant", "content": "summary"}

        strategy = DummyStrategy()
        result = strategy.compact([{"role": "user", "content": "hello"}])
        assert result == {"role": "assistant", "content": "summary"}


class TestSimpleCompaction:
    """Verify SimpleCompaction behavior with mocked Agent."""

    @pytest.mark.asyncio
    async def test_simple_compaction_returns_assistant_message(self):
        """SimpleCompaction.compact() returns one assistant-role message."""
        strategy = SimpleCompaction()
        messages = [
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
            {"role": "user", "content": "And 3+3?"},
        ]

        # Note: Testing internal behavior via private method
        with patch.object(strategy, "_run_compaction_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "The session covered basic arithmetic: 2+2=4 and 3+3=6."
            result = await strategy.compact(messages)

        assert result["role"] == "assistant"
        assert "arithmetic" in result["content"]

    def test_simple_compaction_toolless(self):
        """SimpleCompaction creates Agent with no tools."""
        strategy = SimpleCompaction()
        # Verify no tools are passed to the compaction Agent via public property
        assert strategy.tools == []

    def test_simple_compaction_uses_parent_config(self):
        """SimpleCompaction inherits model/provider from parent config."""
        parent_config = {"model": "gpt-4", "provider": "openai"}
        strategy = SimpleCompaction(parent_config=parent_config)
        assert strategy.parent_config == parent_config

    def test_simple_compaction_fallback_config(self):
        """SimpleCompaction uses fallback when no parent config."""
        strategy = SimpleCompaction()
        assert strategy.parent_config is None
        # Fallback config is tested implicitly: compact() succeeds without parent_config
        # by using built-in defaults (see test_simple_compaction_returns_assistant_message)
        assert strategy.fallback_config is not None
        assert "model" in strategy.fallback_config
        assert "provider" in strategy.fallback_config

    @pytest.mark.asyncio
    async def test_simple_compaction_empty_message_list(self):
        """compact() with empty message list returns assistant message with minimal content."""
        strategy = SimpleCompaction()
        # Note: Testing internal behavior via private method
        with patch.object(strategy, "_run_compaction_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""
            result = await strategy.compact([])

        assert result["role"] == "assistant"
        assert isinstance(result["content"], str)


class TestSessionCompactContext:
    """Verify Session.compact_context() integration with strategy."""

    def test_compact_context_returns_none_when_no_strategy(self):
        """compact_context() returns None when no strategy configured."""
        session = Session()
        result = session.compact_context()
        assert result is None

    def test_compact_context_delegates_to_strategy(self):
        """compact_context() calls the configured strategy."""
        strategy = SimpleCompaction()
        session = Session(
            session_config=SessionConfig(compaction_strategy=strategy)
        )
        session.session_context = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]

        with patch.object(strategy, "compact") as mock_compact:
            mock_compact.return_value = {"role": "assistant", "content": "summary"}
            result = session.compact_context()

        assert result == {"role": "assistant", "content": "summary"}
        mock_compact.assert_called_once()

    def test_compact_context_with_explicit_window(self):
        """compact_context(window=...) uses the provided window."""
        strategy = SimpleCompaction()
        session = Session(
            session_config=SessionConfig(compaction_strategy=strategy)
        )
        window = [{"role": "user", "content": "subset"}]

        with patch.object(strategy, "compact") as mock_compact:
            mock_compact.return_value = {"role": "assistant", "content": "subset summary"}
            result = session.compact_context(window=window)

        mock_compact.assert_called_once_with(window)
        assert result["content"] == "subset summary"


class TestFactoryIntegration:
    """Verify factory creates SimpleCompaction with parent config."""

    def test_factory_initializes_simple_compaction(self):
        """create_tinycua_agent() initializes SimpleCompaction with parent config."""
        strategy = SimpleCompaction()
        config = SessionConfig(compaction_strategy=strategy)
        agent = create_tinycua_agent(session_config=config)
        assert agent.loop.session_config.compaction_strategy is strategy
```

### Key Test Scenarios

- [ ] **Scenario 1**: CompactionStrategy ABC cannot be instantiated directly — enforces contract at class definition time
- [ ] **Scenario 2**: SimpleCompaction.compact() returns exactly one assistant-role message with mocked LLM
- [ ] **Scenario 3**: Session.compact_context() delegates to strategy and returns summary
- [ ] **Scenario 4**: Session.compact_context() returns None when no strategy configured
- [ ] **Edge case**: compact() with empty message list returns assistant message with minimal content
- [ ] **Edge case**: compact_context() with explicit window passes that window to strategy

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for CompactionStrategy contract — test ABC enforcement, method signature
- [ ] Unit tests for SimpleCompaction — test parent config inheritance, fallback, tool-less Agent
- [ ] Unit tests for Session.compact_context() — test delegation, None returns, window passing
- [ ] Update existing test_session_config.py — replace string `compaction_strategy` with proper type
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify `CompactionStrategy` is importable from `tinycua.compaction`
- [ ] Verify `SessionConfig` accepts `CompactionStrategy | None` typing
- [ ] Verify `Session.compact_context()` works with `SimpleCompaction` and a real local model endpoint

### Performance Considerations

- [ ] Compaction adds one LLM call per compact_context() invocation — acceptable for context reduction

## Proposed Changes

### Compaction Package (New)

#### [NEW] `tinycua/compaction/__init__.py`

- **Description**: Package init exporting `CompactionStrategy`, `SimpleCompaction`, `CompactionError`
- **Dependencies**: `strategy.py`, `simple.py`, `errors.py`

#### [NEW] `tinycua/compaction/errors.py`

- **Description**: `CompactionError` exception class for compaction failures
- **Dependencies**: None

#### [NEW] `tinycua/compaction/strategy.py`

- **Description**: `CompactionStrategy` abstract base class with `@abstractmethod compact(messages: list[dict]) -> dict`
- **Dependencies**: `abc.ABC`, `abc.abstractmethod`
- **Rationale**: ABC with `@abstractmethod` enforces the contract at class definition time (design decision #1)

#### [NEW] `tinycua/compaction/simple.py`

- **Description**: `SimpleCompaction` default implementation that runs a tool-less compaction Agent
- **Dependencies**: `CompactionStrategy`, SDK `Agent`
- **Rationale**: Receives parent config snapshot during init, not during compact() (design decision #2)

### Config Module (Modified)

#### [MODIFY] `tinycua/config/session_config.py`

- **Description of change**: Update `compaction_strategy` field type from `Any | None` to `CompactionStrategy | None`. Remove `Any` import if no longer needed.
- **Breaking change**: Existing code passing non-`CompactionStrategy` values to `compaction_strategy` will fail type checking. Runtime `None` values remain valid.

#### [MODIFY] `tinycua/config/__init__.py`

- **Description of change**: Add `CompactionStrategy` and `SimpleCompaction` to `__all__` exports
- **Rationale**: Makes strategy classes available via `from tinycua.config import ...`

### Models Module (Modified)

#### [MODIFY] `tinycua/models/session.py`

- **Description of change**: Implement `compact_context(window: list[dict] | None = None) -> dict | None` — replace the no-op placeholder with real logic that: (1) checks for configured strategy, (2) selects window from session_context if not provided, (3) calls strategy.compact(), (4) replaces compacted window in session_context, (5) returns the summary or None.
- **Rationale**: This is the core integration point between Session and CompactionStrategy

### Tests (New / Modified)

#### [NEW] `tests/unit/test_compaction_strategy.py`

- **Description**: Unit tests for CompactionStrategy ABC — contract enforcement, method signature validation
- **Dependencies**: `tinycua.compaction.strategy`

#### [NEW] `tests/unit/test_simple_compaction.py`

- **Description**: Unit tests for SimpleCompaction — parent config, fallback, tool-less Agent, compact() return value
- **Dependencies**: `tinycua.compaction.simple`

#### [MODIFY] `tests/unit/test_session.py`

- **Description**: Update `test_compact_context_is_noop` to test real behavior (returns None when no strategy, delegates when strategy configured)
- **Dependencies**: `tinycua.compaction.simple`, `tinycua.config.session_config`

#### [MODIFY] `tests/unit/test_session_config.py`

- **Description**: Update `test_session_config_custom_values` to use `SimpleCompaction()` instead of string `"sliding_window"` for `compaction_strategy`
- **Dependencies**: `tinycua.compaction.simple`

#### [NEW] `tests/integration/test_compaction_integration.py`

- **Description**: End-to-end integration tests with mocked LLM — full compaction flow
- **Dependencies**: All compaction modules, Session, SessionConfig

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/compaction/` | New | Package for compaction strategy classes |
| `tinycua/compaction/strategy.py` | New | `CompactionStrategy` ABC |
| `tinycua/compaction/simple.py` | New | `SimpleCompaction` default implementation |
| `tinycua/compaction/errors.py` | New | `CompactionError` exception |
| `tinycua/config/session_config.py` | Modify | Type `compaction_strategy` as `CompactionStrategy \| None` |
| `tinycua/models/session.py` | Modify | Implement `compact_context()` method |
| `tinycua/factory.py` | Modify | Ensure `create_tinycua_agent()` passes parent config to `SimpleCompaction` |

## Data Model Changes

```python
# New exception
class CompactionError(Exception):
    """Raised when compaction fails."""

# New ABC
class CompactionStrategy(ABC):
    @abstractmethod
    async def compact(self, messages: list[dict]) -> dict:
        """Compact messages into one assistant-role summary."""

# New implementation
class SimpleCompaction(CompactionStrategy):
    def __init__(self, parent_config=None, fallback_config=None) -> None: ...
    @property
    def tools(self) -> list: ...  # Returns compaction Agent tools (empty for SimpleCompaction)
    @property
    def fallback_config(self) -> dict: ...  # Returns fallback model/provider config
    async def compact(self, messages: list[dict]) -> dict: ...

# Modified field
@dataclass
class SessionConfig:
    compaction_strategy: CompactionStrategy | None = None  # was Any | None

# Modified method
class Session:
    def compact_context(self, window: list[dict] | None = None) -> dict | None: ...
```

## API Changes

### New Classes

| Class | Module | Description |
|-------|--------|-------------|
| `CompactionStrategy` | `tinycua.compaction.strategy` | ABC for context compaction strategies |
| `SimpleCompaction` | `tinycua.compaction.simple` | Default tool-less compaction Agent implementation |
| `CompactionError` | `tinycua.compaction.errors` | Exception for compaction failures |

### New Properties

| Property | Module | Description |
|----------|--------|-------------|
| `SimpleCompaction.tools` | `tinycua.compaction.simple` | Read-only property returning the compaction Agent's tool list |
| `SimpleCompaction.fallback_config` | `tinycua.compaction.simple` | Read-only property returning the fallback model/provider config |

### Modified Signatures

| Module | Change |
|--------|--------|
| `SessionConfig.compaction_strategy` | `Any \| None` → `CompactionStrategy \| None` |
| `Session.compact_context()` | `() -> None` → `(window: list[dict] \| None = None) -> dict \| None` |

## Dependencies

### External Dependencies

- [x] None — all dependencies already exist in the project

### Internal Dependencies

- [x] Depends on SDK `Agent` class for SimpleCompaction's internal compaction Agent
- [x] Depends on SessionConfig (already exists)
- [x] Depends on Session (already exists)
- [x] Blocks: Phase 2 advanced compaction strategies (not in scope)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SimpleCompaction Agent fails or is slow | Medium | Implement timeout and fallback behavior; document error propagation in CompactionError |
| Compaction produces poor summaries | Low | SimpleCompaction uses clear instructions; advanced strategies deferred to Phase 2 |
| Breaking type change on SessionConfig | Low | Existing `None` values remain valid; only explicit non-None values need to conform |
| Session.compact_context() race conditions | Low | Compaction is node-initiated and sequential in TinyCUALoop |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-06*
