---
description: Automates the complete specs implementation process using subagents for each phase
subtask: true
---

Automate the complete specs implementation process: planning → implementation → review loop → cleanup.

**Target Directory**: $1 (directory containing spec.md and design.md)
**Additional Context (Optional)**: $2 (any additional context or priorities)

## Overview

This command runs a complete implementation workflow using subagents for each phase:
1. Planning phase (Subagent 1) → creates implementation-plan.md and task.md
2. Implementation phase (Subagent 2) → executes the plan
3. Review loop (Subagents 3-6+) → review → validate → fix → validate → fresh review → repeat until truly clean
4. Cleanup phase → archive resolved reviews

## Instructions

### Phase 1: Planning (Subagent 1)

Use Task tool to invoke a subagent with the implementation-plan command:
```
Task: Run /implementation-plan for $1
```

Wait for the subagent to complete and verify implementation-plan.md and task.md are created.

### Phase 2: Implementation (Subagent 2)

Use Task tool to invoke a subagent with the implement-plan command:
```
Task: Run /implement-plan for $1
```

Wait for the subagent to complete and verify tasks are marked complete in task.md.

### Phase 3: Review Loop

Enter a loop that continues until truly clean (no issues found in a FRESH review):

**Step 1: Review (Subagent 3)**
Use Task tool:
```
Task: Run /review-project for $1 with focus on code quality and spec compliance
```

**Step 2: Validate (Subagent 4)**
Use Task tool:
```
Task: Run /validate-review for the review file in $1/reviews/
```

**Step 3: If OPEN issues exist → Fix (Subagent 5)**
Use Task tool:
```
Task: Run /review-implement for the review file in $1/reviews/
```

After fixing, return to Step 2 for re-validation.

**Step 4: If VALIDATE returns CLEAN (no OPEN issues) → Run FRESH Review (Subagent 6)**
Use Task tool:
```
Task: Run /review-project for $1 - do a fresh review to check for any remaining issues
```

**Step 5: Check Fresh Review Result**
- If fresh review has NEW issues → return to Step 2 (Validate → Implement → Validate → Fresh Review)
- If fresh review returns CLEAN (no issues) → Exit Review Loop and proceed to Cleanup

### Phase 4: Cleanup (Subagent 7)

Use Task tool:
```
Task: Run /cleanup-review for $1/reviews/ or .agents/reviews/
```

## Workflow Summary

```
Planning (Subagent 1) → Implementation (Subagent 2) → Review Loop → Cleanup

Review Loop:
  Review (Subagent 3)
       ↓
  Validate (Subagent 4) → If OPEN: Fix (Subagent 5) → Validate (repeat until clean)
       ↓
  If CLEAN → Fresh Review (Subagent 6)
       ↓
  If NEW ISSUES → Return to Validate
  If CLEAN → Exit Loop → Cleanup
```

## Important

- Use Task tool to invoke each subagent for each phase
- Wait for each subagent to complete before proceeding
- After validation returns clean, ALWAYS run one more fresh review to ensure truly clean
- Stay scoped to the spec - don't implement or review things outside the scope
- Run actual commands and tests - don't assume results

Begin by starting Subagent 1 for planning phase.