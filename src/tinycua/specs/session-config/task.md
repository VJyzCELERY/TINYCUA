# Tasks: SessionConfig, Node Config, and Local Model Config (Milestone 1.2)

Implementation tasks for SessionConfig, Node Config, and Local Model Config. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests (defined in implementation-plan.md) <!-- id: 0 -->
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [x] Create NodeConfigBase and policy dataclasses <!-- id: 2 -->
  - [x] Create `tinycua/config/node_config.py` with NodeMessagePolicy, NodeToolPolicy, NodeStreamPolicy, NodeRetryPolicy
  - [x] Create NodeConfigBase with all policy fields and append-only customization
  - [x] Add tool resolution logic to NodeToolPolicy
  - [x] Add validation to NodeRetryPolicy (max_attempts >= 0)
- [x] Create SystemPrompt and SystemPromptBuilder <!-- id: 3 -->
  - [x] Create `tinycua/config/system_prompt.py` with SystemPrompt dataclass
  - [x] Implement SystemPromptBuilder with add_static(), add_configurable_append(), add_dynamic_context()
  - [x] Implement build() method that returns system-role message dict
- [x] Create LocalModelConfig <!-- id: 4 -->
  - [x] Create `tinycua/config/local_model.py` with LocalModelConfig dataclass
  - [x] Add proper defaults and validation
- [x] Create Todo and TodoItem <!-- id: 5 -->
  - [x] Create `tinycua/models/todo.py` with TodoItem dataclass
  - [x] Implement Todo class with append(), mark_done(), next_pending()
  - [x] Add max_items enforcement with ValueError
- [x] Update config package exports <!-- id: 6 -->
  - [x] Update `tinycua/config/__init__.py` to re-export new config classes
  - [x] Update `tinycua/models/__init__.py` to re-export Todo and TodoItem

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 7 -->
- [x] Write unit tests for NodeConfigBase and policies <!-- id: 8 -->
  - [x] Test NodeMessagePolicy defaults and custom values
  - [x] Test NodeToolPolicy resolution order (allow/deny precedence)
  - [x] Test NodeStreamPolicy defaults and custom values
  - [x] Test NodeRetryPolicy defaults, custom values, exhaustion behaviors
  - [x] Test NodeConfigBase construction with all policies
- [x] Write unit tests for SystemPromptBuilder <!-- id: 9 -->
  - [x] Test fragment ordering and priority
  - [x] Test build() output format
  - [x] Test empty fragments case
- [x] Write unit tests for Todo <!-- id: 10 -->
  - [x] Test append() and max_items limit
  - [x] Test mark_done() with valid and invalid indices
  - [x] Test next_pending() behavior
  - [x] Test TodoItem.order auto-assignment on append()
- [x] Write unit tests for LocalModelConfig <!-- id: 11 -->
  - [x] Test construction with required fields
  - [x] Test default values
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 12 -->

## Verification Phase

- [x] Verify all new modules import correctly <!-- id: 13 -->
- [x] Verify dataclasses are immutable where intended <!-- id: 14 -->
- [x] Verify LocalModelConfig can be used by nodes <!-- id: 15 -->
- [x] Check for any breaking changes to existing code <!-- id: 16 -->

## Documentation Phase

- [x] Update module docstrings <!-- id: 17 -->
- [x] Update any relevant README files <!-- id: 18 -->
- [x] Update changelog if applicable <!-- id: 19 -->

## Review and Merge

- [ ] Create pull request <!-- id: 20 -->
- [ ] Address review feedback <!-- id: 21 -->
- [ ] Merge to main branch <!-- id: 22 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-06*