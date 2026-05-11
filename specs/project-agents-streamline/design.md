# Design Document: Project Agent Instructions Streamline

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-05-11 (policy decisions resolved)

---

## Overview

This design formalizes a cleanup of the repository's agent-instruction infrastructure. The key decision is to make `AGENTS.md` the short operational contract, `.agents/rules/` the canonical dynamic rule layer, commands/skills the workflow layer, templates the document-format layer, and `.agents/docs/` removed after migrating normative content (only `guides.md` is retained as a human reference). Enforcement should move from prose-only guidance into lightweight scripts and safe tool wrappers where practical.

---

## Architecture

### Component Overview

```text
Agent session
    |
    v
AGENTS.md  ----------------------+
    |                             |
    v                             v
.agents/commands/           .agents/rules/
    |                             |
    v                             v
.agents/skills/             .agents/templates/
    |                             |
    +------------+----------------+
                 v
          .agents/scripts/
                 |
                 v
       Consistency and safety checks
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `AGENTS.md` | Modified | Clarify normative hierarchy, remove repeated rule-loading content, add current command index |
| `.agents/commands/*.md` | Modified | Add required-context blocks, remove stale command names, reconcile review lifecycle behavior |
| `.agents/skills/*/SKILL.md` | Modified | Align skill names, sources, and raw `gh` guidance with current rules |
| `.agents/rules/*.md` | Modified | Make rules focused and non-overlapping |
| `.agents/docs/*` | Deleted | Remove after migrating normative content into `.agents/rules/`; only `guides.md` retained |
| `.agents/scripts/gh.py` | Modified | Remove automatic push/force-push from PR creation and add PR body validation |
| `.agents/scripts/*` | Modified / New | Add repo-boundary helpers and consistency checks |
| `.agents/tools/*.ts` | Modified | Replace shell string execution with argv-based execution |
| `.agents/templates/*` | Modified | Reconcile review template drift and update subproject template commands |

---

## Data Model

### New Entities _(if applicable)_

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

### Schema Changes _(if applicable)_

- No application data schema changes.
- Command files may gain a standardized Markdown section that is parseable by future checks.
- Scripts may gain shared helper modules under `.agents/scripts/`.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```text
repo_guard.assert_inside_repo(path) -> Path
    Resolve a path and raise a clear error if it escapes the repository root.

repo_guard.tmp_path(name) -> Path
    Return a path under ./tmp and ensure the directory exists.

check-agents-consistency.py
    Validate command/skill references, prohibited command examples, and template drift.
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Path escapes repo | Non-zero script exit with `[FAIL]` message | Must happen before file mutation |
| Raw `gh` in agent-facing docs | Consistency warning or failure | Allow only documented fallback sections |
| Missing command or skill source | Consistency failure | Prevent stale references from accumulating |
| PR body has placeholders | `gh.py create` rejects body | Use template validation before posting |
| Push requested without permission | Refuse and ask user | Never auto-force-push during PR creation |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Remove automatic push and force-push behavior from `gh.py create`.
- [ ] Replace shell-string execution in `.agents/tools/*.ts` with argv-based execution.
- [ ] Add repo-boundary helper and use it in scripts that accept file paths.
- [ ] Fix stale command/skill references identified in `project-agents-analysis.md`.
- [ ] Replace raw `gh` examples in agent-facing docs with `gh.py` or `gh.py cmd` examples.
- [ ] Reconcile review lifecycle policy for local verification vs remote updates.
- [ ] Standardize `./reviews/archives/` and destructive cleanup confirmation policy.
- [ ] Add PR body template validation to `gh.py create` (moved from Phase 2 — must align with spec FR-012).

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Add `check-agents-consistency.py` and run it in local verification.
- [ ] Make `preflight-review.py` consume `.agents/templates/REVIEW-template.md` rather than embedding a second template.
- [ ] Add command required-context blocks and parse them in consistency checks.
- [ ] Migrate or archive `.agents/docs/` content (retain only `guides.md`).

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Keep `AGENTS.md` as the top-level contract.
   - **Reason**: It is already loaded at session start and contains the most current critical rules.
   - **Alternatives Considered**: Move everything into `.agents/docs/`; rejected because it expands context and conflicts with dynamic rule loading.

2. **Decision**: Make `.agents/rules/` canonical for normative rules.
   - **Reason**: The current AGENTS workflow already expects dynamic loading by intent.
   - **Alternatives Considered**: Keep both `.agents/rules/` and `.agents/docs/project_rules/` normative; rejected because it is the source of current duplication.

3. **Decision**: Enforce high-risk rules in scripts, not only prose.
   - **Reason**: Agents can miss prose. Scripts can block path escape, unsafe PR body creation, and stale references reliably.
   - **Alternatives Considered**: Rely on manual review; rejected for safety-critical remote and filesystem operations.

4. **Decision**: Allow raw `gh` only behind `gh.py` or explicit fallback language.
   - **Reason**: The project wants one auditable GitHub path for agents while still retaining escape hatches for unsupported operations.
   - **Alternatives Considered**: Ban raw `gh` in internal scripts; may be too restrictive until `gh.py` fully wraps every operation.

5. **Decision**: Constrain `setup-project` to the repo root.
   - **Reason**: The root-boundary rule must be consistent — no special exceptions for cross-repo setup.
   - **Alternatives Considered**: Permission-gated exception; rejected because it creates an inconsistent boundary rule.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cleanup breaks existing slash-command workflows | Medium | High | Preserve names unless explicitly deprecated; add consistency checks |
| `.agents/docs/` contains useful guidance that is lost | Medium | Medium | Migrate useful normative content into `.agents/rules/` before deletion; retain `guides.md` |
| `gh.py` loses useful auto-push convenience | Medium | Low | Replace with explicit `--push` flow gated by user permission if needed |
| Consistency linter creates noisy false positives | Medium | Medium | Start with warnings, allow explicit exception markers |
| Tool wrapper changes break OpenCode plugin behavior | Low | Medium | Add smoke tests for each wrapper path |

---

## Open Questions _(optional)_

1. ~~Should `setup-project` remain allowed to operate outside the current repo as a special permission-gated exception?~~ **Decided**: Constrained to repo root.
2. Should `review-update` ever resolve OPEN threads when it is about to post a fresh replacement review?
3. ~~Should `.agents/docs/` be removed entirely after migration or kept as human-readable background documentation?~~ **Decided**: Remove after migration; only retain `guides.md`.

---

## References

- Spec: `./spec.md`
- Analysis: `./project-agents-analysis.md`
