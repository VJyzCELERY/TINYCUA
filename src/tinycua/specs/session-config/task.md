# Tasks: SessionConfig, Node Config, and Local Model Config (Milestone 1.2)

Implementation tasks for SessionConfig, Node Config, and Local Model Config. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Create NodeConfigBase and policy dataclasses <!-- id: 2 -->
  - [ ] Create `tinycua/config/node_config.py` with NodeMessagePolicy, NodeToolPolicy, NodeStreamPolicy, NodeRetryPolicy
  - [ ] Create NodeConfigBase with all policy fields and append-only customization
  - [ ] Add tool resolution logic to NodeToolPolicy
  - [ ] Add validation to NodeRetryPolicy (max_attempts >= 1)
- [ ] Create SystemPrompt and SystemPromptBuilder <!-- id: 3 -->
  - [ ] Create `tinycua/config/system_prompt.py` with SystemPrompt dataclass
  - [ ] Implement SystemPromptBuilder with add_static(), add_configurable_append(), add_dynamic_context()
  - [ ] Implement build() method that returns system-role message dict
- [ ] Create LocalModelConfig <!-- id: 4 -->
  - [ ] Create `tinycua/config/local_model.py` with LocalModelConfig dataclass
  - [ ] Add proper defaults and validation
- [ ] Create Todo and TodoItem <!-- id: 5 -->
  - [ ] Create `tinycua/models/todo.py` with TodoItem dataclass
  - [ ] Implement Todo class with append(), mark_done(), next_pending()
  - [ ] Add max_items enforcement with ValueError
- [ ] Update config package exports <!-- id: 6 -->
  - [ ] Update `tinycua/config/__init__.py` to re-export new config classes
  - [ ] Update `tinycua/models/__init__.py` to re-export Todo and TodoItem

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 7 -->
- [ ] Write unit tests for NodeConfigBase and policies <!-- id: 8 -->
  - [ ] Test NodeMessagePolicy defaults and custom values
  - [ ] Test NodeToolPolicy resolution order (allow/deny precedence)
  - [ ] Test NodeStreamPolicy defaults and custom values
  - [ ] Test NodeRetryPolicy defaults, custom values, exhaustion behaviors
  - [ ] Test NodeConfigBase construction with all policies
- [ ] Write unit tests for SystemPromptBuilder <!-- id: 9 -->
  - [ ] Test fragment ordering and priority
  - [ ] Test build() output format
  - [ ] Test empty fragments case
- [ ] Write unit tests for Todo <!-- id: 10 -->
  - [ ] Test append() and max_items limit
  - [ ] Test mark_done() with valid and invalid indices
  - [ ] Test next_pending() behavior
- [ ] Write unit tests for LocalModelConfig <!-- id: 11 -->
  - [ ] Test construction with required fields
  - [ ] Test default values
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 12 -->

## Verification Phase

- [ ] Verify all new modules import correctly <!-- id: 13 -->
- [ ] Verify dataclasses are immutable where intended <!-- id: 14 -->
- [ ] Verify LocalModelConfig can be used by nodes <!-- id: 15 -->
- [ ] Check for any breaking changes to existing code <!-- id: 16 -->

## Documentation Phase

- [ ] Update module docstrings <!-- id: 17 -->
- [ ] Update any relevant README files <!-- id: 18 -->
- [ ] Update changelog if applicable <!-- id: 19 -->

## Review and Merge

- [ ] Create pull request <!-- id: 20 -->
- [ ] Address review feedback <!-- id: 21 -->
- [ ] Merge to main branch <!-- id: 22 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-06*