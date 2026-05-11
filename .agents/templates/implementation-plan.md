# Implementation: [Feature Name]

[Brief description of what this implementation accomplishes. What problem does it solve? What user need does it address?]

## Context

- **Spec Reference**: [link to spec.md or description]
- **Design Reference**: [link to design.md or description]
- **Priority**: [P0|P1|P2|P3]
- **Estimated Effort**: [XS|S|M|L|XL]

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: [path/to/test_file.py]
"""Integration tests for [feature name]."""


def test_[scenario_under_test]:
    """[Describe what this test verifies]"""
    # Arrange
    [setup code]
    # Act
    [action code]
    # Assert
    [assertion code]


def test_[another_scenario]:
    """[Describe]"""
    # Arrange
    [setup]
    # Act
    [action]
    # Assert
    [expected outcome]
```

### Key Test Scenarios

- [ ] **Scenario 1**: [description of what the test covers and why it's the primary success criterion]
- [ ] **Scenario 2**: [description]
- [ ] **Edge case**: [description]

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for [module/component] — test error handling, edge cases, fallbacks
- [ ] Existing test suite — confirm no regressions: `uv run pytest`

### Manual Verification

- [ ] [Verification step 1]
- [ ] [Verification step 2]

### Performance Considerations

- [ ] [Performance test or check]
- [ ] [Load test if applicable]

## Proposed Changes

### [Module/Section Name]

#### [ACTION] [File Path]

- **[Description of change]**: [What specifically needs to be modified]
- **[Rationale]**: [Why this change is needed]

#### [Another ACTION] [File Path]

- **[Description of change]**
- **[Rationale]**

### [Another Module/Section Name]

#### [NEW] [new/file/path.py]

- **[Description]**: [What new component or module needs to be created]
- **[Dependencies]**: [What other modules it depends on]

#### [MODIFY] [existing/file.py]

- **[Description of change]**
- **[Breaking changes if any]**

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| [Component A] | Modify | [What changed] |
| [Component B] | New | [What's added] |
| [Component C] | Remove | [What's being removed] |

## Data Model Changes

```python
# New types or modified interfaces
[NewType]:
    field1: str
    field2: int
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
