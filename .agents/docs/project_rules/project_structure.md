# Project Structure

## Overview
The `MAIN-PROJECT-TEMPLATE` is organized to facilitate modular subproject development and collaboration. Below is the general structure:

```
MAIN-PROJECT-TEMPLATE/
├── docs/                          # Main documentation
├── specs/                         # Project-level feature specs
│   ├── spec-template.md           # Copy for new specs
│   ├── design-template.md         # Copy for new designs
│   └── <feature-name>/            # One folder per feature
│       ├── spec.md
│       └── design.md
├── src/                           # Subprojects
│   └── my-subproject/             # lower-kebab-case subproject folder
│       ├── my_subproject/         # lower_snake_case Python package
│       │   ├── __init__.py
│       │   └── <module>/          # domain/feature subpackage
│       │       └── __init__.py
│       ├── tests/
│       │   ├── unit/
│       │   └── integration/
│       ├── specs/
│       │   ├── README.md
│       │   └── <feature-name>/
│       │       ├── spec.md
│       │       └── design.md
│       ├── docs/
│       │   ├── agents/
│       │   └── examples/
│       ├── AGENTS.md
│       ├── Makefile
│       ├── pyproject.toml         # subproject root — NOT inside the package
│       └── README.md
├── AGENTS.md
├── Makefile
├── PROJECT-GUIDELINES.md
└── README.md
```

Subprojects inherit coding standards and documentation rules from the MAIN-PROJECT but may define specific rules in their `docs/project_rules/` folder.

---

## Package Internal Layout

The Python package (`my_subproject/`) sits at the same level as `pyproject.toml`, not inside it. Domain/feature areas are organised as subpackages (modules):

```
my_subproject/
├── __init__.py
├── clients/          # HTTP clients, streaming helpers
│   └── __init__.py
├── models/           # dataclasses, schemas, types
│   └── __init__.py
└── <other-modules>/  # additional domain subpackages as needed
    └── __init__.py
```

Rules:
- `pyproject.toml` lives at the **subproject root** — never inside the package folder.
- Each domain/feature area gets its own subpackage (e.g., `clients/`, `models/`, `tools/`).
- Every subpackage must have an `__init__.py`.
- Subpackage names use `lower_snake_case`.

---

## Specs and Design Convention

Both the project root and each subproject use the same folder-per-feature convention:

| Location | When to use |
|---|---|
| `specs/<feature-name>/` | Cross-subproject or project-wide features |
| `src/<subproject>/specs/<feature-name>/` | Features scoped to a single subproject |

**Rule**: Never create a flat `spec.md` or `design.md` directly under a `specs/` folder.
Always use a named subfolder with `lower-kebab-case`.

---

## Standard Makefile for Subprojects
All subprojects must include a `Makefile` to simplify common operations. Below are the predefined targets:

- **install**: Installs all dependencies.
- **lint**: Runs the linter (Ruff) for code style checks.
- **test**: Runs the test suite using pytest.
- **coverage**: Runs tests with code coverage and generates an HTML report.
- **complexity**: Runs cognitive complexity analysis (radon).
- **clean**: Removes temporary files, artifacts, and caches.

#### Example Usage:
```bash
# Install dependencies
make install

# Run linting
make lint

# Run tests
make test

# Check coverage
make coverage

# Run complexity audit
make complexity

# Clean the project
make clean
```
