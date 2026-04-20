---
description: Sets up opencode project structure by cloning from GitHub or using local config
subtask: true
---

Set up the opencode project structure.

**Target Directory**: $1 (defaults to current directory if not specified)
**GitHub Repository**: $2 (optional - GitHub repo URL to clone .agents from, e.g., https://github.com/user/repo)

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
   
   # Copy commands
   cp ~/.config/opencode/commands/implementation-plan.md "$1/.agents/commands/"
   cp ~/.config/opencode/commands/implement-plan.md "$1/.agents/commands/"
   cp ~/.config/opencode/commands/review-project.md "$1/.agents/commands/"
   cp ~/.config/opencode/commands/validate-review.md "$1/.agents/commands/"
   cp ~/.config/opencode/commands/review-implement.md "$1/.agents/commands/"
   cp ~/.config/opencode/commands/develop.md "$1/.agents/commands/"
   cp ~/.config/opencode/commands/setup-project.md "$1/.agents/commands/"
   
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
│   │   │   ├── agent_rules.md
│   │   │   ├── workflow.md
│   │   │   ├── style.md
│   │   │   ├── testing.md
│   │   │   ├── debugging.md
│   │   │   ├── security.md
│   │   │   ├── code_generation.md
│   │   │   └── code_review.md
│   │   └── project_rules/
│   │       ├── naming_conventions.md
│   │       ├── project_structure.md
│   │       ├── cognitive_complexity.md
│   │       ├── commit_naming.md
│   │       ├── testing_guidelines.md
│   │       ├── logging_guidelines.md
│   │       ├── coding_standards.md
│   │       └── deployment_and_versioning.md
│   ├── AGENTS.md
│   └── reviews/
├── .opencode -> .agents (symlink)
```

## Important
- Use Bash to clone, create directories, and copy files
- If cloning from GitHub, the repo should contain the `.agents` folder content directly
- If not cloning, copy from local `~/.config/opencode/` as fallback

Begin now - set up the project structure.