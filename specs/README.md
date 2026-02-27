# Specifications Folder

## Overview

This folder contains all feature and project-level specifications.

---

## How to Use

1. **Create a folder** for each feature or initiative: `specs/<feature-name>/`
2. **Copy the templates** into the folder and fill them in:
   - `spec.md` — the "what and why" (adapted from `specs/spec-template.md`)
   - `design.md` — the "how" (adapted from `specs/design-template.md`)
3. **Resolve all** `[NEEDS CLARIFICATION]` markers before implementation begins
4. Keep specs up to date as the implementation evolves

---

## Workflow

```
specs/spec-template.md  →  specs/<feature>/spec.md   (WHAT / WHY)
specs/design-template.md → specs/<feature>/design.md  (HOW)
```

1. **Spec first**: Write `spec.md` — define the problem, requirements, and success criteria
2. **Design second**: Write `design.md` — define architecture, data model, API contracts, phases
3. **Implement**: Code against the design; keep spec/design updated if scope changes
4. **Review**: During code review, compare implementation against `spec.md` requirements

---

## Templates

| Template | Purpose |
|----------|---------|
| `spec-template.md` | Feature specification (WHAT/WHY — no implementation details) |
| `design-template.md` | Technical design document (HOW — architecture, contracts, phases) |

---

## Directory Structure

```
specs/
├── README.md             ← this file
├── spec-template.md      ← copy this for new feature specs
├── design-template.md    ← copy this for new design docs
└── <feature-name>/
    ├── spec.md
    └── design.md
```
