---
description: Commit conventions, PR guidelines, versioning, deployment
globs: "*.md, *.py"
alwaysApply: false
---

# Commits and PRs

## Commit Messages
Format: `type(scope): description`

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`, `style`
Scope: subproject or module name (e.g., `sdk`, `backend`, `cli`, `preflight`)
Description: imperative, present tense, no period at end

Examples:
- `feat(sdk): add SSE streaming with 4 modes`
- `fix(backend): resolve crash in session creation`
- `docs(readme): update installation guide`

## PR Guidelines
- Title follows conventional commit format
- Body includes: summary of changes, testing notes, related issues
- PR targets the appropriate base branch (usually `main`)
- PR description must reference the spec if applicable

## Versioning
- Follow semantic versioning: MAJOR.MINOR.PATCH
- Document breaking changes in CHANGELOG or release notes

## Complexity Limits
- Max function complexity: 10 (radon CC)
- Flag cognitive complexity during review — split complex functions

## Deployment
- Backend: Docker Compose (see `docker-compose.yml`)
- SDK: Published as PyPI package
- CLI: Installed via pip or built as executable
