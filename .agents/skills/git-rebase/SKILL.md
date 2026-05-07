# Skill: Git Rebase Without Dirtying History

## Safe Rebase Workflow

### 1. Check Current State

```bash
git log --oneline --graph --all --decorate -20
```

Understand the branch structure before rebasing.

### 2. Rebase a Branch onto Another

```bash
# Rebase current branch onto main
git rebase main

# Rebase a specific branch onto main (from any checkout)
git rebase main <branch-name>
```

### 3. Handle Conflicts

```bash
# If conflicts occur during rebase:
git status                    # see which files conflict
# Fix conflicts manually
git add <resolved-file>       # stage resolved file
git rebase --continue         # continue rebase

# To abort rebase entirely:
git rebase --abort
```

### 4. Verify After Rebase

```bash
git log --oneline --graph --all --decorate -10
git diff main...HEAD --stat   # check what changed vs main
```

## Preserving Commit Hygiene

### Avoid Merge Commits

- **Do** use `git rebase` instead of `git merge` to keep linear history
- **Don't** create merge commits when syncing with upstream
- Merge commits dirty history with noise from the base branch

### Autosquash for Fixup Commits

```bash
# Mark a commit as fixup of an earlier commit
git commit --fixup <sha>

# Then rebase to squash fixups into their targets
git rebase -i --autosquash <base>
```

Note: `-i` (interactive) is not supported in non-interactive environments. Use `--autosquash` with `GIT_SEQUENCE_EDITOR=true`:

```bash
GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <base>
```

### Cherry-Pick Specific Commits

```bash
# Pick specific commits onto current branch
git cherry-pick <sha1> <sha2>

# Cherry-pick with automatic commit
git cherry-pick --no-commit <sha>   # stage changes without committing
```

## Rebase with Worktrees

When branches are checked out in separate worktrees:

```bash
# Navigate to the worktree directory first
cd .worktrees/<branch-name>

# Then rebase from within the worktree
git rebase <target-branch>

# Return to main worktree
cd /path/to/main/worktree
```

## Cleanup After Rebase

After a successful rebase, if the branch was previously pushed:

```bash
# Force push is required since history was rewritten
git push --force origin <branch-name>
```

## Common Mistakes

| Mistake | Correct Approach |
|---------|-----------------|
| `git merge main` instead of rebase | Use `git rebase main` for linear history |
| Rebasing a shared/public branch | Only rebase branches you own |
| Force pushing without warning | Coordinate with team before force push |
| Interactive rebase in CI/non-TTY | Use `GIT_SEQUENCE_EDITOR=true git rebase -i` |
| Using `git pull` (creates merge) | Use `git pull --rebase` or `git fetch + rebase` |

## Golden Rule

**Never rebase commits that exist on a shared remote branch.** Only rebase your own feature branches before they've been merged.
