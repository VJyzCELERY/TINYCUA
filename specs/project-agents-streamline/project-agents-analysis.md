# Project Agents Analysis

Generated: 2026-05-11

Scope reviewed:

- `AGENTS.md`
- `.agents/commands/`
- `.agents/skills/`
- `.agents/rules/`
- `.agents/scripts/`
- `.agents/tools/`
- `.agents/templates/`
- `.agents/docs/`

## Executive Summary

The agent system is useful and fairly complete, but it has drifted into three overlapping instruction layers:

- `AGENTS.md` now defines the current canonical workflow and critical rules.
- `.agents/rules/` defines newer dynamic, intent-loaded rules.
- `.agents/docs/` still contains older broad rules and is still referenced by commands and skills.

That drift creates stale references, duplicated guidance, and enforcement gaps. The biggest risks are operational safety issues: raw `gh` usage despite a `gh.py` mandate, scripts that can push or force-push without explicit user permission, tool wrappers that interpolate user input into shell strings, and path arguments that are not guarded against leaving the repo.

Recommended direction:

- Make `AGENTS.md` the top-level contract and `.agents/rules/` the only normative rule set.
- Demote `.agents/docs/` to reference material or migrate/delete it.
- Add a small shared enforcement layer for repo-boundary paths, safe temp paths, PR body validation, and GitHub operations.
- Add lightweight lint/smoke checks for stale slash-command names, bare `python`/`pytest`, raw `gh`, force-push text, and tool/script schema mismatches.

## Priority Findings

### 1. `gh.py create` can push and force-push without explicit permission

Severity: Critical

Evidence:

- `AGENTS.md:15` requires explicit user permission before committing or pushing.
- `.agents/scripts/gh.py:1125-1133` pushes missing branches with `git push --force origin <branch>`.
- `.agents/scripts/gh.py:1156-1159` pushes both the PR head and base branch before creating a PR.

Recommended fix:

- Remove automatic pushes from `gh.py create`.
- If auto-push is desired, require explicit flags and never push the base branch.
- Use `--force-with-lease`, never `--force`, and reject `main`/`master` force pushes.

### 2. Mandatory `gh.py` rule is contradicted by raw `gh` usage

Severity: High

Evidence:

- `AGENTS.md:34` says all PR operations, read and write, must go through `.agents/scripts/gh.py`.
- Raw `gh` commands appear in review command docs.
- Several scripts call raw `gh` internally.
- `.agents/skills/gh/SKILL.md` explicitly allows `gh pr diff` and unknown raw commands.

Recommended fix:

- Replace raw examples with `uv run python .agents/scripts/gh.py cmd ...` where possible.
- Clarify whether internal scripts may wrap raw `gh`.
- Remove permissive raw `gh` guidance from agent-facing docs.

### 3. Tool wrappers are shell-injection prone and break on spaces

Severity: High

Evidence:

- `.agents/tools/preflight.ts` and `.agents/tools/gh.ts` build shell strings with `args.join(" ")`.

Recommended fix:

- Replace shell-string `execSync` with `execFileSync` or `spawnSync` and argv arrays.

### 4. Project-boundary rule is mostly advisory, not enforced by scripts

Severity: High

Evidence:

- `AGENTS.md` forbids operating outside the project root.
- Scripts accept caller-provided paths for reads, writes, and deletes without a shared containment guard.

Recommended fix:

- Add `repo_guard.py` with `repo_root()`, `assert_inside_repo(path)`, and `tmp_path(name)`.
- Use it before all file mutation from script arguments.

### 5. `.agents/docs/` is legacy but still competes with `.agents/rules/`

Severity: High

Evidence:

- `AGENTS.md` defines dynamic rule loading from `.agents/rules/`.
- Commands and skills still point to `.agents/docs/` and `.agents/docs/project_rules/`.

Recommended fix:

- Declare a normative hierarchy in `AGENTS.md`.
- Migrate actionable legacy docs into `.agents/rules/` or mark `.agents/docs/` reference-only.

### 6. Implementation-start requirements are under-enforced by commands

Severity: High

Evidence:

- `AGENTS.md` requires feature/subproject clarification, spec, design, tests first, and relevant rules before implementation.
- `/plan`, `/implement`, and `/begin-workflow` do not consistently load or enforce those requirements.

Recommended fix:

- Add a standard required-context block to each command.
- Require planning, testing, and coding rules at the command level where relevant.

### 7. Review command lifecycle has contradictory remote-update behavior

Severity: High

Evidence:

- `review-verify` says it is local-only but later says to post PR replies.
- `review-update` resolves still-OPEN inline threads.
- `_common-review-steps.md` says OPEN threads should not be resolved.

Recommended fix:

- Define one policy: `review-verify` is local-only; `review-update` handles remote replies/resolution; OPEN findings are not resolved unless a fresh replacement-review exception is explicit.

### 8. Stale slash-command names and missing quick-reference entries

Severity: Medium

Evidence:

- Stale references include `review-cleanup`, `review-log`, `.agents/commands/preflight.md`, and `.agents/commands/self-learning.md`.
- `/review-refresh` exists but is missing from `AGENTS.md` quick reference.

Recommended fix:

- Add a consistency check for every `metadata.source` path and slash-command mention.

### 9. Force-push guidance is too permissive

Severity: Medium

Evidence:

- Git skills and commands recommend or require `git push --force` after rebase/cleanup.

Recommended fix:

- Replace with explicit confirmation-gated `git push --force-with-lease`; forbid force-pushing `main`/`master`.

