# Stage 2.5: Clear Backward Compatibility — Specification

**Status**: Draft
**Created**: 2026-05-06
**Last Updated**: 2026-05-06
**Subproject(s) Affected**: tinycua-sdk

## Objective
Remove all backward-compatibility artifacts from the project. The tinycua-sdk is a clean-slate reset, not a migration from v1. No code, test, or document should imply that obsolete v1 parameters are expected or need special handling.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

## Requirements

### R-2.5.1: No _OBSOLETE_PARAMS in Agent Constructor
The `Agent.__init__()` method MUST NOT contain `_OBSOLETE_PARAMS` or any similar backward-compatibility validation. Unknown keyword arguments are handled by Python's native `TypeError`.

### R-2.5.2: No Obsolete-Parameter Test Targets
There MUST NOT be any test target that verifies rejection of obsolete parameters. Delete `targets/05_obsolete_params_rejected.py` from Stage 2.

### R-2.5.3: No Backward-Compatibility Framing in Stages 3–9
All stage descriptions, specs, and designs for stages 3–9 MUST NOT:
- Reference "migration from v1".
- Reference "_OBSOLETE_PARAMS".
- Frame the API as "v2" in a way that implies a prior version existed.
- Include test strategies for obsolete-parameter rejection.

### R-2.5.4: ROADMAP Updated
The ROADMAP MUST:
- Add Stage 2.5 between Stage 2 and Stage 3.
- Remove "_OBSOLETE_PARAMS" from Stage 0's key deletions list.
- Clarify in the title/description that this is a project reset, not a v2 migration.

## Success Criteria

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] Constructor Accepts Only Current Params - targets/01_no_obsolete_params.py - PASS - `print('PASS')`
  Description: Agent constructor does not recognize obsolete params (they cause normal TypeError, not a custom message).

- [ ] No _OBSOLETE_PARAMS in Codebase - N/A - no matches - `grep -r "_OBSOLETE_PARAMS" src/`
  Description: No reference to `_OBSOLETE_PARAMS` remains in spec files or implementation.

- [ ] Target 2.5 Deleted - N/A - file not found - `ls specs/stage-02-agent-config/targets/05_*`
  Description: The obsolete-params rejection test file is removed.

## Target File
- `targets/01_no_obsolete_params.py`
