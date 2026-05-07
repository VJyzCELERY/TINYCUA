# Agents Documentation

This project uses the `.agents/` directory for all AI agent-related configuration, commands, templates, and documentation.

---

## Quick Reference

### Available Commands

| Command | Description |
|---------|-------------|
| `/begin-workflow` | Full pipeline: plan → implement → review → cleanup |
| `/plan` | Creates implementation plan + task list from spec & design |
| `/implement` | Executes plan tasks using TDD (red → green → refactor) |
| `/review-loop` | Review cycle: report → validate → fix → fresh → cleanup |
| `/review-report` | Scoped code review of current branch changes |
| `/review-validate` | Full pipeline: clarify vague findings → verify statuses |
| `/review-clarify` | Improves review precision — rewrites vague findings |
| `/review-verify` | Checks each finding: addressed, invalid, or still OPEN |
| `/review-implement` | Applies fixes for review findings |
| `/review-post` | Posts review as a GitHub PR review with inline comments |
| `/review-update` | Follows up on PR review (resolve threads, flag remaining) |
| `/review-fetch` | Fetches unresolved PR comments into a review report |
| `/review-cleanup` | Archives resolved reviews |
| `/rebase` | Safely rebases current branch onto target (avoids commit duplication) |
| `/commit-cleanup` | Cleans up commit history — squashes fixups, removes duplicates |
| `/begin-worktree` | Creates a new worktree + branch for feature development |
| `/worktree-prune` | Removes inactive worktrees (checks PR status) |
| `/worktree-cleanup` | Cleans up local artifacts in the current worktree |
| `/setup-project` | Bootstraps `.agents/` structure in a new project |

### Project Structure

```
.agents/
├── scripts/           # Reusable scripts (Python, cross-platform)
│   ├── preflight-review.py
│   ├── preflight-pr.py
│   └── preflight-rebase.py
├── commands/          # Opencode commands
├── templates/         # Document templates
├── skills/            # Reusable skill references
│   ├── gh-pr-management/
│   ├── git-rebase/
│   ├── gh-review/
│   └── self-learning/
├── docs/
│   ├── agents/       # Agent rules and guidelines
│   └── project_rules/ # Project-specific rules
├── reviews/          # Archived reviews
├── AGENTS.md         # [REMOVED]
───
reviews/              # Active review outputs (root level)
```

### Key Files

- [.agents/docs/agents/agent_rules.md](.agents/docs/agents/agent_rules.md) — Core agent principles
- [.agents/docs/agents/workflow.md](.agents/docs/agents/workflow.md) — Development workflow
- [.agents/docs/agents/style.md](.agents/docs/agents/style.md) — Code formatting and naming
- [.agents/docs/agents/testing.md](.agents/docs/agents/testing.md) — Testing guidelines
- [.agents/docs/agents/debugging.md](.agents/docs/agents/debugging.md) — Debugging guide
- [.agents/docs/agents/security.md](.agents/docs/agents/security.md) — Security guidelines
- [.agents/docs/agents/code_generation.md](.agents/docs/agents/code_generation.md) — AI code generation rules
- [.agents/docs/agents/code_review.md](.agents/docs/agents/code_review.md) — Review standards
- [.agents/docs/project_rules/naming_conventions.md](.agents/docs/project_rules/naming_conventions.md) — Naming rules
- [.agents/docs/project_rules/project_structure.md](.agents/docs/project_rules/project_structure.md) — Project structure
- [.agents/docs/project_rules/cognitive_complexity.md](.agents/docs/project_rules/cognitive_complexity.md) — Complexity rules
- [.agents/docs/project_rules/commit_naming.md](.agents/docs/project_rules/commit_naming.md) — Commit naming rules
- [.agents/docs/project_rules/testing_guidelines.md](.agents/docs/project_rules/testing_guidelines.md) — Full testing rules
- [.agents/docs/project_rules/logging_guidelines.md](.agents/docs/project_rules/logging_guidelines.md) — Logging standards
- [.agents/docs/project_rules/coding_standards.md](.agents/docs/project_rules/coding_standards.md) — Code standards
- [.agents/docs/project_rules/deployment_and_versioning.md](.agents/docs/project_rules/deployment_and_versioning.md) — Deployment guidelines
- [.agents/docs/project_rules/pull_request.md](.agents/docs/project_rules/pull_request.md) — PR guidelines (spec/design sync)
- [.agents/docs/project_rules/worktree.md](.agents/docs/project_rules/worktree.md) — Worktree management rules
- [.agents/scripts/preflight-review.py](.agents/scripts/preflight-review.py) — Pre-flight: stale review, unstaged changes, scope
- [.agents/scripts/preflight-pr.py](.agents/scripts/preflight-pr.py) — Pre-flight: PR number detection
- [.agents/scripts/preflight-rebase.py](.agents/scripts/preflight-rebase.py) — Pre-flight: rebase safety check
- [.agents/scripts/gh.py](.agents/scripts/gh.py) — GitHub PR/review helper (fetch, post, update, resolve, create)

