# Implementation: Remove Modeling

Delete the entire `modeling/` package from the SDK. User profiling, personality analysis, and user modeling are consumer concerns, not SDK responsibilities.

## Context

- **Spec Reference**: [spec.md](spec.md)
- **Design Reference**: [design.md](design.md)
- **Priority**: P1
- **Estimated Effort**: S

## Proposed Changes

### Remove `modeling/` Package

#### [DELETE] `tinycua_sdk/modeling/__init__.py`

- **Description of change**: Delete the package init file.
- **Rationale**: Removes the `modeling` package entry point.

#### [DELETE] `tinycua_sdk/modeling/user.py`

- **Description of change**: Delete `UserModel`, `UserPreference`, and `UserGoal` classes.
- **Rationale**: User data models are owned by the consumer backend.

#### [DELETE] `tinycua_sdk/modeling/profiler.py`

- **Description of change**: Delete `CommunicationProfiler`.
- **Rationale**: Communication profiling is a consumer-specific concern.

#### [DELETE] `tinycua_sdk/modeling/personality.py`

- **Description of change**: Delete `Personality` class.
- **Rationale**: Personality analysis is stateful and privacy-sensitive; consumer should handle it.

### Remove Modeling References

#### [MODIFY] Files referencing `tinycua_sdk.modeling`

- **Description of change**: Search for any imports or references to `tinycua_sdk.modeling` across the codebase and remove them.
- **Rationale**: Prevents broken imports after package deletion.
- **Breaking changes**: Any consumer code importing from `tinycua_sdk.modeling` will break. Consumers should define their own user profile schema and inject preferences via `Agent.instructions` or `Agent.system_prompt`.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `modeling/` package | Remove | Entire package deleted |
| `Agent` (if references exist) | Modify | Remove `modeling` imports/parameters |

## Data Model Changes

No new types or interfaces. The following types are removed:
- `UserModel`
- `UserPreference`
- `UserGoal`
- `CommunicationProfiler`
- `Personality`

## API Changes

No new endpoints. No modified endpoints.

## Verification Plan

### Automated Tests

- [ ] Run `pytest` and confirm all remaining tests pass
- [ ] Confirm no test files reference `tinycua_sdk.modeling`

### Manual Verification

- [ ] Run `rg "from tinycua_sdk.modeling" src/` — expect 0 matches
- [ ] Run `rg "import tinycua_sdk.modeling" src/` — expect 0 matches
- [ ] Run `rg "UserModel|Personality|CommunicationProfiler" src/tinycua_sdk/` — expect 0 matches

## Rollout Strategy

1. **Phase 1** (Deletion): Delete all `modeling/` files.
2. **Phase 2** (Cleanup): Remove any remaining references in other modules/tests.
3. **Phase 3** (Verification): Run test suite to confirm nothing is broken.

## Dependencies

### Internal Dependencies

- [ ] Depends on Stage 01, Stage 02
- [ ] Blocks: None (can proceed in parallel with Stages 03–05, 07)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hidden references in tests or docs | Medium | Use `rg` to grep entire codebase before deletion |
| Consumers relying on `modeling` types | High | Document migration path in design.md; types are removed in major/minor bump |

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
