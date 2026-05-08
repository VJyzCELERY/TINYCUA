# Skill: worktree-cleanup — Clean Local Artifacts

## Purpose

Clean up local artifacts in the current worktree: review files, temp files, dev directories, caches.

## Execution

1. Delete `./reviews/` directory
2. Delete `./tmp/` directory
3. Delete `./dev/` directory
4. Delete Python cache directories (`__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`)
5. Report what was cleaned

## Common Pitfalls

- Only clean the current worktree — not the main repo or other worktrees
- Confirm with user before deleting if unsure
