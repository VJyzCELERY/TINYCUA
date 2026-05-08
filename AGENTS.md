# Agents Documentation

This project uses the `.agents/` directory for all AI agent-related configuration, commands, templates, and documentation.

**Baseline harness is opencode, but all instructions are harness-agnostic.** If your harness does not support a specific mechanism (skill loading, tool detection, etc.), fall back to reading files directly and executing commands via bash.

---

## Critical: Always Ask, Read, and Check First

0. **Run start preflight** — At the start of every session, run `uv run python .agents/scripts/preflight-start.py`. This detects your OS and establishes the project boundary so you never operate outside it.
1. **Never leave the project root** — Your attached root directory is your entire world. Do NOT read, write, or execute anything outside it. If you need temporary files, use `./tmp/` (already gitignored) and clean up after yourself. Never use system `/tmp/`.
2. **Parent agents: instruct subagents to read AGENTS.md** — Whenever you delegate to a subagent, explicitly tell it to read this AGENTS.md file first. Subagents start with zero context and won't know these rules unless told.
3. **Ask when uncertain** — If any instruction is ambiguous or incomplete, use the question/ask tool to clarify (priority). Only write questions inline if your harness has no such tool. Do NOT guess. Subagents report questions to the parent orchestrator, not the user.
4. **Ask before committing** — Never commit or push without explicit user permission. Each batch needs a fresh ask unless the user grants unrestricted permission.
5. **Read rules first** — Before starting any task, read relevant rules from `.agents/docs/` (both `agents/` and `project_rules/`). Each file defines conventions and constraints.
6. **Use templates** — Before generating any document (PR body, spec, design, review, implementation plan, task list), check `.agents/templates/` first and follow the template structure.
7. **Run preflight scripts** — Commands reference preflight scripts in `.agents/scripts/`. Run them before executing the command. If a preflight fails, read the script manually to recover.
8. **Use `uv run` for Python** — Never bare `python` or `pytest`. Always `cd <subproject-dir> && uv run`.
9. **Use gh.py for PR operations** — All PR/review write operations must go through `.agents/scripts/gh.py`. Never use raw `gh pr edit`, `gh pr review`, or similar direct commands for PR writes. Check `uv run python .agents/scripts/gh.py --help` for available subcommands.

---

## How to Explore `.agents/`

Everything you need is in `.agents/`. Explore it like a filesystem — only read what you need:

```
.agents/
├── commands/        # Slash command definitions (load on demand)
├── skills/          # How-to guides for each command/tool (load on demand)
├── tools/           # Custom tool definitions (opencode format, invoke scripts/)
├── scripts/         # Python scripts (gh.py, preflight-*.py)
├── templates/       # Document templates (check before generating)
├── docs/
│   ├── agents/      # Agent behavior rules, workflow, style, testing
│   └── project_rules/ # Naming, coding standards, commit style, testing
└── reviews/         # Archived review reports
```

### When to load what

| Trigger | Load this |
|---------|-----------|
| Slash command received | `.agents/commands/<name>.md` + matching skill from `.agents/skills/<name>/` |
| Before any script | Run preflight first: `uv run python .agents/scripts/preflight-<name>.py` |
| Need PR/review help | Load skill: `gh-pr-management` or read `.agents/skills/gh-pr-management/SKILL.md` |
| Need git help | Load skill: `git-rebase` or read `.agents/skills/git-rebase/SKILL.md` |
| Need to create a skill | Load skill: `self-learning` and use `.agents/templates/skill.md` |

List available skills: `ls .agents/skills/` — each is a directory with a `SKILL.md` inside.

List available tools: `ls .agents/tools/` or run `uv run python .agents/scripts/gh.py --help`.

Read docs: `ls .agents/docs/agents/` and `ls .agents/docs/project_rules/`.

### Skill loading (harness-dependent)

```
# Native mechanism:
#   opencode: skill({ name: "<name>" })
#   generic:  Read .agents/skills/<name>/SKILL.md
```

If unsure, always fall back to reading the file directly.

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

All commands reference preflight scripts in `.agents/scripts/`. Run the preflight first. If it fails, read the script's `<EOF_DESC>` section to understand what to fix.
