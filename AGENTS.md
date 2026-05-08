# Agents Documentation

This project uses the `.agents/` directory for all AI agent-related configuration, commands, templates, and documentation.

---

## Critical: Always Ask, Read, and Check First

0. **Run start preflight** — At the start of every session, run `uv run python .agents/scripts/preflight-start.py`. This detects your OS and establishes the project boundary so you never operate outside it.
1. **Never leave the project root** — Your attached root directory is your entire world. Do NOT read, write, or execute anything outside it. If you need temporary files, use `./tmp/` (already gitignored) and clean up after yourself. Never use system `/tmp/`.
2. **Parent agents: instruct subagents to read AGENTS.md** — Whenever you delegate to a subagent, explicitly tell it to read this AGENTS.md file first. Subagents start with zero context and won't know these rules unless told.
3. **Ask when uncertain** — If any instruction is ambiguous or incomplete, use the question/ask tool to clarify. Do NOT guess. Subagents report questions to the parent orchestrator, not the user.
4. **Ask before committing** — Never commit or push without explicit user permission. Each batch needs a fresh ask unless the user grants unrestricted permission.
5. **Read rules first** — Before starting any task, read relevant rules from `.agents/docs/` (both `agents/` and `project_rules/`). Each file defines conventions and constraints.
6. **Use templates** — Before generating any document (PR body, spec, design, review, implementation plan, task list), check `.agents/templates/` first and follow the template structure.
7. **Run preflight scripts** — Commands reference preflight scripts in `.agents/scripts/`. Run them before executing the command. If a preflight fails, read the script manually to recover.
8. **Use `uv run` for Python** — Never bare `python` or `pytest`. Always `cd <subproject-dir> && uv run`.
9. **Use gh.py for PR operations** — All PR/review write operations must go through `.agents/scripts/gh.py`. Never use raw `gh pr edit`, `gh pr review`, or similar direct commands for PR writes. Check `uv run python .agents/scripts/gh.py --help` for available subcommands.

---

## Using Skills and Docs — What to Load Before Each Task

Agents have access to three layers of guidance. **Always load the relevant ones before starting a task:**

### Layer 1: Commands (`.agents/commands/`)
Commands are the entry point — they tell you what to do and which preflight to run. When you receive a slash command (e.g., `/review-report`), read the corresponding `.md` file first:
```
.agents/commands/review-report.md
.agents/commands/begin-workflow.md
.agents/commands/review-loop.md
...
```

### Layer 2: Skills (`.agents/skills/<name>/SKILL.md`)
Skills teach you **how** to use the tools and scripts. Before running any tool, load the relevant skill:

| When you need to... | Load this skill |
|---|---|
| Run any slash command | `<command-name>` — each command has a matching skill (e.g., `review-report`, `begin-workflow`, `rebase`, `plan`) |
| Create/update/post PR reviews and comments | `gh-pr-management` — all gh.py operations |
| Run the full review workflow | `gh-review` — posting reviews, inline comments, replies |
| Run any preflight script | `preflight` — session start, review, PR, rebase preflights |
| Rebase branches safely | `git-rebase` — rebase workflow, conflict handling, worktrees |
| Create or update a skill | `self-learning` — skill structure and guidelines |

If your harness does not detect skills automatically, read them directly:

> Read skill: `.agents/skills/<name>/SKILL.md`

### Layer 3: Tools (`.agents/tools/*.ts`)
Tools are the executable functions agents can call directly (opencone custom tool format). The following tools are available:

| Tool | What it does |
|------|-------------|
| `gh_fetch` | Fetch PR info, comments, or unresolved reviews |
| `gh_post` | Post review, comment, reply, or inline comment on a PR |
| `gh_resolve` | Resolve a PR review thread |
| `gh_create` | Create a new GitHub PR |
| `gh_update` | Update a PR body |
| `preflight_start` | Detect OS and establish project boundary |
| `preflight_review` | Check review scope, staleness, and unstaged changes |
| `preflight_pr` | Detect PR number from current branch |
| `preflight_rebase` | Check rebase safety and list commits |

These tools invoke the Python scripts in `.agents/scripts/`. If your harness does not detect tools, use the scripts directly:

> uv run python .agents/scripts/gh.py --help
> uv run python .agents/scripts/preflight-review.py --help

### Layer 3: Docs (`.agents/docs/`)
Docs define conventions and constraints. Read the relevant ones before generating code or documents:

- `.agents/docs/agents/` — agent behavior rules, workflow, style, testing, code review standards
- `.agents/docs/project_rules/` — naming, project structure, commit style, coding standards, testing guidelines

### Layer 4: Scripts (`.agents/scripts/`)
Scripts are the executable tools. Check a script's own usage before running it:
```
uv run python .agents/scripts/gh.py --help
uv run python .agents/scripts/preflight-review.py --help
```

Read the `<EOF_DESC>` section in any preflight script to understand what it checks:
```
head -20 .agents/scripts/preflight-review.py
```

---

## Quick Reference

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
│   ├── begin-workflow/
│   ├── begin-worktree/
│   ├── commit-cleanup/
│   ├── gh-pr-management/
│   ├── gh-review/
│   ├── git-rebase/
│   ├── implement/
│   ├── plan/
│   ├── preflight/
│   ├── rebase/
│   ├── review-cleanup/
│   ├── review-clarify/
│   ├── review-fetch/
│   ├── review-implement/
│   ├── review-loop/
│   ├── review-post/
│   ├── review-report/
│   ├── review-update/
│   ├── review-validate/
│   ├── review-verify/
│   ├── self-learning/
│   ├── setup-project/
│   ├── worktree-cleanup/
│   └── worktree-prune/
├── scripts/           # Reusable Python scripts (cross-platform)
│   ├── gh.py          # All PR/review operations via REST API
│   ├── preflight-start.py  # OS detection + project boundary (run at session start)
│   ├── preflight-review.py
│   ├── preflight-pr.py
│   └── preflight-rebase.py
├── tools/             # Opencode custom tool definitions (calls scripts/)
│   ├── gh.ts          # gh.py wrapped as opencode tools
│   └── preflight.ts   # preflight scripts wrapped as opencode tools
├── docs/
│   ├── agents/        # Agent rules and guidelines
│   ├── project_rules/ # Project-specific rules
│   └── guides.md      # Human-readable command guide
├── reviews/           # Archived reviews
───
reviews/              # Active review outputs (root level)
```

All commands reference preflight scripts. Run them first. If they fail, read the script's `<EOF_DESC>` section manually to understand what to fix.
