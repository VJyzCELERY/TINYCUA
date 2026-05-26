# Design Document: TINYCUA Architecture Documentation

**Spec**: ./spec.md
**Status**: In Progress
**Last Updated**: 2026-05-26

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
| Agent Spec | Describes an LLM-powered agent (role, flow, tools, design decisions) | `query-analyst.md` |
| Process Spec | Describes a deterministic non-agent component | `information-passthrough.md` |
| Decision Record | Captures design tradeoffs and resolved decisions | `analysis-<topic>.md` |

### Fixed Files

- **`README.md`** — Must exist. Acts as the entry-point index, listing all architecture docs grouped by category with descriptions and links.

### Cross-Reference Convention

All internal links use relative `[display text](kebab-case-file.md)`:
```markdown
> **See also:** [Overview](overview.md), [Information Digestion](information-digestion.md)
```

---

## Data Model

### Doc File Structure

Each agent spec doc includes:
- `>` header with file path reference
- `## Role` section
- `## Inputs / Outputs` section
- `## Internal Flow` section (Mermaid diagram)
- `## Design Decisions` table
- `> **See also:**` cross-reference footer

### README Structure

```
# TINYCUA Architecture

## Agent Specifications
| File | Description |
| ...

## Non-Agent Processes
| File | Description |
| ...

## Design Decision Records
| File | Description |
| ...
```

---

## Implementation Phases

### Phase 1 — MVP

- [ ] Create `src/tinycua/docs/architecture/` directory
- [ ] Create `README.md` index
- [ ] Create doc files for each architecture component
- [ ] Verify all cross-reference links resolve

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
