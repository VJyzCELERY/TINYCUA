---
name: begin-worktree
description: Begin worktree command guidance — use when running /begin-worktree to create a feature worktree and branch
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/begin-worktree.md
---

# Skill: begin-worktree — Create a Feature Worktree

## What I do

Guide `/begin-worktree` execution: choose a branch name, run the project worktree creation script, and report the resulting branch/path/base to the user.

## When to use me

Use this when the user invokes `/begin-worktree` or asks to create a new feature worktree before writing specs.

## How to use me

### 1. Determine the branch name

- If the user provided a branch name like `feat/new-ui`, use it directly.
- If the user provided only a feature description, ask for the branch name.
- Prefer conventional names like `feat/<description>`, `fix/<description>`, or `chore/<description>`.

### 2. Run the creation script

```bash
uv run python .agents/scripts/create-worktree.py <branch-name>
```

The script handles main repo root detection, base branch detection, name sanitization, branch-exists checks, and worktree creation. Do not pre-create the branch or worktree.

### 3. Report results

Read the script output and summarize:

- `BRANCH=...`
- `PATH=...`
- `BASE=...`
- Next steps: `cd <PATH>`, then run `/plan` or `/begin-workflow` when ready.

## Common Pitfalls

- The new branch is based on the current branch, not always `main`.
- Worktrees are created under the main repo root's `.worktrees/` directory.
- If the script prints `[FAIL]` and `[ACTION]`, follow the `[ACTION]` exactly instead of guessing.
