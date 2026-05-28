# Implementation: Project Agent Instructions Streamline

Consolidate the repository's agent-instruction system so agents can identify the canonical rule hierarchy, avoid stale workflow guidance, and rely on lightweight scripts/tool wrappers for the highest-risk safety checks.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: L

## Proposed Changes

### Safety Enforcement

#### [MODIFY] `.agents/scripts/gh.py`

- **Remove implicit remote mutation**: Update PR creation so it never pushes, force-pushes, or pushes the base branch unless the user explicitly requested that behavior through a safe, documented flow.
- **Validate PR body structure**: Reject PR bodies with unfilled template placeholders or missing required sections from `.agents/templates/PR-body.md`.
- **Rationale**: The current instruction contract requires explicit user permission before remote mutation and template use for PR bodies.

#### [NEW] `.agents/scripts/repo_guard.py`

- **Add shared path guard helpers**: Provide `repo_root()`, `assert_inside_repo(path)`, and `tmp_path(name)` helpers for scripts that accept path arguments.
- **Rationale**: Boundary enforcement should be centralized and testable instead of repeated as prose-only guidance.

#### [MODIFY] `.agents/scripts/*.py`

- **Apply path guards**: Use `repo_guard.assert_inside_repo()` before reading, writing, creating, or deleting caller-provided paths.
- **Use project temp paths**: Replace system temp directory usage with `repo_guard.tmp_path()` where scripts create temporary files for repo work.
- **Rationale**: This enforces the project-root and `./tmp/` rules consistently.

#### [MODIFY] `.agents/tools/*.ts`

- **Replace shell-string execution**: Change tool wrappers from shell-interpolated command strings to argv-based execution via `execFileSync` or `spawnSync`.
- **Rationale**: User-controlled arguments must not be joined into shell strings, and paths/titles/branches containing spaces must work reliably.

### Instruction Consolidation

#### [MODIFY] `AGENTS.md`

- **Clarify normative hierarchy**: Define the precedence of `AGENTS.md`, `.agents/commands/`, `.agents/skills/`, `.agents/rules/`, `.agents/templates/`, and `.agents/docs/`.
- **Remove duplicated rule-loading tables**: Keep one dynamic-loading reference.
- **Update command index**: Add current commands, including `/review-refresh`, and remove stale command references.
- **Rationale**: The session-start contract must be concise and authoritative.

#### [MODIFY] `.agents/rules/*.md`

- **Reduce overlap**: Keep each rule file focused on its intent area and remove broad duplicated requirements from `001-agent-behavior.md` where they belong in specialized rule files.
- **Rationale**: Dynamic rule loading only works if rules are focused and non-conflicting.

#### [MODIFY] `.agents/docs/*`

- **Demote or migrate legacy docs**: Move actionable normative guidance into `.agents/rules/`, then mark remaining docs as reference-only or remove them after migration.
- **Rationale**: `.agents/docs/` must not compete with `.agents/rules/` as a normative rule source.

#### [MODIFY] `.agents/commands/*.md`

- **Fix stale references**: Remove references to nonexistent commands and stale metadata source paths.
- **Add command contracts**: Add required-context blocks declaring preflight, skills, rules, templates, mutation scope, and confirmation requirements.
- **Reconcile review lifecycle**: Make `review-verify` local-only and reserve remote replies/resolution for update/post commands.
- **Rationale**: Commands need machine-checkable expectations and one clear local-vs-remote mutation policy.

#### [MODIFY] `.agents/skills/*/SKILL.md`

- **Align skill guidance**: Replace permissive raw `gh` guidance with `gh.py` or documented fallback paths, fix stale command references, and point planning/implementation guidance to current rule files.
- **Rationale**: Skills should provide tactical guidance without contradicting `AGENTS.md`.

#### [MODIFY] `.agents/templates/*`

- **Reconcile template drift**: Make review templates canonical, update subproject templates to use `uv run`, and ensure generated subproject `AGENTS.md` inherits root critical rules.
- **Rationale**: Generated documents and project scaffolds must comply with current rules by default.

### Consistency Checks

#### [NEW] `.agents/scripts/check-agents-consistency.py`

- **Validate references**: Check command names, skill references, rule references, template references, and `metadata.source` paths against actual files.
- **Detect prohibited examples**: Report raw `gh`, bare `python`/`pytest`, unguarded `git push --force`, and stale archive path examples unless explicitly marked as allowed fallback or wrong-example text.
- **Detect template drift**: Check that embedded review/PR templates match canonical templates or are loaded from them.
- **Rationale**: Automated consistency checks prevent drift from recurring.

#### [NEW] Tests for `.agents/scripts/` and `.agents/tools/`

