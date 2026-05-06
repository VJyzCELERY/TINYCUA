# Implementation: Stage 2.5 — Clear Backward Compatibility

Remove all backward-compatibility artifacts (`_OBSOLETE_PARAMS`, migration framing, obsolete test targets) from the project to reinforce that this is a clean-slate reset, not a v2 migration.

## Context

- **Spec Reference**: `specs/refactor-tinycua-sdk-v2/specs/stage-2.5-clear-backward-compat/spec.md`
- **Design Reference**: `specs/refactor-tinycua-sdk-v2/specs/stage-2.5-clear-backward-compat/design.md`
- **Priority**: P1
- **Estimated Effort**: S

## Proposed Changes

### Agent Constructor (Runtime)

#### [MODIFY] `stage-02-agent-config/design.md`

- **[Remove `_OBSOLETE_PARAMS` frozenset]**: Delete lines 88–94 in the design document that define the frozenset of obsolete v1 parameter names.
- **[Remove `**kwargs` validation loop]**: Delete the kwarg-checking logic from `Agent.__init__()` signature and body.
- **[Remove obsolete-params row from Error Handling table]**: Delete the "Obsolete parameter passed" scenario row.
- **[Rationale]**: The Python runtime natively raises `TypeError` for unexpected keyword arguments. Custom validation is unnecessary and sends a misleading "migration" signal.

### Stage 2 Spec & Targets

#### [MODIFY] `stage-02-agent-config/spec.md`

- **[Remove obsolete-param requirement subsection]**: Delete the "Obsolete parameter rejection" subsection.
- **[Remove obsolete-param success criterion]**: Delete the corresponding criterion line.
- **[Rationale]**: The spec should not list requirements that no longer exist.

#### [MODIFY] `stage-02-agent-config/targets.md`

- **[Delete Target 2.5]**: Remove the "Obsolete Parameters Rejected" target entry.
- **[Renumber targets 2.6→2.5, 2.7→2.6]**: Shift subsequent target numbers.
- **[Rationale]**: No test target should verify removed functionality.

#### [DELETE] `stage-02-agent-config/targets/05_obsolete_params_rejected.py`

- **[Rationale]**: Target file for obsolete-params rejection is no longer needed.

#### [DELETE] `stage-02-agent-config/targets/05_obsolete_params_rejected_expected-output.txt`

- **[Rationale]**: Expected output file for the deleted target.

### Stage 0 Cleanup References

#### [MODIFY] `stage-00-cleanup/spec.md`, `stage-00-cleanup/design.md`, `stage-00-cleanup/implementation-plan.md`, `stage-00-cleanup/task.md`

- **[Remove `_OBSOLETE_PARAMS` mentions]**: Delete all references to `_OBSOLETE_PARAMS` from these files.
- **[Rationale]**: Stage 0 no longer needs to list `_OBSOLETE_PARAMS` as a deletion target because Stage 2 no longer creates it.

### Stage 3-9 Documentation

#### [MODIFY] `stage-03-execution-core/description.md`

- **[Add Stage 2.5 dependency]**: Add Stage 2.5 to the dependencies list.
- **[Rationale]**: Stage 3 builds on Stage 2, and Stage 2.5 now sits between them.

#### [MODIFY] `stage-09-final-integration/design.md`

- **[Remove obsolete-param test strategy row]**: Delete "obsolete param rejection" from the test strategy table (originally line 144).
- **[Rationale]**: There is no obsolete-param behavior to test.

### ROADMAP

#### [MODIFY] `docs/ROADMAP.md`

- **[Add Stage 2.5 entry]**: Insert Stage 2.5 between Stage 2 and Stage 3.
- **[Remove `_OBSOLETE_PARAMS` from Stage 0 deletions]**: Clean up Stage 0's key deletions list.
- **[Clarify project-reset framing]**: Update title and/or principle 2 to state this is a project reset, not a v2 migration.
- **[Rationale]**: The ROADMAP must reflect the actual stage sequence and project framing.

### Verification Target

#### [NEW] `targets/01_no_obsolete_params.py`

- **[Description]**: Create a target that verifies passing any obsolete parameter name (from the former `_OBSOLETE_PARAMS` set) to `Agent()` raises a normal `TypeError` (not a custom message).
- **[Dependencies]**: Stage 2 Agent implementation must be complete.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `agent/agent.py` (per design.md) | Modify | Remove `_OBSOLETE_PARAMS` frozenset and `**kwargs` validation loop |
| `stage-02-agent-config/design.md` | Modify | Remove obsolete-params design artifacts and error scenarios |
| `stage-02-agent-config/spec.md` | Modify | Remove obsolete-params requirements |
| `stage-02-agent-config/targets.md` | Modify | Remove Target 2.5, renumber subsequent targets |
| `stage-02-agent-config/targets/05_*.*` | Delete | Delete target and expected-output files |
| `stage-00-cleanup/*.md` | Modify | Remove `_OBSOLETE_PARAMS` references |
| `stage-03-execution-core/description.md` | Modify | Add Stage 2.5 dependency |
| `stage-09-final-integration/design.md` | Modify | Remove obsolete-params test strategy row |
| `docs/ROADMAP.md` | Modify | Add Stage 2.5, clean up Stage 0, reframe project |
| `targets/01_no_obsolete_params.py` | New | Verification target for clean constructor |

## Verification Plan

### Automated Checks

- [ ] `grep -r "_OBSOLETE_PARAMS" specs/refactor-tinycua-sdk-v2/` returns no matches (PASS = no output)
- [ ] `ls stage-02-agent-config/targets/05_*` reports "No such file or directory" (PASS)
- [ ] Run `uv run python targets/01_no_obsolete_params.py` outputs `PASS`

### Manual Verification

- [ ] Review all stage 3–9 spec/design/description files for any remaining "v2 migration" or "backward-compat" language.
- [ ] Verify ROADMAP.md renders correctly with Stage 2.5 between Stage 2 and Stage 3.

### Performance Considerations

- No performance impact — this is a net removal of validation code.

## Dependencies

### Internal Dependencies

- [ ] Depends on Stage 2 (Agent Configuration & Creation) being complete.
- [ ] Blocks correct framing for Stages 3–9.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missed references to `_OBSOLETE_PARAMS` in far-flung docs | Low | Run broad `grep` across entire `specs/` directory |
| Renumbering targets 2.6/2.7 could cause downstream confusion if other stages reference by number | Low | Search for any cross-references to target numbers 2.6 or 2.7 before renumbering |
| Merging this branch with active work on Stages 3+ could cause merge conflicts in ROADMAP | Medium | Coordinate merge timing; Stage 2.5 should be merged before substantial Stage 3+ changes |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-06*
