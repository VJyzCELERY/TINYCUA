# Tasks: CompactionStrategy Contract (Milestone 1.3)

Implementation tasks for CompactionStrategy Contract. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write unit tests for CompactionStrategy ABC contract (test_compaction_strategy.py) <!-- id: 0 -->
  - [ ] Test ABC cannot be instantiated directly
  - [ ] Test subclass without compact() cannot be instantiated
  - [ ] Test concrete subclass with compact() works
  - [ ] Test compact() signature accepts list[dict] and returns dict
- [ ] Write unit tests for SimpleCompaction (test_simple_compaction.py) <!-- id: 1 -->
  - [ ] Test compact() returns one assistant-role message
  - [ ] Test tool-less Agent (no tools passed)
  - [ ] Test parent config inheritance
  - [ ] Test fallback config when no parent config
  - [ ] Test compact() with empty message list
- [ ] Write unit tests for Session.compact_context() (update test_session.py) <!-- id: 2 -->
  - [ ] Test returns None when no strategy configured
  - [ ] Test delegates to strategy when configured
  - [ ] Test passes explicit window to strategy
  - [ ] Test replaces compacted window in session_context
- [ ] Write integration tests (test_compaction_integration.py) <!-- id: 3 -->
  - [ ] Test full compaction flow with mocked LLM
  - [ ] Test factory initializes SimpleCompaction with parent config
  - [ ] Test end-to-end session.compact_context() with SimpleCompaction
- [ ] Run all tests — expect RED (failures since no implementation yet) <!-- id: 4 -->

## Implementation Phase

- [ ] Create `tinycua/compaction/errors.py` — CompactionError exception <!-- id: 5 -->
- [ ] Create `tinycua/compaction/strategy.py` — CompactionStrategy ABC <!-- id: 6 -->
  - [ ] Define abstract compact(messages: list[dict]) -> dict method
  - [ ] Add docstring with Args/Returns/Raises
- [ ] Create `tinycua/compaction/simple.py` — SimpleCompaction implementation <!-- id: 7 -->
  - [ ] __init__ with parent_config and fallback_config params
  - [ ] compact() method that runs tool-less compaction Agent
  - [ ] tools property returns empty list — compaction Agent has no tools
  - [ ] fallback_config property returns sensible defaults
  - [ ] _run_compaction_agent() creates Agent with no tools and simple instruction
- [ ] Create `tinycua/compaction/__init__.py` — package exports <!-- id: 8 -->
  - [ ] Export CompactionStrategy, SimpleCompaction, CompactionError
- [ ] Update `tinycua/config/session_config.py` — type compaction_strategy <!-- id: 9 -->
  - [ ] Change field type from `Any | None` to `CompactionStrategy | None`
  - [ ] Add TYPE_CHECKING import for CompactionStrategy
  - [ ] Remove Any import if no longer needed
- [ ] Update `tinycua/config/__init__.py` — export new classes <!-- id: 10 -->
  - [ ] Add CompactionStrategy and SimpleCompaction to __all__
- [ ] Implement `Session.compact_context()` in `tinycua/models/session.py` <!-- id: 11 -->
  - [ ] Check for configured strategy — return None if not set
  - [ ] Select compactable window from session_context if window not provided
  - [ ] Call strategy.compact(window)
  - [ ] Replace compacted window in session_context with summary
  - [ ] Return summary or None
- [x] No changes needed — Session is already importable from `tinycua.models.session` <!-- id: 12 -->

## Testing Phase

- [ ] Run unit tests — expect GREEN (all pass) <!-- id: 13 -->
  - [ ] `cd src/tinycua && uv run pytest tests/unit/test_compaction_strategy.py -v`
  - [ ] `cd src/tinycua && uv run pytest tests/unit/test_simple_compaction.py -v`
  - [ ] `cd src/tinycua && uv run pytest tests/unit/test_session.py -v`
- [ ] Run integration tests — expect GREEN <!-- id: 14 -->
  - [ ] `cd src/tinycua && uv run pytest tests/integration/test_compaction_integration.py -v`
- [ ] Run full test suite — confirm no regressions <!-- id: 15 -->
  - [ ] `cd src/tinycua && uv run pytest`

## Verification Phase

- [ ] Verify CompactionStrategy is importable from tinycua.compaction <!-- id: 16 -->
- [ ] Verify SessionConfig accepts CompactionStrategy | None typing <!-- id: 17 -->
- [ ] Verify Session.compact_context() returns None when no strategy <!-- id: 18 -->
- [ ] Verify SimpleCompaction works with a real local model endpoint <!-- id: 19 -->

## Documentation Phase

- [ ] Update spec.md status tracker — mark implemented items <!-- id: 20 -->
- [ ] Update design.md implementation phases — mark Phase 1 items complete <!-- id: 21 -->

## Review and Merge

- [ ] Address any review feedback <!-- id: 22 -->
- [ ] Merge to base branch <!-- id: 23 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-06*
