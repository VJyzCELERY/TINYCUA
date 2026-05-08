---
name: worktree-prune
description: Remove inactive worktrees whose branches have been merged or abandoned
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/worktree-prune.md
---

# Skill: worktree-prune — Remove Stale Worktrees

## Purpose

Remove inactive worktrees whose feature branches have been merged or abandoned. Checks PR status before removing.

## Execution

1. List all worktrees: `git worktree list`
2. For each worktree (except main): check if branch has a merged or closed PR
3. If merged/abandoned: `git worktree remove .worktrees/<branch>` and `git branch -D <branch>`
4. Report which worktrees were removed

## Common Pitfalls

- Never remove the main worktree
- Check PR status before removing — don't delete active work
- Confirm with user before bulk removal
