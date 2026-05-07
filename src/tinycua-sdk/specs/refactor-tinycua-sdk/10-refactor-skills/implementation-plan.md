# Implementation: Stage 10 — Refactor Skills Framework

Clean up the `skills/` package: remove the stateful `SkillBackend` hierarchy, add `Skill.load()` for string-based skill parsing, make `SkillRegistry` a non-singleton with no filesystem I/O, and remove or simplify filesystem-dependent loaders.

## Context

- **Spec Reference**: [spec.md](spec.md)
- **Design Reference**: [design.md](design.md)
- **Priority**: P0
- **Estimated Effort**: M

## Proposed Changes

### Skills Package Core

#### [DELETE] `tinycua_sdk/skills/backend.py`

- **[Description of change]**: Delete the entire file.
- **[Rationale]**: `SkillBackend`, `LocalSkillBackend`, `RemoteSkillBackend`, `HybridSkillBackend`, and `get_skill_backend()` are stateful storage abstractions. Storage is a consumer concern. The consumer decides where skills live (file, DB, S3, inline). This is parallel invention of the same pattern removed from `memory/` and `session/` in earlier stages.
- **[Breaking changes]**: Any code importing from `tinycua_sdk.skills.backend` will break. No tests in the current suite reference this file.

#### [MODIFY] `tinycua_sdk/skills/models.py`

- **[Description of change]**:
  1. Update `Skill` dataclass fields to match the new design:
     - Add: `source: str | None = None`
     - Add: `is_active: bool = True`
     - Add: `version: str = "1.0.0"`
     - Keep: `name`, `description`, `category`, `instructions`, `tools`, `dependencies`, `metadata`
     - Remove or deprecate: `path`, `created_at`, `modified_at` (these are filesystem concerns; `source` replaces `path`).
  2. Add `Skill.load(cls, text: str) -> Skill` classmethod that parses Markdown text with YAML frontmatter.
  3. Add `Skill.from_dict(cls, data: dict) -> Skill` classmethod.
  4. Update `Skill.to_dict()` to include new fields (`source`, `is_active`, `version`) and omit removed ones.
  5. Add a private `_parse_markdown_sections(body: str) -> dict[str, str]` helper to extract `## Description`, `## Instructions`, `## Tools` sections.
- **[Rationale]**: Skills must be loadable from strings (not just files). This makes the SDK I/O-free and allows skills to come from any source (DB, S3, inline).
- **[Breaking changes]**: `path`, `created_at`, `modified_at` removed. Any code relying on them must migrate to `source`.

#### [MODIFY] `tinycua_sdk/skills/registry.py`

