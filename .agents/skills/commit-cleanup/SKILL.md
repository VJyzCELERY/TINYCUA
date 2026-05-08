---
name: commit-cleanup
description: Clean up commit history after rebase — squash fixups, remove duplicates
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/commit-cleanup.md
---

# Skill: commit-cleanup — Squash Fixups, Remove Duplicates

## Purpose

Clean up commit history after rebase: squash fixup!/squash! commits, remove duplicate commits already in target.

## Execution

1. Run preflight: `uv run python .agents/scripts/preflight-rebase.py --target main --list-commits`
2. Count fixup/squash commits: `git log --oneline main..HEAD | grep -c 'fixup!\|squash!'`
3. If fixups exist: `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash main`
4. Detect duplicates: `git log --oneline --left-right main...HEAD --cherry-pick | grep '^<' | wc -l`
5. If duplicates exist: `git rebase main` (drops already-applied commits)
6. Verify: `git log --oneline main..HEAD`

## Common Pitfalls

- Only squash fixup!/squash! markers — never squash meaningful commits together
- After cleanup, force push is required if branch was previously pushed
- Do NOT squash fixups across worktrees — each worktree has its own refs