### 10. Setup-project violates current boundary and temp-file rules

Severity: Medium

Evidence:

- `setup-project` accepts arbitrary targets and uses `mktemp -d` despite root-boundary and `./tmp/` rules.

Recommended fix:

- Constrain targets inside the current root or document a special permission-gated exception.
- Use `./tmp/setup-project-*`.

### 11. Review templates are duplicated and inconsistent

Severity: Medium

Evidence:

- `.agents/templates/REVIEW-template.md` differs from the embedded template in `preflight-review.py`.

Recommended fix:

- Make `preflight-review.py` load the canonical template and fill placeholders.

### 12. Tool schemas are stale relative to scripts

Severity: Medium

Evidence:

- `preflight_pr` tool passes positional args, while `preflight-pr.py` expects `--pr` or `--branch`.
- `gh` tool exposes unsupported resources and command shapes.

Recommended fix:

- Add smoke tests or generate schemas from argparse definitions.

### 13. Broad rules in `001-agent-behavior.md` duplicate and over-constrain dedicated rules

Severity: Medium

Evidence:

- `001-agent-behavior.md` duplicates code, test, commit, docs, worktree, and validation rules.
- Some mandates are too broad, such as all functions/classes needing docstrings and all generated code requiring unit plus integration tests.

Recommended fix:

- Keep `001-agent-behavior.md` to behavior/orchestration only.
- Move concrete requirements to focused rule files.

### 14. Archive path and cleanup behavior are inconsistent

Severity: Medium

Evidence:

- Review archive uses `./reviews/archives/`; cleanup references `./reviews/archived/`.
- Human guide says cleanup deletes `./dev/`.

Recommended fix:

- Standardize on `./reviews/archives/`.
- Do not delete `./dev/` by default.
- Require dry-run and explicit confirmation before destructive cleanup.

### 15. Subproject template contradicts Python/uv rules

Severity: Medium

Evidence:

- Subproject Makefile uses `python3`, bare `ruff`, bare `pytest`, and bare `radon`.

Recommended fix:

- Update template commands to use `uv run`.
- Make subproject `AGENTS.md` inherit root critical rules explicitly.

### 16. Bare `python` examples still exist

Severity: Low

Recommended fix:

- Replace `python -c` and `python -m json.tool` examples with `uv run python ...`.

### 17. Human guide is stale compared with `AGENTS.md`

Severity: Low

Recommended fix:

- Synchronize `.agents/docs/guides.md` with `AGENTS.md` or replace it with a generated index.

## Redundant Or Repeated Information To Streamline

- Dynamic rule-loading tables are repeated in `AGENTS.md`; keep one table.
- Preflight instructions are repeated across AGENTS and review commands; centralize review preflight in `_common-preflight.md`.
- Review status definitions appear in rules, common modules, and commands; define one canonical status policy.
- Code-generation standards appear in `001`, `002`, and legacy docs; keep actionable content in focused rules.
- Command and skill lists appear in AGENTS, guides, and files; generate or validate them.

## Rules That Need Stronger Enforcement

- Enforce boundary and temp-path rules in code with shared helpers.
- Enforce PR body template use in `gh.py create`.
- Enforce command/skill consistency with a script.
- Enforce no raw GitHub operations in agent-facing docs unless explicitly marked as fallback.
- Enforce no bare Python/Pytest in agent docs except explicitly marked wrong examples.
- Enforce safe destructive operations through list/dry-run, ask, execute.

## Proposed Streamlined Structure

Canonical hierarchy:

1. `AGENTS.md`: top-level operational contract and command index.
2. `.agents/commands/*.md`: exact slash-command workflows.
3. `.agents/skills/*/SKILL.md`: tactical workflow guidance.
4. `.agents/rules/*.md`: normative intent-loaded rules.
5. `.agents/templates/*`: required output formats.
6. `.agents/docs/*`: optional reference only, or removed after migration.

Each command should include a machine-checkable block:

```markdown
## Required Context

- Preflight: <script or none>
- Skills: <skill names>
- Rules: <rule files>
- Templates: <template files or none>
- Mutates files: yes/no
- Mutates git history: yes/no
- Mutates remote: yes/no
- Requires user confirmation: <conditions>
```

## Suggested Cleanup Plan

### Phase 1: Safety fixes

- Remove auto-push and force-push from `gh.py create`.
- Replace shell-string `execSync` in `.agents/tools/*.ts` with argv execution.
- Add repo-boundary helpers and guard script path arguments.
- Update force-push docs to require explicit confirmation and `--force-with-lease`.

### Phase 2: Consistency fixes

- Replace raw `gh` examples with `gh.py cmd` examples.
- Fix `preflight_pr` tool args to use `--pr`.
- Fix stale command and skill references.
- Add `/review-refresh` to `AGENTS.md` or remove/deprecate the command.
- Standardize archive path as `./reviews/archives/`.

### Phase 3: Documentation consolidation

- Move useful `.agents/docs/` guidance into `.agents/rules/`.
- Mark remaining `.agents/docs/` files as reference-only or delete them.
- De-duplicate `AGENTS.md` dynamic rule-loading sections.
- Update `setup-project` to template the canonical structure.

### Phase 4: Automated checks

- Add `check-agents-consistency.py`.
- Add checks for stale slash-command names, missing `metadata.source`, raw `gh`, bare Python/Pytest, unguarded force-push examples, and template drift.
- Add smoke tests for `.agents/tools/*` against script argparse behavior.
