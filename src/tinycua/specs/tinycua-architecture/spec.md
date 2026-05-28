# Feature Specification: TINYCUA Architecture Documentation

**Status**: Implemented
**Created**: 2026-05-26
**Last Updated**: 2026-05-26
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Provide a coherent, single source-of-truth architecture documentation so contributors can understand TINYCUA's agent orchestration, data flow, and component responsibilities.
- **Gaps**: Architecture documentation has no formal home in the project. There is no established directory, index, or naming convention for architecture docs.
- **Non-Goals**: This spec does NOT cover implementation code, SDK APIs, CLI documentation, or non-architecture docs. Individual doc content may evolve — only the structure and coherence are in scope.
- **Constraints**: Files must live under `src/tinycua/docs/architecture/`. Must not duplicate existing `.agents/` skill/rule documentation.

---

## User Scenarios & Testing

### Primary Scenario

A developer wants to understand how TINYCUA orchestrates its agents. They navigate to `src/tinycua/docs/architecture/`, open the README index, and find links to each component's documentation with diagrams, inputs/outputs, flow, and design decisions.

### Acceptance Scenarios

1. **Given** the architecture docs directory exists, **When** a reader opens `README.md`, **Then** they see an index linking to all architecture docs with brief descriptions.
2. **Given** the architecture docs are in place, **When** reading any individual doc, **Then** the doc is self-contained and follows the category-specific structure defined in the design document.
3. **Given** all docs are cross-referenced, **When** a reader follows a "See also" link, **Then** it resolves to another doc within the same directory.

### Edge Cases

- Links to docs not yet written should use expected kebab-case filenames so the structure is predictable.
- Decision record docs (analyses of design tradeoffs) should be clearly distinguished from agent specification docs.

---

## Requirements

### Functional Requirements

- **FR-001**: An `README.md` index file MUST list all architecture docs with brief descriptions and links.
- **FR-002**: One file per architecture component (agent, process, or analysis), named in kebab-case.
- **FR-003**: Each agent doc MUST include sections for: Role, Inputs/Outputs, Internal Flow (Mermaid diagram), and Design Decisions.
- **FR-004**: All cross-references between docs MUST use relative `[display text](filename.md)` links.
- **FR-005**: Decision record docs MUST be labeled as such to distinguish from agent specifications.

### Key Entities

- **Architecture Doc File**: A markdown file describing one component. Named in kebab-case, stored under `src/tinycua/docs/architecture/`.
- **README Index**: The entry-point file listing and linking to all architecture docs.
- **Agent Doc**: Describes an LLM-powered agent with its role, flow, tools, and design decisions.
- **Non-Agent Process Doc**: Describes a deterministic component.
- **Decision Record**: A doc capturing design tradeoffs and resolved decisions.

---

## Success Criteria

- [x] **Complete coverage**: Every architecture component has a corresponding doc file.
- [x] **README index exists**: `README.md` lists all docs with descriptions and working links.
- [x] **Cross-references resolve**: All "See also" links between docs point to valid filenames.
- [x] **Kebab-case naming**: All filenames use kebab-case.
- [x] **No broken links**: Every `[text](file.md)` reference resolves to an existing file.
- [x] **Self-contained docs**: Each doc is independently readable.

---

## Testing Plan

### Unit Tests

Not applicable — documentation-only change.

### Manual Tests

- Verify `README.md` links resolve in a markdown viewer.
- Verify Mermaid diagrams render correctly.
- Verify all "See also" cross-reference links are valid relative paths.
- Spot-check 3 docs to confirm content quality: role, flow, design decisions present.

---

## Review Checklist

- [x] No implementation details
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
