# TINYCUA

TINYCUA is a modular multi-subproject repository consisting of three primary subprojects that work together to provide a complete system.

## Subprojects
1. **tinycua-backend** - Backend services and core API functionality.
2. **tinycua-runner** - Execution engine and workflow orchestration.
3. **tinycua-sdk** - Developer SDK and integration libraries.

## Folder Structure
```
TINYCUA/
├── docs/                          # Main project-level documentation
│   ├── agents/                    # AI agent rules and guidelines
│   └── project_rules/             # Coding standards, testing, logging rules
├── specs/                         # Project-level specifications
├── src/                           # Source directory for subprojects
│   ├── tinycua-backend/
│   ├── tinycua-runner/
│   └── tinycua-sdk/
└── ...
```

## Getting Started
1. Refer to the `docs/` folder for project rules and guidelines.
2. Each subproject in `src/` is self-contained with its own documentation, tests, and configuration.
3. Use `make` commands to manage installation, testing, and linting.

## Quick Start
```bash
# Install all subproject dependencies
make install

# Run all tests
make test

# Run linting across all subprojects
make lint
```
