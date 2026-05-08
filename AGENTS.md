# Agents Documentation

This project uses the `.agents/` directory for all AI agent-related configuration, commands, templates, and documentation.

**Baseline harness is opencode, but all instructions are harness-agnostic.** If your harness does not support a specific mechanism (skill loading, tool detection, etc.), fall back to reading files directly and executing commands via bash.

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
| Create or update a skill | `self-learning` — skill structure, frontmatter, and `.agents/templates/skill.md` |

If your harness does not detect skills automatically, read them from the directory directly — the skill files are always at `.agents/skills/<name>/SKILL.md` and you can list them with `ls .agents/skills/`.

The full list of available skills is also documented in XML format (matching opencode convention):

```
<available_skills>
  <skill>
    <name>begin-workflow</name>
    <description>Automate the complete specs implementation process using subagents for each phase</description>
  </skill>
  <skill>
    <name>begin-worktree</name>
    <description>Create isolated development worktrees with matching branches</description>
  </skill>
  <skill>
    <name>commit-cleanup</name>
    <description>Clean up commit history after rebase — squash fixups, remove duplicates</description>
  </skill>
  <skill>
    <name>gh-pr-management</name>
    <description>Create, update, and manage GitHub PRs via gh.py</description>
  </skill>
  <skill>
    <name>gh-review</name>
    <description>Post, reply, resolve, and update PR reviews via gh.py and gh api</description>
  </skill>
  <skill>
    <name>git-rebase</name>
    <description>Safely rebase branches without dirtying history</description>
  </skill>
  <skill>
    <name>implement</name>
    <description>Execute implementation plan tasks using strict TDD</description>
  </skill>
  <skill>
    <name>plan</name>
    <description>Create implementation plans and task lists from spec and design documents</description>
  </skill>
  <skill>
    <name>preflight</name>
    <description>Run preflight checks before session start, reviews, PRs, and rebases</description>
  </skill>
  <skill>
    <name>rebase</name>
    <description>Safely rebase current branch onto target without duplicating commits</description>
  </skill>
  <skill>
    <name>review-cleanup</name>
    <description>Archive resolved review reports after all findings are addressed</description>
  </skill>
  <skill>
    <name>review-clarify</name>
    <description>Improve review finding precision — rewrite vague descriptions, add context</description>
  </skill>
  <skill>
    <name>review-fetch</name>
    <description>Fetch unresolved PR review comments into a local structured report</description>
  </skill>
  <skill>
    <name>review-implement</name>
    <description>Apply code fixes from review findings without updating the review report</description>
  </skill>
  <skill>
    <name>review-loop</name>
    <description>Orchestrate review-until-clean cycles with fresh subagents per step</description>
  </skill>
  <skill>
    <name>review-post</name>
    <description>Post completed review reports as GitHub PR reviews with inline comments</description>
  </skill>
  <skill>
    <name>review-report</name>
    <description>Conduct scoped code reviews of branch changes and generate structured reports</description>
  </skill>
  <skill>
    <name>review-update</name>
    <description>Update PR reviews after fixes — resolve addressed, reply on remaining</description>
  </skill>
  <skill>
    <name>review-validate</name>
    <description>Run the complete validation pipeline — clarify then verify findings</description>
  </skill>
  <skill>
    <name>review-verify</name>
    <description>Execute validation commands to determine finding status — addressed, invalid, or open</description>
  </skill>
  <skill>
    <name>self-learning</name>
    <description>Guide for creating and updating project-specific agent skills</description>
  </skill>
  <skill>
    <name>setup-project</name>
    <description>Bootstrap or update .agents/ structure from MAIN-PROJECT-TEMPLATE</description>
  </skill>
  <skill>
    <name>worktree-cleanup</name>
    <description>Remove local artifacts in current worktree — reviews, tmp, caches</description>
  </skill>
  <skill>
    <name>worktree-prune</name>
    <description>Remove inactive worktrees whose branches have been merged or abandoned</description>
  </skill>
</available_skills>
```

The agent loads a skill by calling the native mechanism (if your harness has one). If your harness does not support it, read the file directly:

```
# Native skill loading (harness-dependent):
#   opencode: skill({ name: "review-report" })
#   claude:   Read .agents/skills/review-report/SKILL.md
#   generic:  Read .agents/skills/review-report/SKILL.md
```

If you don't know what harness you're on, list available skills and read the one you need:

```
ls .agents/skills/
# then
Read .agents/skills/<name>/SKILL.md
```

### Layer 3: Tools (`.agents/tools/*.ts`)
Tools are the executable functions agents can call directly (opencode custom tool format). The following tools are available:

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
| Load skill template | `.agents/templates/skill.md` — frontmatter + structure for new skills |

---

## Directory Structure

```
.agents/
├── commands/          # Slash command definitions (harness-agnostic)
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
├── tools/             # Custom tool definitions (opencode custom tool format, calls scripts/)
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
