---
description: Full review validation pipeline — clarifies vague findings, then verifies each one
subtask: true
---

Full review validation: first clarify vague findings, then verify each one's status.

**Query**: $1 (natural language query or review file path, e.g., "validate the findings in reviews/REVIEW-foo.md" or simply "reviews/REVIEW-foo.md")
**Focus Area (Optional)**: $2 (validate only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, validate ALL OPEN findings.

---

## Role

`review-validate` runs the complete validation pipeline in two phases:

1. **Clarify** (delegates to `/review-clarify`): improve the precision of each finding
2. **Verify** (delegates to `/review-verify`): check if each finding is addressed, invalid, or still OPEN

---

## Instructions

Use Task tool to invoke subagents for each phase:

### Phase 1: Clarify (Subagent 1)

```
Task: Run /review-clarify for $1
```

This improves finding descriptions, adds missing context, sharpens validation commands.

### Phase 2: Verify (Subagent 2)

```
Task: Run /review-verify for $1
```

This runs each finding's validation command and determines its status (ADDRESSED, INVALID, or OPEN).

---

## Important

- Always run clarify BEFORE verify — precise findings lead to accurate validation
- Use a fresh subagent for each phase to keep context clean
- After verify returns, review the report to confirm all findings are properly statused
