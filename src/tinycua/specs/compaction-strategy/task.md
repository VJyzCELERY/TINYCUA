# Tasks: CompactionStrategy Contract (Milestone 1.3)

Implementation tasks for CompactionStrategy Contract. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write unit tests for CompactionStrategy ABC contract (test_compaction_strategy.py) <!-- id: 0 -->
  - [x] Test ABC cannot be instantiated directly
  - [x] Test subclass without compact() cannot be instantiated
  - [x] Test concrete subclass with compact() works
  - [x] Test compact() signature accepts list[dict] and returns dict
- [x] Write unit tests for SimpleCompaction (test_simple_compaction.py) <!-- id: 1 -->
  - [x] Test compact() returns one assistant-role message
  - [x] Test tool-less Agent (no tools passed)
  - [x] Test parent config inheritance
  - [x] Test fallback config when no parent config
  - [x] Test compact() with empty message list
- [x] Write unit tests for Session.compact_context() (update test_session.py) <!-- id: 2 -->
  - [x] Test returns None when no strategy configured
  - [x] Test delegates to strategy when configured
  - [x] Test passes explicit window to strategy
  - [x] Test replaces compacted window in session_context
- [x] Write integration tests (test_compaction_integration.py) <!-- id: 3 -->
  - [x] Test full compaction flow with mocked LLM
  - [x] Test factory initializes SimpleCompaction with parent config
  - [x] Test end-to-end session.compact_context() with SimpleCompaction
- [x] Run all tests — expect RED (failures since no implementation yet) <!-- id: 4 -->

## Implementation Phase

- [x] Create `tinycua/compaction/errors.py` — CompactionError exception <!-- id: 5 -->
- [x] Create `tinycua/compaction/strategy.py` — CompactionStrategy ABC <!-- id: 6 -->
  - [x] Define abstract compact(messages: list[dict]) -> dict method
  - [x] Add docstring with Args/Returns/Raises
- [x] Create `tinycua/compaction/simple.py` — SimpleCompaction implementation <!-- id: 7 -->
  - [x] __init__ with parent_config and fallback_config params
  - [x] compact() method that runs tool-less compaction Agent
  - [x] tools property returns empty list — compaction Agent has no tools
  - [x] fallback_config property returns sensible defaults
  - [x] _run_compaction_agent() creates Agent with no tools and simple instruction
- [x] Create `tinycua/compaction/__init__.py` — package exports <!-- id: 8 -->
  - [x] Export CompactionStrategy, SimpleCompaction, CompactionError
- [x] Update `tinycua/config/session_config.py` — type compaction_strategy <!-- id: 9 -->
  - [x] Change field type from `Any | None` to `CompactionStrategy | None`
  - [x] Add TYPE_CHECKING import for CompactionStrategy
  - [x] Remove Any import if no longer needed
- [x] Update `tinycua/config/__init__.py` — export new classes <!-- id: 10 -->
  - [x] Add CompactionStrategy and SimpleCompaction to __all__
- [x] Implement `Session.compact_context()` in `tinycua/models/session.py` <!-- id: 11 -->
  - [x] Check for configured strategy — return None if not set
  - [x] Select compactable window from session_context if window not provided
  - [x] Call strategy.compact(window)
  - [x] Replace compacted window in session_context with summary
  - [x] Return summary or None
- [x] No changes needed — Session is already importable from `tinycua.models.session` <!-- id: 12 -->

## Testing Phase

- [x] Run unit tests — expect GREEN (all pass) <!-- id: 13 -->
  - [x] `cd src/tinycua && uv run pytest tests/unit/test_compaction_strategy.py -v`
  - [x] `cd src/tinycua && uv run pytest tests/unit/test_simple_compaction.py -v`
  - [x] `cd src/tinycua && uv run pytest tests/unit/test_session.py -v`
- [x] Run integration tests — expect GREEN <!-- id: 14 -->
  - [x] `cd src/tinycua && uv run pytest tests/integration/test_compaction_integration.py -v`
- [x] Run full test suite — confirm no regressions <!-- id: 15 -->
  - [x] `cd src/tinycua && uv run pytest`

## Verification Phase

- [x] Verify CompactionStrategy is importable from tinycua.compaction <!-- id: 16 -->
- [x] Verify SessionConfig accepts CompactionStrategy | None typing <!-- id: 17 -->
- [x] Verify Session.compact_context() returns None when no strategy <!-- id: 18 -->
- [ ] Verify SimpleCompaction works with a real local model endpoint <!-- id: 19 -->

## Documentation Phase

- [x] Update spec.md status tracker — mark implemented items <!-- id: 20 -->
- [x] Update design.md implementation phases — mark Phase 1 items complete <!-- id: 21 -->

## Review and Merge

- [ ] Address any review feedback <!-- id: 22 -->
- [ ] Merge to base branch <!-- id: 23 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-07*
