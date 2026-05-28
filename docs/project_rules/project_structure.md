# Project Structure

## Overview
TINYCUA is organized to facilitate modular subproject development and collaboration. Below is the general structure:

```
TINYCUA/
├── docs/                          # Main documentation
│   ├── agents/                    # AI agent rules and guidelines
│   └── project_rules/             # Coding standards, testing, logging rules
├── specs/                         # Project-level specifications
│   └── <feature-name>/
│       ├── spec.md
│       └── design.md
├── src/                           # Subprojects
│   ├── tinycua-backend/
│   ├── tinycua-finetune/
│   ├── tinycua-runner/
│   └── tinycua-sdk/
├── .gitignore
├── AGENTS.md
├── Makefile
├── PROJECT-GUIDELINES.md
└── README.md
```

Subprojects inherit coding standards and documentation rules from TINYCUA but may define specific rules in their `docs/project_rules/` folder.

---

## Package Internal Layout

The Python package (`my_subproject/`) sits at the same level as `pyproject.toml`, not inside it. Domain/feature areas are organised as subpackages:

```
src/
└── my-subproject/                 # lower-kebab-case subproject folder
    ├── my_subproject/             # lower_snake_case Python package
    │   ├── __init__.py
    │   └── <module>/              # domain/feature subpackage (lower_snake_case)
    │       └── __init__.py
    ├── tests/
    │   ├── unit/
    │   └── integration/
    ├── specs/
    │   ├── README.md
    │   └── <feature-name>/
    │       ├── spec.md
    │       └── design.md
    ├── docs/
    │   ├── agents/
    │   └── examples/
    ├── AGENTS.md
    ├── Makefile
    ├── pyproject.toml             ← subproject root, NOT inside the package
    └── README.md
```

Rules:
- `pyproject.toml` lives at the **subproject root** — never inside the package folder.
- Each domain/feature area gets its own subpackage (e.g., `clients/`, `models/`, `tools/`).
- Every subpackage must have an `__init__.py`.
- Subpackage names use `lower_snake_case`.

---

## Specs Convention

Specs are **never** stored as flat files directly inside a `specs/` folder. Every spec belongs in a named feature subfolder. This applies at both the project level and inside each subproject.

| Level | Path pattern |
|-------|-------------|
| Project-wide | `specs/<feature-name>/spec.md` and `design.md` |
| Subproject-scoped | `src/<subproject>/specs/<feature-name>/spec.md` and `design.md` |

Subfolder names use `lower-kebab-case`.

---

## Standard Makefile for Subprojects
All subprojects must include a `Makefile` to simplify common operations. Below are the predefined targets:

- **install**: Installs all dependencies.
- **lint**: Runs the linter (Ruff) for code style checks.
- **test**: Runs the test suite using pytest.
- **coverage**: Runs tests with code coverage and generates an HTML report.
- **complexity**: Checks cognitive complexity with radon.
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

# Check complexity
make complexity

# Clean the project
make clean
```
