# Tasks: Project Agent Instructions Streamline

Implementation tasks for Project Agent Instructions Streamline. Check off items as completed.

## Implementation Phase

- [ ] Resolve spec/design policy decisions before implementation <!-- id: 0 -->
  - [ ] Decide whether `setup-project` may target paths outside the current repo behind explicit permission
  - [ ] Decide whether `.agents/docs/` remains reference-only or is removed after migration
  - [ ] Update `spec.md` and `design.md` so Phase 1 aligns with MUST requirements such as PR body template validation
- [ ] Add repo-boundary helper module <!-- id: 1 -->
  - [ ] Write failing tests for in-repo path acceptance, outside-path rejection, and `./tmp/` path creation
  - [ ] Implement `.agents/scripts/repo_guard.py`
  - [ ] Apply the helper to scripts that mutate caller-provided paths
- [ ] Remove implicit remote mutation from `gh.py create` <!-- id: 2 -->
  - [ ] Write failing tests or script-level checks for PR creation without automatic push or force-push
  - [ ] Remove automatic head/base branch pushes from PR creation
  - [ ] Add clear failure messaging when a remote branch is missing
- [ ] Add PR body template validation <!-- id: 3 -->
  - [ ] Write failing tests for missing sections and unfilled placeholders
  - [ ] Validate PR bodies against `.agents/templates/PR-body.md`
  - [ ] Update PR creation docs to describe the validation behavior
- [ ] Replace shell-string execution in tool wrappers <!-- id: 4 -->
  - [ ] Write smoke tests or checks for arguments containing spaces and shell metacharacters
  - [ ] Replace `execSync` shell strings with argv-based `execFileSync` or `spawnSync`
  - [ ] Preserve existing tool schemas and output behavior
- [ ] Consolidate top-level and dynamic instructions <!-- id: 5 -->
  - [ ] Update `AGENTS.md` with one normative hierarchy and one dynamic rule-loading reference
  - [ ] Update `.agents/rules/*.md` to reduce overlap and keep specialized rules focused
  - [ ] Migrate normative `.agents/docs/` content into `.agents/rules/`
  - [ ] Mark remaining `.agents/docs/` content reference-only or remove it after migration
- [ ] Align commands and skills <!-- id: 6 -->
  - [ ] Add required-context blocks to command files
  - [ ] Remove stale command names and stale `metadata.source` references
  - [ ] Replace raw `gh` examples with `gh.py` or documented fallback guidance
  - [ ] Reconcile review lifecycle behavior for local verification and remote updates
- [ ] Update templates and generated scaffolds <!-- id: 7 -->
  - [ ] Reconcile review template drift between `.agents/templates/REVIEW-template.md` and `preflight-review.py`
  - [ ] Update subproject templates to use `uv run` commands
  - [ ] Ensure generated subproject `AGENTS.md` inherits root critical rules
- [ ] Add agent consistency checker <!-- id: 8 -->
  - [ ] Write failing tests for missing command/skill/rule/template references
  - [ ] Write failing tests for raw `gh`, bare Python/Pytest, unsafe force-push guidance, and template drift
  - [ ] Implement `.agents/scripts/check-agents-consistency.py`
  - [ ] Document allowed fallback/exception markers

## Testing Phase

- [ ] Run repo-boundary helper tests <!-- id: 9 -->
- [ ] Run `gh.py` PR creation and PR body validation tests <!-- id: 10 -->
- [ ] Run tool-wrapper smoke tests for argv handling <!-- id: 11 -->
- [ ] Run consistency-check tests <!-- id: 12 -->
- [ ] Run `uv run python .agents/scripts/check-agents-consistency.py` after cleanup <!-- id: 13 -->
- [ ] Run `uv run python .agents/scripts/gh.py --help` and confirm documented examples are supported <!-- id: 14 -->

## Verification Phase

- [ ] Verify `AGENTS.md` exposes the canonical instruction hierarchy without requiring legacy docs <!-- id: 15 -->
- [ ] Verify command files declare preflight, skills, rules, templates, mutation scope, and confirmation requirements <!-- id: 16 -->
- [ ] Verify destructive workflows include dry-run/listing and explicit confirmation gates <!-- id: 17 -->
- [ ] Verify review lifecycle commands no longer contradict local-only vs remote-update behavior <!-- id: 18 -->
- [ ] Verify `.agents/docs/` is reference-only or migrated away <!-- id: 19 -->

## Documentation Phase

- [ ] Update `specs/project-agents-streamline/spec.md` if implementation decisions change scope or acceptance criteria <!-- id: 20 -->
- [ ] Update `specs/project-agents-streamline/design.md` if architecture or phase ordering changes <!-- id: 21 -->
- [ ] Update agent-facing docs and templates touched by the cleanup <!-- id: 22 -->
- [ ] Document how to run the new consistency check <!-- id: 23 -->

## Review and Merge

- [ ] Run a focused review on agent safety, remote mutation, and path-boundary behavior <!-- id: 24 -->
- [ ] Address review feedback with additional tests where needed <!-- id: 25 -->
- [ ] Confirm no `./reviews/` artifacts are staged before commit or PR creation <!-- id: 26 -->
- [ ] Create or update the pull request using `.agents/templates/PR-body.md` and `.agents/scripts/gh.py` <!-- id: 27 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-11*
