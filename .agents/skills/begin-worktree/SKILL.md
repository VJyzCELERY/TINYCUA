---
name: begin-worktree
description: Create isolated development worktrees with matching branches
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/begin-worktree.md
---

# Skill: begin-worktree — Create Isolated Development Worktree

## Purpose

Create a new git worktree at `.worktrees/<branch>/` with a matching branch for isolated feature development.

## Execution

```bash
# Create worktree and branch
git worktree add .worktrees/<branch> -b <branch> main

# Navigate to worktree
cd .worktrees/<branch>
```

## Common Pitfalls

- Always base off `main` unless explicitly told otherwise
- Use kebab-case for branch names (e.g., `feat/my-feature`)
- Never create nested worktrees — one per feature
- Run `preflight-start.py` when entering a new worktree session
