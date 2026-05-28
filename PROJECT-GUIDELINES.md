# Project Guidelines

This document outlines the core principles and organizational rules for any project built from this template.

---

## Core Principles

### 1. Simplicity First

If the solution feels complex, it is. Break it down.

- Prefer simple solutions over clever ones
- Inline single-use helpers instead of extracting them
- Avoid premature abstraction
- Question every layer of indirection

### 2. Test-First

Write failing tests before implementation. No exceptions.

- Unit tests must exist for all new logic
- Integration tests for workflows and APIs
- Tests validate the spec, not just the code
- Coverage is a side effect, not the goal

### 3. Question the Spec

During review, challenge assumptions. Specs can be wrong.

- Does the spec make sense?
- Are there gaps or contradictions?
- Is the proposed solution minimal?
- Flag spec issues early — do not blindly implement

### 4. No Overengineering

Implement only what is in the spec. Avoid flexibility that is not needed yet.

- Simple code is maintainable code
- Flag gold-plating and premature optimization
- Do not add features not requested by the spec

---

## Tooling Decisions

1. **Ruff** is used for code style enforcement (linting + formatting).
2. **uv** is used for package management in Python.
3. **pytest** is used for all testing, with **pytest-cov** for coverage.
4. **radon** is used to check cognitive complexity alongside Ruff C901.

---

## Specifications and Design Rules

Specs live in `specs/` folders — both at the project root and inside each subproject.
**Never** create a flat `spec.md` or `design.md` directly inside `specs/`.
Always use a named feature subfolder.

### Project-level specs (root `specs/`)

For cross-subproject or project-wide features:

1. Create `specs/<feature-name>/`
2. Add two files using the root templates:
   - `spec.md` — the "what and why" (copy from `specs/spec-template.md`)
   - `design.md` — the "how" (copy from `specs/design-template.md`)
3. Resolve all `[NEEDS CLARIFICATION]` markers before starting implementation

### Subproject-level specs (`src/<subproject>/specs/`)

For features scoped to a single subproject:

1. Create `src/<subproject>/specs/<feature-name>/`
2. Add two files using the root templates:
   - `spec.md` (copy from `specs/spec-template.md`)
   - `design.md` (copy from `specs/design-template.md`)
3. Update `src/<subproject>/specs/README.md` features table
4. Resolve all `[NEEDS CLARIFICATION]` markers before starting implementation

Feature subfolder names use `lower-kebab-case`.

---

## Subproject Rules

- Subprojects live in `src/` using lower-kebab-case folder names (e.g., `src/my-subproject/`)
- Source code (Python package) folders use lower_snake_case (e.g., `my_subproject/`)
- Each subproject must have:
  - `docs/agents/` — agent rules and guidelines
  - `docs/project_rules/` — project-specific rules
  - `specs/` — feature specs in `specs/<feature-name>/` subfolders (see above)
  - `tests/unit/` and `tests/integration/` — test directories
  - `Makefile` with `install`, `lint`, `test`, `coverage`, `complexity`, `clean` targets
  - `pyproject.toml` configured with Ruff, pytest, and radon

### Package Internal Layout

The Python package folder sits alongside `pyproject.toml` at the subproject root.
Inside the package, code is organised into domain/feature subpackages (modules):

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
    ├── docs/
    ├── AGENTS.md
    ├── Makefile
    ├── pyproject.toml             ← subproject root, NOT inside the package
    └── README.md
```

Rules:
- `pyproject.toml` lives at the subproject root — never inside the package folder.
- Each domain/feature area gets its own subpackage folder (e.g., `clients/`, `models/`, `tools/`).
- Every subpackage must have an `__init__.py`.
- Keep subpackage names short and noun-based (`lower_snake_case`).
