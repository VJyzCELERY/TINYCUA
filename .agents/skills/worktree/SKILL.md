---
name: worktree
description: Create, prune, and clean up git worktrees
license: MIT
compatibility: opencode
metadata:
  type: command-skill
---

# Skill: worktree — Worktree Management

## Purpose

Manage git worktrees: create new worktrees for feature development, prune inactive ones, and clean up local artifacts.

## Execution

### Create worktree
1. Ask for branch name, verify it doesn't exist locally or remotely
2. Run: `git worktree add .worktrees/<branch> <branch>`
3. Verify the worktree was created successfully

### Prune worktrees
1. List all worktrees: `git worktree list`
2. For each linked worktree: check if branch has an open PR
3. If PR is merged/closed and branch is safe to remove: `git worktree remove <path>`

### Clean up
1. Remove review files: `rm -f ./reviews/REVIEW_*.md`
2. Clean tmp directory: `rm -rf ./tmp/*`
3. Remove pycache: `find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null`

## Common Pitfalls
- Never create a worktree for a branch that already exists
- Only prune worktrees whose PRs are merged or abandoned
- Always verify before destructive operations
