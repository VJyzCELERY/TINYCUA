# Agents Documentation

This project uses the `.agents/` directory for all AI agent-related configuration, commands, templates, and documentation.

---

## Quick Reference

### Available Commands

| Command | Description |
|---------|-------------|
| `/begin-workflow <dir>` | Automates complete specs implementation process |
| `/plan <dir>` | Creates implementation plan from spec.md/design.md |
| `/implement <dir>` | Executes implementation plan using TDD |
| `/review-report <dir>` | Reviews project changes and generates a scoped report |
| `/review-validate <file>` | Validates findings from a previous review |
| `/review-implement <file>` | Implements fixes for review findings |
| `/review-cleanup <file>` | Archives resolved reviews |
| `/setup-project <dir>` | Sets up project with .agents structure |

### Project Structure

```
.agents/
├── commands/          # Opencode commands
├── templates/         # Document templates
├── docs/
│   ├── agents/       # Agent rules and guidelines
│   └── project_rules/ # Project-specific rules
├── reviews/          # Review outputs
└── AGENTS.md         # [REMOVED]
```

### Key Files

- [.agents/docs/agents/agent_rules.md](.agents/docs/agents/agent_rules.md) — Core agent principles
- [.agents/docs/agents/workflow.md](.agents/docs/agents/workflow.md) — Development workflow
- [.agents/docs/agents/style.md](.agents/docs/agents/style.md) — Code formatting and naming
- [.agents/docs/agents/testing.md](.agents/docs/agents/testing.md) — Testing guidelines
- [.agents/docs/agents/debugging.md](.agents/docs/agents/debugging.md) — Debugging guide
- [.agents/docs/agents/security.md](.agents/docs/agents/security.md) — Security guidelines
- [.agents/docs/agents/code_generation.md](.agents/docs/agents/code_generation.md) — AI code generation rules
- [.agents/docs/agents/code_review.md](.agents/docs/agents/code_review.md) — Review standards
- [.agents/docs/project_rules/naming_conventions.md](.agents/docs/project_rules/naming_conventions.md) — Naming rules
- [.agents/docs/project_rules/project_structure.md](.agents/docs/project_rules/project_structure.md) — Project structure
- [.agents/docs/project_rules/cognitive_complexity.md](.agents/docs/project_rules/cognitive_complexity.md) — Complexity rules
- [.agents/docs/project_rules/commit_naming.md](.agents/docs/project_rules/commit_naming.md) — Commit naming rules
- [.agents/docs/project_rules/testing_guidelines.md](.agents/docs/project_rules/testing_guidelines.md) — Full testing rules
- [.agents/docs/project_rules/logging_guidelines.md](.agents/docs/project_rules/logging_guidelines.md) — Logging standards
- [.agents/docs/project_rules/coding_standards.md](.agents/docs/project_rules/coding_standards.md) — Code standards
- [.agents/docs/project_rules/deployment_and_versioning.md](.agents/docs/project_rules/deployment_and_versioning.md) — Deployment guidelines

---

## Critical: Use `uv run` for All Python/Pytest Commands

This project uses `uv` for Python environment management. **Never use bare `python` or `pytest`** — they may import from the wrong worktree.

Always `cd` into the subproject directory first, then use `uv run`:

```bash
# ✅ Correct
cd src/tinycua-sdk && uv run python script.py
cd src/tinycua-sdk && uv run pytest tests/

# ❌ Wrong
python script.py
pytest tests/
```

See [Workflow docs](.agents/docs/agents/workflow.md) for full details.

---

## Review File Convention

All review files live at `./reviews/REVIEW-{name}.md` (relative to repo root / workdir).
This is a consistent, predictable location so agents always know where to find reviews.

| Command | Output Location |
|---------|----------------|
| `/review-report <dir>` | Writes to `./reviews/REVIEW-{name}.md` |
| `/review-validate <file>` | Updates `./reviews/REVIEW-{name}.md` |
| `/review-implement <file>` | Updates statuses in `./reviews/REVIEW-{name}.md` |

---

## Quick Start

1. **Setup project**: Run `/setup-project <project-dir>` to initialize
2. **Create plan**: Run `/plan <dir>` with spec.md and design.md
3. **Implement**: Run `/implement <dir>` to execute the plan
4. **Review**: Run `/review-report <dir>` to review code
5. **Validate**: Run `/review-validate <review-file>` to validate findings
6. **Fix**: Run `/review-implement <review-file>` to implement fixes
