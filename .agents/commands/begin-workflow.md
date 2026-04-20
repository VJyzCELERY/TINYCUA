---
description: Automates the complete specs implementation process with planning, implementation, and review loop
subtask: true
---

Automate the complete specs implementation process: planning → implementation → review loop → cleanup.

**Target Directory**: $1 (directory containing spec.md and design.md)
**Additional Context (Optional)**: $2 (any additional context or priorities)

## Overview

This command runs a complete implementation workflow:
1. Planning phase (create implementation-plan.md and task.md)
2. Implementation phase (execute the plan)
3. Review loop (review → validate → fix → repeat until clean)
4. Cleanup phase (archive resolved reviews)

## Instructions

### Phase 1: Planning

1. Read the spec.md and design.md files in `$1`
2. Create implementation-plan.md following the template at `~/.config/opencode/templates/implementation-plan.md`
3. Create task.md following the template at `~/.config/opencode/templates/task.md`

### Phase 2: Implementation

4. Read implementation-plan.md and task.md
5. Execute each task in order using TDD:
   - Write tests first
   - Implement code to pass tests
   - Run tests to verify
6. Update task.md as tasks are completed

### Phase 3: Review Loop

Enter a loop that continues until no issues are found:

**Step 3a: Review**
- Run `/review-project $1` with focus on code quality and spec compliance
- Scope the review to what's been implemented (don't review unrelated code)

**Step 3b: Validate**
- Run `/validate-review` on the review file
- Check if there are any OPEN findings

**Step 3c: If OPEN issues exist → Fix**
- Run `/review-implement` to fix the open issues
- After fixing, return to Step 3a for a fresh review
- Continue loop until no OPEN issues

**Step 3d: If no OPEN issues → Exit loop**
- Proceed to Phase 4

### Phase 4: Cleanup

7. Run `/cleanup-review` to archive resolved reviews

## Workflow Summary

```
Planning → Implementation → Review Loop → Cleanup
                                      ↓
                              Review → Validate
                                      ↓
                               If OPEN: Fix → Repeat
                               If Clean: Exit → Cleanup
```

## Important

- Stay scoped to the spec - don't implement or review things outside the scope
- Run actual commands and tests - don't assume results
- Update task.md as tasks complete
- Keep the review scoped to what's implemented

Begin by reading spec.md and design.md, then proceed through each phase.