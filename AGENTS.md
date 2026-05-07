# Agents Documentation

This project uses the `.agents/` directory for all AI agent-related configuration, commands, templates, and documentation.

---

## Critical: Always Ask, Read, and Check First

1. **Ask when uncertain** — If any instruction is ambiguous or incomplete, use the question/ask tool to clarify. Do NOT guess. Subagents report questions to the parent orchestrator, not the user.
2. **Ask before committing** — Never commit or push without explicit user permission. Each batch needs a fresh ask unless the user grants unrestricted permission.
3. **Read rules first** — Before starting any task, read relevant rules from `.agents/docs/` (both `agents/` and `project_rules/`). Each file defines conventions and constraints.
3. **Use templates** — Before generating any document (PR body, spec, design, review, implementation plan, task list), check `.agents/templates/` first and follow the template structure.
4. **Run preflight scripts** — Commands reference preflight scripts in `.agents/scripts/`. Run them before executing the command. If a preflight fails, read the script manually to recover.
5. **Use `uv run` for Python** — Never bare `python` or `pytest`. Always `cd <subproject-dir> && uv run`.

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/begin-workflow` | Full pipeline: plan → implement → review → cleanup |
| `/begin-worktree` | Creates a new worktree + branch for feature development |
| `/plan` | Creates implementation plan + task list from spec & design |
| `/implement` | Executes plan tasks using TDD |
| `/review-loop` | Review cycle: report → validate → fix → fresh → cleanup |
| `/review-report` | Scoped code review of current branch changes |
| `/review-validate` | Full pipeline: clarify vague findings → verify statuses |
| `/review-clarify` | Improves review precision — rewrites vague findings |
| `/review-verify` | Checks each finding: addressed, invalid, or still OPEN |
| `/review-implement` | Applies fixes for review findings (does NOT update report) |
| `/review-post` | Posts review as a PR review with inline comments (+ tracks URLs) |
| `/review-update` | Follows up on PR review (resolve threads, flag remaining) |
| `/review-fetch` | Fetches unresolved PR comments into a review report |
| `/review-cleanup` | Archives resolved reviews |
| `/rebase` | Safely rebases current branch onto target |
| `/commit-cleanup` | Cleans up commit history — squashes fixups, removes duplicates |
| `/worktree-prune` | Removes inactive worktrees (checks PR status) |
| `/worktree-cleanup` | Cleans up local artifacts in the current worktree |
| `/setup-project` | Bootstraps `.agents/` structure in a new project |

---

## Directory Structure

```
.agents/
├── commands/          # Opencode command definitions
├── templates/         # Document templates (check before generating)
├── skills/            # Specialized workflow instructions
│   ├── gh-pr-management/
│   ├── git-rebase/
│   ├── gh-review/
│   └── self-learning/
├── scripts/           # Reusable Python scripts (cross-platform)
│   ├── gh.py          # All PR/review operations via REST API
│   ├── preflight-review.py
│   ├── preflight-pr.py
│   └── preflight-rebase.py
├── docs/
│   ├── agents/        # Agent rules and guidelines
│   ├── project_rules/ # Project-specific rules
│   └── guides.md      # Human-readable command guide
├── reviews/           # Archived reviews
───
reviews/              # Active review outputs (root level)
```

All commands reference preflight scripts. Run them first. If they fail, read the script's `<EOF_DESC>` section manually to understand what to fix.
