# Implementation: [Feature Name]

[Brief description of what this implementation accomplishes. What problem does it solve? What user need does it address?]

## Context

- **Spec Reference**: [link to spec.md or description]
- **Design Reference**: [link to design.md or description]
- **Priority**: [P0|P1|P2|P3]
- **Estimated Effort**: [XS|S|M|L|XL]

## Proposed Changes

### [Module/Section Name]

#### [ACTION] [File Path]

- **[Description of change]**: [What specifically needs to be modified]
- **[Rationale]**: [Why this change is needed]

#### [Another ACTION] [File Path]

- **[Description of change]**
- **[Rationale]**

### [Another Module/Section Name]

#### [NEW] [new/file/path.ts]

- **[Description]**: [What new component or module needs to be created]
- **[Dependencies]**: [What other modules it depends on]

#### [MODIFY] [existing/file.ts]

- **[Description of change]**
- **[Breaking changes if any]**

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| [Component A] | Modify | [What changed] |
| [Component B] | New | [What's added] |
| [Component C] | Remove | [What's being removed] |

## Data Model Changes

```typescript
// New types or modified interfaces
interface [NewType] {
  field1: string;
  field2: number;
}
```

## API Changes

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/resource | Create new resource |
| GET | /api/v1/resource/:id | Get resource by ID |

### Modified Endpoints

| Method | Path | Change |
|--------|------|--------|
| GET | /api/v1/existing | Added new query parameter |

## Verification Plan

### Automated Tests

- [ ] Unit tests for [module/component]
- [ ] Integration tests for [feature]
- [ ] E2E tests for [user flow]

### Manual Verification

- [ ] [Verification step 1]
- [ ] [Verification step 2]

### Performance Considerations

- [ ] [Performance test or check]
- [ ] [Load test if applicable]

## Rollout Strategy

1. **Phase 1** ([description]): [what happens in this phase]
2. **Phase 2** ([description]): [what happens in this phase]
3. **Phase 3** ([description]): [what happens in this phase]

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| [package-name] | ^1.0.0 | [reason] |

### Internal Dependencies

- [ ] Depends on [other implementation]
- [ ] Blocks [other feature]

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| [Risk description] | [High/Medium/Low] | [Mitigation strategy] |

---

*Generated from spec.md and design.md*
*Last updated: [ISO Date]*