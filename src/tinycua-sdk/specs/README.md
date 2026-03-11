# Specifications for tinycua-sdk

## Overview

This folder houses specifications and design documents specific to `tinycua-sdk`.

## Convention

Specs are organised by feature, not stored flat. Each feature has its own subfolder:

```
specs/
└── <feature-name>/
    ├── spec.md      # "what and why" — requirements and acceptance criteria
    └── design.md   # "how" — architecture, decisions, implementation phases
```

Use `lower-kebab-case` for all subfolder names.

## Adding a New Feature Spec

1. Create `specs/<feature-name>/`
2. Copy `spec.md` from `../../../../specs/spec-template.md` and fill it in.
3. Copy `design.md` from `../../../../specs/design-template.md` and fill it in.
4. Resolve all `[NEEDS CLARIFICATION]` markers before starting implementation.

## Features

| Feature | Spec | Design |
|---------|------|--------|
| _(none yet — add rows as features are specced)_ | | |
