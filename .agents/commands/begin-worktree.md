---
description: Creates a new worktree with a matching branch for feature development
subtask: true
---

Create a new worktree and branch for feature development. Use this when you want to start work without creating specs yet.

> Load skill: worktree (for worktree creation)

**Query**: $1 (natural language — specify the branch name or feature description, e.g., "create a worktree for feat/new-ui" or just "new-ui")

---

## Instructions

1. **Determine branch name**: From `$1`, extract or ask for the branch name:
   - If user provided a name (e.g., "feat/new-ui"), use it
   - If user provided a description (e.g., "I want to build a new UI"), ask: "What branch name would you like to use?"
   - Suggest conventional format: `type/description` (e.g., `feat/new-ui`, `fix/login-bug`)

2. **Validate branch name**:
   ```bash
   # Check if branch already exists
   git show-ref --verify --quiet refs/heads/<branch-name> && echo "EXISTS"
   ```
   If branch exists, ask user if they want to reuse it or choose a different name.

3. **Derive worktree directory**: Replace all `/` in branch name with `-`:
   - Branch: `feat/new-ui` → Worktree dir: `.worktrees/feat-new-ui`
   - Branch: `fix/login-bug` → Worktree dir: `.worktrees/fix-login-bug`

4. **Create the worktree**:
   ```bash
   git worktree add .worktrees/<worktree-dir> <branch-name>
   ```
   If the branch doesn't exist yet, git will create it from HEAD.

5. **Report**: Tell the user:
   - Worktree path: `.worktrees/<worktree-dir>/`
   - Branch name: `<branch-name>`
   - How to navigate: `cd .worktrees/<worktree-dir>/`
   - Next steps: Create specs with `/plan`, or run `/begin-workflow` to start

## Important

- Always create the worktree from the current branch (typically `main`)
- The branch and worktree names must stay in sync — if you rename the branch, rename the worktree too
- After creating the worktree, you can run `/plan` or `/begin-workflow` inside it
- Use `/implement` to start implementing after specs are ready
