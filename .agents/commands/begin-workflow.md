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

## Important Global Rule: Use `uv run` for Python

All subagents MUST be told to use `uv run --directory src/tinycua-sdk` for Python/pytest commands.
Bare `python` or `pytest` may import from the wrong worktree.

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
Use Task tool — review file is always at `./reviews/REVIEW-{name}.md`:
```
Task: Run /validate-review for ./reviews/REVIEW-{name}.md
```

**Step 3: If OPEN issues exist → Fix (Subagent 5)**
Use Task tool — review file is at `./reviews/REVIEW-{name}.md`:
```
Task: Run /review-implement for ./reviews/REVIEW-{name}.md
```

After fixing, return to Step 2 for re-validation.

**Step 4: If VALIDATE returns CLEAN (no OPEN issues) → Run FRESH Review (Subagent 6)**

IMPORTANT: When running the fresh review:
- Do NOT give the subagent any context about previous reviews or findings
- Do NOT mention what issues were found or fixed before
- Tell the subagent this is a completely fresh, independent review
- The subagent should approach it like they are reviewing for the first time
- Tell the subagent to use `uv run --directory src/tinycua-sdk` for all Python commands

Use Task tool:
```
Task: Run /review-project for $1 - perform a FRESH independent review. Do NOT use any context from previous reviews. Treat this as a brand new review and check for any remaining issues from scratch.
```

**Step 5: Check Fresh Review Result**
- If fresh review has ANY new issues → return to Step 2 (Validate → Implement → Validate → Fresh Review)
- If fresh review returns CLEAN (zero issues) → Exit Review Loop and proceed to Cleanup

### Phase 4: Cleanup (Subagent 7)

Use Task tool:
```
Task: Run /cleanup-review for ./reviews/
```

## Workflow Summary

```
Planning (Subagent 1) → Implementation (Subagent 2) → Review Loop → Cleanup

Review Loop:
  Review (Subagent 3) → writes to ./reviews/REVIEW-{name}.md
       ↓
  Validate (Subagent 4) → updates ./reviews/REVIEW-{name}.md → If OPEN: Fix (Subagent 5) → updates ./reviews/REVIEW-{name}.md → Validate (repeat until clean)
       ↓
  If CLEAN → Fresh Review (Subagent 6) - INDEPENDENT, no prior context
       ↓
  If NEW ISSUES → Return to Validate
  If CLEAN (zero issues) → Exit Loop → Cleanup
```

## Important

- Use Task tool to invoke each subagent for each phase
- Wait for each subagent to complete before proceeding
- After validation returns clean, ALWAYS run one more fresh review
- For FRESH review: explicitly tell subagent to be independent with no prior context
- Stay scoped to the spec - don't implement or review things outside the scope
- Run actual commands and tests - don't assume results
- Always instruct subagents to use `uv run --directory src/tinycua-sdk` for Python/pytest
- All review files live at `./reviews/REVIEW-{name}.md` — a consistent, predictable location

Begin by starting Subagent 1 for planning phase.
