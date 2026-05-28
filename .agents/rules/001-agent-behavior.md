---
description: Agent behavior, code generation rules, development workflow, and debugging practices
globs: "*.md, *.py"
alwaysApply: false
---

# Agent Behavior Rules

## Core Principles
- **Simplicity First**: Prefer simple solutions. If it feels complex, break it down.
- **Test-First**: Write failing tests before implementation. No exceptions.
- **Question the Spec**: Challenge assumptions during review — specs can be wrong.
- **No Overengineering**: Implement only what's in the spec. Avoid premature abstraction.

## Project Boundary
- Stay inside the project root. Use `./tmp/` for temp files (gitignored).
- Never use system `/tmp/` for project work.

## Code Generation
- Adopt coding standards, logging practices, and Ruff auto-fix.
- All functions/classes need Google-style docstrings with Args/Returns/Raises.
- Include tests alongside generated code (unit + integration).
- Commit messages follow conventional commits: `type(scope): message`.
- Exception handling: use `try-except` blocks, define custom exceptions when needed.
- Update comprehensive docs (`docs/full-docs/`) alongside code changes.

## Development Workflow
- Worktrees for feature branches — never develop directly on main.
- Use `uv run` for all Python/pytest commands.
- Run `make lint`, `make test`, `make complexity` before considering work complete.
