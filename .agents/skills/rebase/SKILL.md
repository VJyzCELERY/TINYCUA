---
name: rebase
description: Safely rebase current branch onto target without duplicating commits
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/rebase.md
---

# Skill: rebase — Safely Rebase Branch onto Target

## Purpose

Rebase current branch onto target (default: main) without duplicating already-applied commits. Delegates to the `git-rebase` skill for raw git operations.

## Prerequisites

- Load skill: git-rebase (for conflict handling details)
- Load skill: preflight (for preflight-rebase.py)

## Execution

1. Run preflight: `uv run python .agents/scripts/preflight-rebase.py --target <target>`
2. Check for already-applied commits: `git log --oneline <target>..HEAD`
3. If no unique commits, exit early
4. Run: `git rebase <target>`
5. If conflicts: analyze, present to user via question/ask tool, apply their decision
6. Verify: `git log --oneline --graph --all --decorate -10`
7. Force push: `git push --force origin <branch>`

## Common Pitfalls

- Never use `--reapply-cherry-picks` unless intentionally needed
- Always involve the user for conflict resolution — never auto-resolve
- Check commits are not already in target before rebasing
- Use worktree-specific directory: `cd .worktrees/<branch>` then rebase
