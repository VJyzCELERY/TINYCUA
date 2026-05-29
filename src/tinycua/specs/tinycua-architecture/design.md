# Design Document: TINYCUA Architecture Documentation

> **Category:** Design Doc
> **Spec:** ./spec.md
> **Status:** Implemented
> **Last Updated:** 2026-05-26

---

## Overview

Establish `src/tinycua/docs/architecture/` as the single source of truth for TINYCUA's agent architecture documentation. Each component gets its own kebab-case file, all linked from a README index. No code changes.

---

## Architecture

### Directory Structure

```
src/tinycua/docs/architecture/
├── README.md                    # Index of all docs (required)
├── <component>.md               # One file per architecture component
└── ...
```

### Naming Convention

All files use **kebab-case** (e.g., `query-analyst.md`, `task-execution.md`). Files are categorized by type:

| Category | Description | Example |
|----------|-------------|---------|
| Architecture Overview | Top-level routing modes, agent reference, and architecture thesis | `overview.md` |
| Agent Spec | Describes an LLM-powered agent (role, flow, tools, design decisions) | `query-analyst.md` |
| Process Spec | Describes a deterministic non-agent process or system (session model, orchestration) | `worker-orchestration.md` |
| Tool Spec | Describes a tool available to agents (interface, retrieval flow, search contract) | `context-retrieval.md` |
| Decision Record | Captures design tradeoffs and resolved decisions | `analysis-<topic>.md` |
| Reference Spec | Documents shared data structures, state objects, or schemas | `state-objects.md` |
| Design Note | Describes a design pattern, rubric, or guideline without being a formal decision record | `task-classification.md` |

Additional categories may be introduced as the architecture evolves. These core categories are the minimum starting point.

### Fixed Files

- **`README.md`** — Must exist. Acts as the entry-point index, listing all architecture docs grouped by category with descriptions and links.

### Cross-Reference Convention

All internal links use relative `[display text](kebab-case-file.md)`:
```markdown
> **See also:** [Overview](overview.md), [Information Digester](information-digestion.md)
```

---

## Data Model

### Doc File Structure

Each agent spec doc includes:
- `>` header block with `Category`, blank line, `File`, `Last Updated`, `Status`, and `See also` fields
- `## Role` section
- `## Inputs / Outputs` section
- `## Internal Flow` section (Mermaid diagram)
- `## Design Decisions` table

### Process Doc Structure

Each process spec doc includes at minimum:
- `>` header block with `Category`, blank line, `File`, `Last Updated`, `Status`, and `See also` fields
- `## Role` section

Where applicable, process specs should also include:
- `## Inputs / Outputs` section (recommended — format may vary by component)
- `## Internal Flow` section (Mermaid diagram)

### README Structure

```
# TINYCUA Architecture

## Architecture Overview
| File | Description |
| ...

## Agent Specifications
| File | Description |
| ...

## Process Specifications
| File | Description |
| ...

## Tool Specifications
| File | Description |
| ...

## Reference Specifications
| File | Description |
| ...

## Design Notes
| File | Description |
| ...

## Decision Records
| File | Description |
| ...
```

The README should also include a numbered learning path section guiding new readers through the docs in logical order, placed before the category reference tables.

The README sections map directly to the file categories above. Additional sections may be added as new categories are introduced.

---

## Implementation Phases

### Phase 1 — MVP

- [x] Create `src/tinycua/docs/architecture/` directory
- [x] Create `README.md` index
- [x] Create doc files for each architecture component
- [x] Verify all cross-reference links resolve

---

## Technical Decisions

1. **Decision**: kebab-case filenames
   - **Reason**: Consistent markdown convention, URL-friendly.
   - **Alternatives Considered**: PascalCase — rejected as less conventional for docs.

2. **Decision**: Single `README.md` index, manually maintained
   - **Reason**: Small file count, no tooling dependency.
   - **Alternatives Considered**: Auto-generated index — over-engineered for this scale.

3. **Decision**: Each doc is self-contained
   - **Reason**: Readers should not need to open multiple files to understand a component.
   - **Alternatives Considered**: Split files — rejected as over-fragmentation.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Broken cross-references | Medium | Low | Link audit as verification step |
| Mermaid rendering issues | Low | Medium | Spot-check in Mermaid-compatible viewer |

---

## References

- Spec: `./spec.md`