---

## Skills

Skills provide specialized instructions for common workflows. Read the relevant skill before performing the task.

| Skill | Description |
|-------|-------------|
| [gh-pr-management](.agents/skills/gh-pr-management/SKILL.md) | Creating, updating, and managing PRs with `gh` |
| [git-rebase](.agents/skills/git-rebase/SKILL.md) | Rebasing branches without dirtying commit history |
| [gh-review](.agents/skills/gh-review/SKILL.md) | Fetching, posting, and updating PR reviews with `gh` |
| [self-learning](.agents/skills/self-learning/SKILL.md) | Creating and updating project-specific skills based on recurring patterns |

---

## Critical: Always Ask When Uncertain

If any instruction is ambiguous, incomplete, or conflicting, use the question/ask tool (agent-harness agnostic) to clarify with the user. Do NOT guess or assume. If you are a subagent, report questions to your parent orchestrator instead.

---

## Critical: Always Read Rules and Check Templates First

**Before starting any task**, read the relevant rules from `.agents/docs/` first. This includes agent rules (`.agents/docs/agents/`) and project rules (`.agents/docs/project_rules/`). Each rule file defines conventions, constraints, and expectations that the agent must follow.

**Before generating any document**, always check `.agents/templates/` first. Use Read to load the relevant template and follow its structure.

**Before generating any document** (PR body, implementation plan, review report, task list, spec, or design), **always check `.agents/templates/` first**. Use Read to load the relevant template and follow its structure.

Available templates:
- `PR-body.md` — Pull request description
- `implementation-plan.md` — Implementation plan
- `task.md` — Task checklist
- `REVIEW-template.md` — Review report
- `spec.md` — Feature specification
- `design.md` — Design document

If no template exists for the document you need, create one following the conventions of existing templates.

---

## Critical: Use `uv run` for All Python/Pytest Commands

This project uses `uv` for Python environment management. **Never use bare `python` or `pytest`** — they may import from the wrong worktree.

Always `cd` into the subproject directory first, then use `uv run`:

```bash
# ✅ Correct
cd src/<subproject-dir> && uv run python script.py
cd src/<subproject-dir> && uv run pytest tests/

# ❌ Wrong
python script.py
pytest tests/
```

See [Workflow docs](.agents/docs/agents/workflow.md) for full details.

---

## Review File Convention

All review files live at `./reviews/REVIEW-{name}.md` (relative to repo root / workdir).
This is a consistent, predictable location so agents always know where to find reviews.

| Command | Output Location |
|---------|----------------|
| `/review-report <dir>` | Writes to `./reviews/REVIEW-{name}.md` |
| `/review-validate <file>` | Updates `./reviews/REVIEW-{name}.md` |
| `/review-implement <file>` | Updates statuses in `./reviews/REVIEW-{name}.md` |

---

## Quick Start

1. **Setup project**: Run `/setup-project <project-dir>` to initialize
2. **Create plan**: Run `/plan <dir>` with spec.md and design.md
3. **Implement**: Run `/implement <dir>` to execute the plan
4. **Review**: Run `/review-report <dir>` to review code
5. **Validate**: Run `/review-validate <review-file>` to validate findings
6. **Fix**: Run `/review-implement <review-file>` to implement fixes