- **Cover safety helpers**: Test repo-boundary acceptance/rejection, safe temp paths, and PR body validation.
- **Cover wrapper execution**: Test wrapper argument construction with spaces and special characters.
- **Cover consistency parser**: Test stale command, missing source, raw `gh`, bare Python/Pytest, and force-push detection.
- **Rationale**: Each implementation task should be backed by a focused test-first cycle.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `AGENTS.md` | Modify | Becomes the concise top-level operational contract and command index |
| `.agents/rules/` | Modify | Becomes the canonical dynamic normative layer |
| `.agents/docs/` | Delete | Removed after migrating normative content into `.agents/rules/`; only `guides.md` retained |
| `.agents/commands/` | Modify | Gains required-context blocks and reconciled workflow behavior |
| `.agents/skills/` | Modify | Aligns tactical guidance with current rules and `gh.py` policy |
| `.agents/templates/` | Modify | Becomes the canonical source for generated document structures |
| `.agents/scripts/repo_guard.py` | New | Centralizes repo-boundary and temp-path enforcement |
| `.agents/scripts/check-agents-consistency.py` | New | Detects drift across commands, skills, rules, docs, scripts, tools, and templates |
| `.agents/tools/*.ts` | Modify | Uses argv-based execution instead of shell string interpolation |

## Data Model Changes

```text
CommandContract:
    preflight: str | None
    skills: list[str]
    rules: list[str]
    templates: list[str]
    mutates_files: bool
    mutates_git_history: bool
    mutates_remote: bool
    confirmation_required: str

ConsistencyFinding:
    severity: str
    path: str
    line: int | None
    message: str
    suggested_fix: str
```

## API Changes

### New Script Interfaces

| Command | Description |
|---------|-------------|
| `uv run python .agents/scripts/check-agents-consistency.py` | Validate agent command, skill, rule, template, and safety-reference consistency |

### New Helper Functions

| Function | Description |
|----------|-------------|
| `repo_guard.repo_root()` | Return the resolved project root |
| `repo_guard.assert_inside_repo(path)` | Resolve and validate that a path remains inside the project root |
| `repo_guard.tmp_path(name)` | Return a repo-local temporary path under `./tmp/` |

## Verification Plan

### Automated Tests

- [ ] Unit tests for `repo_guard` accepting in-repo paths and rejecting outside paths.
- [ ] Unit tests for PR body validation against `.agents/templates/PR-body.md`.
- [ ] Unit tests for consistency checks covering missing references, raw `gh`, bare Python/Pytest, force-push examples, and template drift.
- [ ] Unit or smoke tests for `.agents/tools/*.ts` wrapper argument handling with paths, branches, and titles containing spaces.
- [ ] Integration test that runs `uv run python .agents/scripts/check-agents-consistency.py` successfully after cleanup.
- [ ] Integration test that runs `uv run python .agents/scripts/gh.py --help` and verifies documented examples use supported commands.

### Manual Verification

- [ ] Read `AGENTS.md` and confirm the normative hierarchy is identifiable without reading legacy docs.
- [ ] Review one command file from each command family and confirm it declares required context and mutation policy.
- [ ] Confirm destructive workflows include dry-run/listing steps and explicit confirmation gates.
- [ ] Confirm `.agents/docs/` files are either reference-only or migrated away.

### Performance Considerations

- [ ] Keep consistency checks lightweight enough for local pre-merge verification.
- [ ] Avoid broad recursive parsing that makes routine command use noticeably slower.

## Rollout Strategy

1. **Phase 1 (Safety MVP)**: Remove implicit `gh.py create` pushes, fix tool wrapper shell execution, add path guards, update highest-risk docs, and reconcile review lifecycle behavior.
2. **Phase 2 (Consistency Automation)**: Add `check-agents-consistency.py`, PR body validation, template loading for review preflight, command contracts, and tests.
3. **Phase 3 (Documentation Consolidation)**: Migrate useful `.agents/docs/` content, mark remaining docs reference-only or remove them, and update templates/scaffolds.

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| None | N/A | Use standard Python and existing project tooling |

### Internal Dependencies

- [ ] Depends on maintainers deciding the setup-project boundary exception policy. **Decided**: Constrained to repo root.
- [ ] Depends on maintainers deciding whether `.agents/docs/` should be retained as reference-only or removed after migration. **Decided**: Remove, retain only `guides.md`.
- [ ] Blocks implementation cleanup for agent workflow safety issues identified in `project-agents-analysis.md`.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Removing auto-push behavior breaks existing PR creation habits | Medium | Fail with clear instructions and require explicit user-approved push flow |
| Consistency checks produce noisy false positives | Medium | Start with targeted checks, allow documented exception markers, and add regression tests for exceptions |
| Migrating `.agents/docs/` loses useful human guidance | Medium | Inventory docs before removal and migrate normative content into focused rule files |
| Command contracts add maintenance burden | Low | Keep the block compact and validate it automatically |
| Tool wrapper changes break harness integrations | Medium | Add smoke tests and preserve public tool schemas while changing execution internals |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-11*
