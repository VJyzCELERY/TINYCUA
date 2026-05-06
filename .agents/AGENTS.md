# Agents Documentation Index

This file serves as an index for navigating the AI agent-related documentation stored in `.agents/docs/`.

---

## Available Commands

| Command | Description |
|---------|-------------|
| `/implementation-plan <dir>` | Creates implementation-plan.md and task.md from spec.md and design.md |
| `/implement-plan <dir>` | Executes implementation plan using TDD |
| `/review-project <dir>` | Reviews a project and generates a report |
| `/validate-review <file>` | Validates findings from a previous review |
| `/review-implement <file>` | Implements fixes for review findings |
| `/develop <query>` | Full development workflow |
| `/setup-project <dir>` | Sets up project with .agents structure |

Run any command by typing it directly in opencode.

---

## Critical: Use `uv run` for All Python/Pytest Commands

This project uses `uv` for Python environment management. **Never use bare `python` or `pytest`** — they may import from the wrong worktree.

Always prefix Python invocations with `uv run --directory src/<subproject>`:

```bash
# ✅ Correct
uv run --directory src/tinycua-sdk python script.py
uv run --directory src/tinycua-sdk pytest tests/

# ❌ Wrong
python script.py
pytest tests/
```

See [Workflow docs](docs/agents/workflow.md) for full details.

---

## Review File Convention

All review files live at `./reviews/REVIEW-{name}.md` (relative to repo root / workdir).  
This is a consistent, predictable location so agents always know where to find reviews.

| Command | Output Location |
|---------|----------------|
| `/review-project <dir>` | Writes to `./reviews/REVIEW-{dir-name}.md` |
| `/validate-review <file>` | Updates `./reviews/REVIEW-{name}.md` |
| `/review-implement <file>` | Updates statuses in `./reviews/REVIEW-{name}.md` |

---

## Documentation Contents

### 1. [Agent Rules](docs/agents/agent_rules.md)
   - Core principles: Simplicity First, Test-First, Question the Spec, No Overengineering.
   - General agent behavior rules and code generation expectations.

### 2. [Workflow](docs/agents/workflow.md)
   - Development commands (`make lint`, `make test`, `make coverage`, etc.).
   - Commit and PR guidelines.
   - Feature development workflow (spec → design → test → implement → review).

### 3. [Style](docs/agents/style.md)
   - Code formatting rules: line length, quotes, indentation.
   - Naming conventions: modules, classes, functions, constants.
   - Docstring format (Google-style) and pre-commit iteration.

### 4. [Testing](docs/agents/testing.md)
   - Test directory structure and naming conventions.
   - Test-first workflow, fixture usage, coverage requirements.
   - Edge cases to always cover.

### 5. [Debugging](docs/agents/debugging.md)
   - Debugging workflow and log checking patterns.
   - Common root causes and how to isolate issues.

### 6. [Security](docs/agents/security.md)
   - Secrets and credentials handling.
   - Environment variable patterns and `.env.example` convention.
   - Input validation and error handling principles.

### 7. [Code Generation](docs/agents/code_generation.md)
   - Rules for AI-generated code: docstrings, testing expectations, commit naming.

### 8. [Code Review](docs/agents/code_review.md)
   - Review principles, overengineering detection, spec compliance checks.
   - Review format, severity levels, and communication style.

---

## Project Rules

### 9. [Naming Conventions](docs/project_rules/naming_conventions.md)

### 10. [Project Structure](docs/project_rules/project_structure.md)

### 11. [Cognitive Complexity](docs/project_rules/cognitive_complexity.md)

### 12. [Commit Naming](docs/project_rules/commit_naming.md)

### 13. [Testing Guidelines](docs/project_rules/testing_guidelines.md)

### 14. [Logging Guidelines](docs/project_rules/logging_guidelines.md)

### 15. [Coding Standards](docs/project_rules/coding_standards.md)

### 16. [Deployment and Versioning](docs/project_rules/deployment_and_versioning.md)

---

## Directory Structure

```
.agents/
├── commands/          # Opencode commands
│   ├── implementation-plan.md
│   ├── implement-plan.md
│   ├── review-project.md
│   ├── validate-review.md
│   ├── review-implement.md
│   ├── develop.md
│   └── setup-project.md
├── templates/         # Document templates
│   ├── implementation-plan.md
│   ├── task.md
│   └── REVIEW-template.md
├── docs/
│   ├── agents/       # Agent rules and guidelines
│   └── project_rules/ # Project-specific rules
├── reviews/          # Review outputs
└── AGENTS.md         # This file
```

---

## Quick Start

1. **Setup project**: Run `/setup-project <project-dir>` to initialize
2. **Create plan**: Run `/implementation-plan <dir>` with spec.md and design.md
3. **Implement**: Run `/implement-plan <dir>` to execute the plan
4. **Review**: Run `/review-project <dir>` to review code
5. **Validate**: Run `/validate-review <review-file>` to validate findings
6. **Fix**: Run `/review-implement <review-file>` to implement fixes