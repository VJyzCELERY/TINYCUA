# Project Guidelines

This document outlines the general rules and best practices for the TINYCUA project.

---

## Decisions
1. **Ruff** will be used for code style enforcement.
2. **uv** will be used for package management in Python.

---

## Specifications and Design Rules
Specifications are stored in the `specs/` folder. When creating a new spec:
1. Create a folder within `specs/`.
2. Add two files:
   - `spec.md`: The detailed specification.
   - `design.md`: Visual/technical design associated with the spec.

---

## Subproject Rules
- Subprojects live in `src/`.
- Each subproject must have its own documentation in `docs/` and follow the `docs/agents`, `docs/examples`, and `docs/project_rules` structure.
- Common tools (e.g., `ruff`, `pytest`) must be configured per subproject.
