# Feature Specification: Project Agent Instructions Streamline

**Status**: Draft
**Created**: 2026-05-11
**Last Updated**: 2026-05-11
**Subproject(s) Affected**: root agent infrastructure (`AGENTS.md`, `.agents/`)

---

## Quick Guidelines

- This spec describes what the agent-instruction cleanup must achieve, not the exact implementation patch.
- Requirements are limited to repository agent infrastructure and documentation.
- No application runtime behavior is in scope.

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a clear, enforceable, low-duplication agent instruction system so agents can follow project rules safely and consistently.
- **Gaps**: `AGENTS.md`, `.agents/rules/`, `.agents/docs/`, command files, skills, scripts, tools, and templates have drifted. Some instructions are stale, repeated, contradictory, or not enforced by scripts/tools.
- **Non-Goals**: This spec does not change TINYCUA product features, runtime behavior, application APIs, or model/agent implementation outside this repository's `.agents/` infrastructure.
- **Constraints**: Existing slash-command workflows should remain recognizable unless explicitly deprecated. Repository-boundary rules, `uv run` Python usage, template usage, and explicit permission before commits/pushes must remain preserved or strengthened.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

An agent starts work in the repository, reads `AGENTS.md`, loads only the relevant dynamic rule files, follows a command/skill workflow, and is blocked or warned before violating project safety rules such as using raw `gh`, writing outside the repo, using bare `python`, force-pushing without permission, or generating documents without templates.

### Acceptance Scenarios

1. **Given** an agent needs to perform PR work, **When** it reads the instructions, **Then** the only normal path uses `.agents/scripts/gh.py` and any fallback is explicit, gated, and documented.
2. **Given** an agent generates a review, PR body, spec, design, implementation plan, task list, or skill, **When** it follows the docs, **Then** it is directed to the canonical template and the scripts validate required structure where feasible.
3. **Given** a command or skill references another command, skill, rule, or template, **When** consistency checks run, **Then** stale names and missing files are reported.
4. **Given** a script accepts a file path, **When** the path points outside the project root, **Then** the script rejects it before reading, writing, or deleting.
5. **Given** a destructive operation is documented, **When** an agent follows the workflow, **Then** it must perform a dry-run/listing step and request explicit confirmation before deletion, history rewrite, remote push, or remote branch deletion.

### Edge Cases

- A command legitimately needs raw `gh` functionality not exposed by `gh.py`; the fallback must be explicit and safe.
- A setup workflow may need to operate on another project; this must either be prohibited by the root-boundary rule or documented as a special permission-gated exception.
- A review workflow may replace old GitHub review threads with a fresh review; OPEN thread resolution must be deliberate and documented rather than accidental.
- Legacy docs may contain useful content; migration must preserve useful rules while removing normative ambiguity.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The project MUST define a single normative hierarchy for agent instructions.
- **FR-002**: `.agents/rules/` MUST be the canonical dynamic rule location, or `.agents/docs/` MUST be explicitly marked as reference-only.
- **FR-003**: `AGENTS.md` MUST avoid repeating the same dynamic rule-loading table in multiple places.
- **FR-004**: Command and skill docs MUST use current slash-command names and MUST NOT reference nonexistent commands such as `review-cleanup`, `review-log`, `preflight.md`, or `self-learning` unless those commands are restored.
- **FR-005**: PR and GitHub instructions MUST route normal read/write operations through `.agents/scripts/gh.py`.
- **FR-006**: Any raw `gh` fallback MUST require checking `gh.py --help`, using `gh.py cmd` where possible, and documenting why fallback is necessary.
- **FR-007**: Scripts and tool wrappers MUST avoid unquoted shell-string interpolation for user-controlled arguments.
- **FR-008**: Scripts that read, write, delete, or create paths from arguments MUST enforce project-root containment.
- **FR-009**: PR creation MUST NOT push or force-push branches unless the user explicitly requested that remote mutation.
- **FR-010**: Any history rewrite or force-push guidance MUST require explicit user confirmation and prefer `--force-with-lease`.
- **FR-011**: Review lifecycle commands MUST have one clear local-vs-remote mutation policy.
- **FR-012**: Review, PR, spec, design, implementation-plan, task, and skill documents MUST use their canonical templates.
- **FR-013**: Generated subproject templates MUST comply with root rules, especially `uv run` usage.
- **FR-014**: Cleanup and worktree-prune workflows MUST require dry-run/listing plus explicit confirmation before destructive actions.
- **FR-015**: The project SHOULD include automated consistency checks for stale command names, missing `metadata.source` files, raw `gh` usage, bare Python/Pytest examples, unguarded force-push guidance, and template drift.

### Key Entities _(include if feature involves data)_

- **Instruction hierarchy**: The ordered precedence of `AGENTS.md`, commands, skills, rules, templates, and reference docs.
- **Command contract**: Machine-checkable metadata for each command, including required preflight, skills, rules, templates, mutation scope, and confirmation requirements.
- **Consistency check**: A script or workflow that validates docs and metadata against actual files.
- **Safety guard**: Shared helper logic for repo-boundary and safe temp-path enforcement.

---

## Success Criteria _(mandatory)_

- **Canonical source clarity**: A reviewer can identify the normative instruction hierarchy from `AGENTS.md` without reading legacy docs.
- **Reduced contradiction**: Known stale references and contradictory review/PR/worktree instructions are removed or explicitly reconciled.
- **Enforced safety**: Scripts/tools prevent the highest-risk violations rather than relying only on prose.
- **Validated references**: A consistency check can detect missing command/skill/source references.
- **Template compliance**: PR bodies and review reports are generated from or validated against canonical templates.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test repo-boundary path helper accepts in-repo paths and rejects paths outside the repo.
- Test any consistency-check parser detects missing command files, missing skill sources, raw `gh`, and bare Python/Pytest examples.
- Test PR body validation rejects unfilled placeholders and missing required sections.

### Integration Tests

- Run the consistency check against `.agents/` and verify it reports no stale references after cleanup.
- Exercise tool-wrapper command construction with paths, branches, and titles containing spaces.
- Run `uv run python .agents/scripts/gh.py --help` and verify documented command examples correspond to supported paths.

### Manual Tests _(if applicable)_

- Read `AGENTS.md` and verify it is concise enough to be a session-start contract.
- Review a sample command file and verify it declares required preflight, skills, rules, templates, and mutation policy.
- Confirm destructive workflows clearly show dry-run/listing and confirmation gates.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Analysis report | Done | Captured in `project-agents-analysis.md` |
| Formal spec | Done | This file |
| Design document | Done | See `design.md` |
| Implementation cleanup | TODO | Future work |
| Automated consistency checks | TODO | Future work |

---

## Open Questions _(optional)_

1. **Should `.agents/docs/` be deleted, archived, or kept as reference-only?**
   - **Owner**: project maintainers
   - **Target**: before implementation cleanup begins
   - **Status**: Discussion
   - **Proposed Answer**: Keep only after adding a clear reference-only banner, then migrate useful normative content into `.agents/rules/`.

2. **Should internal scripts be allowed to call raw `gh`?**
   - **Owner**: project maintainers
   - **Target**: before `gh.py` cleanup
   - **Status**: Discussion
   - **Proposed Answer**: Agents must use `gh.py`; internal scripts may wrap raw `gh` behind safe, tested helper functions.

---

## Review Checklist

- [x] No implementation details that require a specific patch shape
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
