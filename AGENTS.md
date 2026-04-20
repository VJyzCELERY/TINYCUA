# Agents Documentation

This project uses the `.agents/` directory for all AI agent-related configuration, commands, templates, and documentation.

**For full documentation, see: [.agents/AGENTS.md](.agents/AGENTS.md)**

---

## Quick Reference

### Available Commands

| Command | Description |
|---------|-------------|
| `/implementation-plan <dir>` | Creates plan from spec.md/design.md |
| `/implement-plan <dir>` | Executes implementation plan using TDD |
| `/review-project <dir>` | Reviews project and generates report |
| `/validate-review <file>` | Validates review findings |
| `/review-implement <file>` | Implements fixes for review findings |
| `/develop <query>` | Full development workflow |
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
└── AGENTS.md         # Full documentation
```

### Key Files

- [.agents/AGENTS.md](.agents/AGENTS.md) - Complete agent documentation index
- [.agents/docs/agents/agent_rules.md](.agents/docs/agents/agent_rules.md) - Core agent principles
- [.agents/docs/agents/workflow.md](.agents/docs/agents/workflow.md) - Development workflow
- [.agents/docs/agents/testing.md](.agents/docs/agents/testing.md) - Testing guidelines
- [.agents/docs/project_rules/coding_standards.md](.agents/docs/project_rules/coding_standards.md) - Code standards
- [.agents/docs/project_rules/naming_conventions.md](.agents/docs/project_rules/naming_conventions.md) - Naming rules

---

For detailed documentation, see [.agents/AGENTS.md](.agents/AGENTS.md)