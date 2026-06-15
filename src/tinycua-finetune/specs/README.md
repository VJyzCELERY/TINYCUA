# Specifications for tinycua-finetune

## Overview

This folder contains all feature specifications and design documents specific to this
subproject. Each feature gets its own subfolder, mirroring the convention used in the
root-level `specs/` folder.

---

## How to Use

1. **Create a folder** for each feature: `specs/<feature-name>/`
2. **Copy the root templates** and fill them in:
   - `spec.md` — the "what and why" (copy from `../../../specs/spec-template.md`)
   - `design.md` — the "how" (copy from `../../../specs/design-template.md`)
3. **Resolve all** `[NEEDS CLARIFICATION]` markers before implementation begins
4. Keep specs up to date as the implementation evolves

---

## Workflow

```
../../../specs/spec-template.md   →  specs/<feature>/spec.md   (WHAT / WHY)
../../../specs/design-template.md →  specs/<feature>/design.md  (HOW)
```

1. **Spec first**: Write `spec.md` — problem statement, requirements, acceptance scenarios
2. **Design second**: Write `design.md` — architecture, data model, API contracts, phases
3. **Implement**: Code against the design; keep spec/design updated if scope changes
4. **Review**: During code review, compare implementation against `spec.md` requirements

---

## Directory Structure

```
specs/
├── README.md                       ← this file
└── <feature-name>/
    ├── spec.md                     ← WHAT and WHY (filled from spec-template.md)
    └── design.md                   ← HOW (filled from design-template.md)
```

### Existing Features

| Feature | Spec | Design |
|---------|------|--------|
| `tinycua-finetune` (subproject scaffold) | [spec.md](tinycua-finetune/spec.md) | [design.md](tinycua-finetune/design.md) |

---

## Notes

- One folder per feature. Do not create a flat `spec.md` or `design.md` directly under
  `specs/` — always use a named subfolder.
- Feature folder names use `lower-kebab-case`.
- The authoritative templates are at the repo root: `../../../specs/spec-template.md`
  and `../../../specs/design-template.md`.