- **[Description of change]**:
  1. Remove `SkillLoader` import and `self._loader = SkillLoader()`.
  2. Remove `cache` parameter from `__init__`.
  3. Remove `load_skills_from_directory()` method.
  4. Rename `register_skill(skill)` -> `register(skill)`.
  5. Rename `get_skill(name)` -> `get(name)`.
  6. Add `unregister(name: str) -> None` method.
  7. Keep `list_skills(category)`, `clear()`, and `count` property.
  8. Remove `get_categories()` (or keep if deemed useful — not referenced by new design).
  9. Ensure no singleton pattern is used (it already isn't, but verify).
- **[Rationale]**: Registry should be a simple in-memory dict wrapper. No I/O. Explicit instance per consumer.
- **[Breaking changes]**: Method renames and removal of `load_skills_from_directory()`.

#### [DELETE] `tinycua_sdk/skills/loader.py`

- **[Description of change]**: Delete the entire file.
- **[Rationale]**: `SkillLoader` performs filesystem scanning (`discover_skills`, `load_skill` from directories). All parsing logic moves into `Skill.load(text)`. Consumers that need to load from files read the file themselves and pass the string to `Skill.load()`.
- **[Breaking changes]**: `SkillLoader`, `SkillNotFoundError`, `SkillParseError` are removed from `tinycua_sdk.skills.loader`. `Skill.load()` should raise its own parsing exceptions (e.g., `ValueError` or a new `SkillLoadError`).

#### [MODIFY] `tinycua_sdk/skills/cache.py`

- **[Description of change]**:
  1. Remove `snapshot_dir` parameter and `save_snapshot()` / `load_snapshot()` methods.
  2. Remove `invalidate_if_stale()` and `check_modification` parameter (stale checking depends on filesystem `path`).
  3. Keep LRU in-memory cache (`get`, `put`, `invalidate`, `clear`, `_evict_lru`, `size`).
- **[Rationale]**: Cache should be ephemeral (in-memory only), not persistent. The design explicitly says "not persistent."
- **[Breaking changes]**: Snapshot persistence removed. Any code relying on `save_snapshot`/`load_snapshot` will break.

#### [MODIFY] `tinycua_sdk/skills/__init__.py`

- **[Description of change]**:
  1. Remove imports for deleted modules (`SkillLoader`, `SkillNotFoundError`, `SkillParseError`, `SkillCache`, `create_skills_list_tool`, `create_skill_view_tool`).
  2. Keep exports: `Skill`, `SkillRegistry`.
  3. Update `__all__` accordingly.
- **[Rationale]**: Clean public API. Only expose what remains.
- **[Breaking changes]**: Removed symbols from public API.

### Consumer Code Updates

#### [MODIFY] `tinycua_sdk/agent/loader.py`

- **[Description of change]**:
  1. Update `_load_skill_tools()` to read SKILL.md files directly (using `Path.read_text()`) and call `Skill.load(content)` instead of `skill_registry.load_skills_from_directory()`.
  2. Update `skill_registry.get_skill(name)` -> `skill_registry.get(name)`.
- **[Rationale]**: The agent loader is a consumer of the skills API within the SDK. It must adapt to the removal of `load_skills_from_directory()`.

#### [MODIFY] `tinycua/tinycua/tui/skills_manager.py`

- **[Description of change]**:
  1. Remove `SkillLoader` import.
  2. Replace `SkillLoader` usage with direct file reading and `Skill.load()`.
  3. Replace `_registry.load_skills_from_directory()` with explicit `Skill.load()` calls.
  4. Replace `_registry.get_skill(name)` -> `_registry.get(name)`.
- **[Rationale]**: TUI is a consumer of the SDK. It owns the skill lifecycle and filesystem I/O.

### Test Updates

#### [MODIFY] `tests/unit/test_skills.py`

- **[Description of change]**: This file already tests the new API (`Skill.load`, `SkillRegistry.register`, `SkillRegistry.get`). It should pass once `models.py` and `registry.py` are updated. No changes needed unless field mismatches occur (e.g., `path` -> `source`).

#### [MODIFY/DELETE] `tests/unit/test_skills_registry.py`

- **[Description of change]**:
  1. Update `register_skill` -> `register`.
  2. Update `get_skill` -> `get`.
  3. Remove `test_load_skills_from_directory`.
  4. Remove `test_get_categories` (or update if `get_categories` is kept).
  5. Add tests for `unregister()`.
  6. Add test confirming two `SkillRegistry` instances are independent.
- **[Rationale]**: Align tests with new registry API.

#### [MODIFY/DELETE] `tests/unit/test_skills_loader.py`

- **[Description of change]**: Replace with tests for `Skill.load()`:
  1. Test parsing YAML frontmatter.
  2. Test parsing without frontmatter.
  3. Test parsing sections (`## Description`, `## Instructions`).
  4. Test invalid YAML handling.
- **[Rationale]**: `SkillLoader` is deleted; its behavior moves into `Skill.load()`.

#### [MODIFY] `tests/unit/test_skills_cache.py`

- **[Description of change]**:
  1. Remove `test_save_and_load_snapshot`.
  2. Remove `test_invalidate_if_stale`.
  3. Keep LRU, put/get, invalidate, clear tests.
- **[Rationale]**: Cache is ephemeral only.

#### [MODIFY] `tests/unit/test_skills_tools.py`

- **[Description of change]**: Update `register_skill` -> `register`.
- **[Rationale]**: Align with renamed registry method.

#### [MODIFY] `tests/unit/test_skills_improver.py`

- **[Description of change]**: No changes needed if `Skill` dataclass changes are backward-compatible for fields it uses.
- **[Rationale]**: `SkillImprover` only references `skill.name`.

#### [MODIFY] `tests/integration/test_skills_integration.py`

- **[Description of change]**:
  1. Replace `registry.load_skills_from_directory(tmp_path)` with explicit file reading + `Skill.load()`.
  2. Update `create_skills_list_tool` / `create_skill_view_tool` imports if they move.
- **[Rationale]**: Align with new I/O-free registry.

#### [MODIFY] `tests/integration/test_skills_example.py`

- **[Description of change]**:
  1. Remove `SkillLoader` usage.
  2. Replace directory loading with `Skill.load()` from file content.
- **[Rationale]**: Align with new API.

#### [MODIFY] `tests/integration/test_agent_creation.py`

- **[Description of change]**: Replace `registry.load_skills_from_directory(tmp_path)` with explicit file reading + `Skill.load()` + `registry.register()`.
- **[Rationale]**: Align with new API.

### Examples and Documentation

#### [MODIFY] `examples/12_skills_example.py`

- **[Description of change]**: Remove `SkillLoader` usage. Replace directory loading with `Skill.load()` from file content.
- **[Rationale]**: Examples must reflect the new API.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `skills/backend.py` | Delete | Remove `SkillBackend` hierarchy |
| `skills/loader.py` | Delete | Remove filesystem-scanning `SkillLoader` |
| `skills/models.py` | Modify | Add `Skill.load()`, `from_dict()`, update fields |
| `skills/registry.py` | Modify | Non-singleton, no I/O, rename methods |
| `skills/cache.py` | Modify | Remove persistent snapshot, stale checking |
| `skills/__init__.py` | Modify | Clean exports |
| `agent/loader.py` | Modify | Use `Skill.load()` directly |
| `tinycua/tui/skills_manager.py` | Modify | Use `Skill.load()` directly |
| `tests/unit/test_skills_loader.py` | Modify | Test `Skill.load()` instead of `SkillLoader` |
| `tests/unit/test_skills_registry.py` | Modify | Align with new registry API |
| `tests/unit/test_skills_cache.py` | Modify | Remove persistent tests |
| `tests/integration/*` | Modify | Use `Skill.load()` + `register()` |

## Data Model Changes

```python
@dataclass
class Skill:
    name: str
    description: str = ""
    category: str = "general"
    instructions: str = ""
    tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    source: str | None = None      # NEW: replaces `path`
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True         # NEW
    version: str = "1.0.0"         # NEW
    # REMOVED: path, created_at, modified_at
```

## API Changes

### Removed Symbols

| Symbol | Location | Replacement |
|--------|----------|-------------|
| `SkillBackend` | `skills/backend.py` | Consumer-managed storage |
| `LocalSkillBackend` | `skills/backend.py` | Consumer-managed storage |
| `RemoteSkillBackend` | `skills/backend.py` | Consumer-managed storage |
| `HybridSkillBackend` | `skills/backend.py` | Consumer-managed storage |
| `get_skill_backend` | `skills/backend.py` | None |
| `SkillLoader` | `skills/loader.py` | `Skill.load(text)` |
| `SkillNotFoundError` | `skills/loader.py` | `ValueError` or custom exception in `Skill.load` |
| `SkillParseError` | `skills/loader.py` | `ValueError` or custom exception in `Skill.load` |
| `load_skills_from_directory` | `skills/registry.py` | Consumer reads files + `Skill.load()` |
| `register_skill` | `skills/registry.py` | `register` |
| `get_skill` | `skills/registry.py` | `get` |
| `save_snapshot` | `skills/cache.py` | None (ephemeral only) |
| `load_snapshot` | `skills/cache.py` | None (ephemeral only) |
| `invalidate_if_stale` | `skills/cache.py` | None |

### New Symbols

| Symbol | Location | Description |
|--------|----------|-------------|
| `Skill.load(text)` | `skills/models.py` | Parse skill from Markdown string |
| `Skill.from_dict(data)` | `skills/models.py` | Deserialize from dict |
| `SkillRegistry.unregister(name)` | `skills/registry.py` | Remove a skill from registry |

## Verification Plan

### Automated Tests

- [ ] Unit tests for `Skill.load()` (frontmatter, sections, edge cases)
- [ ] Unit tests for `Skill.to_dict()` / `Skill.from_dict()` round-trip
- [ ] Unit tests for `SkillRegistry` (register, get, unregister, list, filter, independence)
- [ ] Unit tests for `SkillCache` (LRU only, no persistence)
- [ ] Unit tests for `skills_tools` (skills_list, skill_view)
- [ ] Integration tests for skills end-to-end
- [ ] Integration tests for agent creation with skills
- [ ] Run full `pytest` suite

### Manual Verification

- [ ] Verify `examples/12_skills_example.py` runs correctly
- [ ] Verify `tinycua` TUI skills manager loads skills

## Rollout Strategy

1. **Phase 1** (Core): Update `models.py`, `registry.py`, delete `backend.py` and `loader.py`
2. **Phase 2** (Cache): Update `cache.py` to be ephemeral only
3. **Phase 3** (Consumers): Update `agent/loader.py`, `tui/skills_manager.py`, `skills_tools.py`
4. **Phase 4** (Tests): Update all test files
5. **Phase 5** (Cleanup): Update `__init__.py`, examples, run full test suite

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PyYAML | existing | YAML frontmatter parsing in `Skill.load()` |

### Internal Dependencies

- [x] Depends on Stage 01 (core types)
- [x] Depends on Stage 02 (tool framework)
- [x] Depends on Stage 08 (core registry removal)
- [ ] Blocks Stage 11 (Agent refactor depends on clean skill framework)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `agent/loader.py` breaks due to missing `load_skills_from_directory` | High | Rewrite agent loader to read files directly and call `Skill.load()` |
| `tinycua` TUI breaks due to missing `SkillLoader` | High | Rewrite TUI skills manager to read files directly |
| Tests fail due to field removals (`path`, `created_at`, `modified_at`) | Medium | Update tests to use `source` instead of `path`; remove timestamp assertions |
| `CallableTool` acceptance criteria cannot be met (file does not exist) | Low | Verify `CallableTool` is already gone from codebase; mark as no-op |

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
