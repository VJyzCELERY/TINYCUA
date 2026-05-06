---
description: Sets up opencode project structure by cloning from GitHub or using local config
subtask: true
---

Set up the opencode project structure.

**Target Directory**: $1 (defaults to current directory if not specified)
**GitHub Repository (Optional)**: $2 (GitHub repo URL to clone .agents from, e.g., https://github.com/user/repo)

If no GitHub repository is provided ($2 is empty), use local config from ~/.config/opencode/

## Instructions

1. **Create target directory**: Create `$1/` directory if it doesn't exist

2. **Clone from GitHub OR use local config**:

   **If GitHub repository provided ($2)**:
   ```bash
   cd "$1"
   git clone <repo-url> .agents
   ```

   **If NO GitHub repository (use local config)**:
   ```bash
    mkdir -p "$1/.agents/commands"
    mkdir -p "$1/.agents/templates"
    mkdir -p "$1/.agents/docs/agents"
    mkdir -p "$1/.agents/docs/project_rules"
    mkdir -p "$1/.agents/reviews"
    mkdir -p "$1/reviews"   # Review output directory (consistent location)

   # Copy commands
   cp ~/.config/opencode/commands/*.md "$1/.agents/commands/"

   # Copy templates
   cp ~/.config/opencode/templates/*.md "$1/.agents/templates/"
   ```

3. **Create .opencode symlink**:
   ```bash
   cd "$1"
   ln -sf .agents .opencode
   ```

## Expected Structure

After setup:
```
project/
├── .agents/
│   ├── commands/
│   │   ├── implementation-plan.md
│   │   ├── implement-plan.md
│   │   ├── review-project.md
│   │   ├── validate-review.md
│   │   ├── review-implement.md
│   │   ├── develop.md
│   │   └── setup-project.md
│   ├── templates/
│   │   ├── implementation-plan.md
│   │   ├── task.md
│   │   └── REVIEW-template.md
│   ├── docs/
│   │   ├── agents/
│   │   └── project_rules/
│   └── reviews/
├── .opencode -> .agents (symlink)
```

## Important
- Use Bash to clone, create directories, and copy files
- If cloning from GitHub, the repo should contain the `.agents` folder content directly
- If not cloning, copy from local `~/.config/opencode/` as fallback

Begin now - set up the project structure.