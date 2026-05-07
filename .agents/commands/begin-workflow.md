---
description: Automates the complete specs implementation process using subagents for each phase
subtask: true
---

Automate the complete specs implementation process: planning → implementation → review loop → cleanup.

**Target Directory**: $1 (directory containing spec.md and design.md)
**Additional Context (Optional)**: $2 (any additional context or priorities)

## Orchestrator Role

The agent that executes this command is the **orchestrator**. You (the running agent) are the orchestrator — you use Task tool to delegate to subagents for each phase, but you own the loop, apply oversight rules, and make go/no-go decisions. Subagents are intentionally kept free of prior review context.

## Overview

This command runs a complete implementation workflow using subagents for each phase, with the orchestrator overseeing the entire process:
1. Planning phase (Subagent 1) → creates implementation-plan.md and task.md
2. Implementation phase (Subagent 2) → executes the plan
3. Review loop (Subagents 3-6+) → review → validate → fix → validate → fresh review → repeat until truly clean
4. Cleanup phase → archive resolved reviews

## Important Global Rule: Use `uv run` for Python

All subagents MUST `cd <subproject-dir> && uv run` for Python/pytest commands.
Bare `python` or `pytest` may import from the wrong worktree.

## Instructions

### Phase 1: Planning (Subagent 1)

Use Task tool to invoke a subagent with the implementation-plan command:
```
Task: Run /plan for $1
```

Wait for the subagent to complete and verify implementation-plan.md and task.md are created.

### Phase 2: Implementation (Subagent 2)

Use Task tool to invoke a subagent with the implement-plan command:
```
Task: Run /implement for $1
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
Task: Run /review-validate for ./reviews/REVIEW-{name}.md
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
- Tell the subagent to `cd <subproject-dir> && uv run` for all Python commands

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
Task: Run /review-cleanup for ./reviews/
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

## Review Loop Oversight Rules (Orchestrator Responsibilities)

The **orchestrator** (you — the agent executing this command) owns the loop and must apply these rules. The reviewer, validator, and fixer subagents are intentionally kept free of prior context to ensure fresh perspectives.

> **Rule of thumb**: The orchestrator says "no, we already fixed that" or "that's out of scope now" to prevent infinite loops. Subagents are useful idiots — they generate creative thoroughness that the orchestrator filters.

### 1. Bookkeep Review History

Maintain a running ledger of every finding across all cycles. For each new fresh review:

1. **Check each finding against the ledger**: has this exact issue been raised and addressed before?
2. **If yes → Invalidate**: mark it INVALID with a note: "Already addressed in cycle N — no regression detected."
3. **If no → Keep as OPEN**: the finding is genuinely new.

### 2. Handle Reopened Issues

A previously addressed finding may legitimately reopen:
- If **code has changed** since the fix (the fix was reverted or modified), treat as a valid new OPEN finding.
- If **code has NOT changed** since the fix, the reviewer is wrong — **invalidate**.
- Verification: `git diff <commit-where-fix-was-applied> -- <file>` to check for regressions.

### 3. Tighten Scope as Issues Shrink

As the loop progresses and findings become increasingly nitpicky (minor, info, suggestions), the orchestrator should tighten review scope to enable better termination:

- **First 1-2 cycles**: Full scope — all spec compliance, code quality, test coverage.
- **Cycles 3-4**: Narrow to spec compliance and correctness issues. Defer cosmetic/style suggestions.
- **Cycles 5+**: Only accept findings that represent **real bugs**, **spec violations**, or **test gaps that would let actual bugs through**. Reject pure style preferences, missing `__all__`, annotation preferences, naming nits, etc.

### 4. Orchestrator Validation Gate

After each fresh review, before passing findings to the validate-fix pipeline:

1. Run each finding through the ledger (rule 1).
2. Check for reopened issues with code diff verification (rule 2).
3. Assess severity against current cycle scope (rule 3).
4. Produce a filtered findings list — only genuinely new, in-scope, non-duplicate issues proceed to Step 2 (Validate).

This keeps the reviewer free to be creatively thorough while the orchestrator prevents infinite loops from diminishing-returns nitpicking.

## Important

- The **orchestrator** (the agent running this command) is responsible for applying the Review Loop Oversight Rules. Do NOT pass oversight context to subagents.
- Use Task tool to invoke each subagent for each phase
- Wait for each subagent to complete before proceeding
- After validation returns clean, ALWAYS run one more fresh review
- For FRESH review: explicitly tell subagent to be independent with no prior context — do NOT mention any previous findings or fixes
- The orchestrator filters and gates fresh review findings through the oversight rules before passing to validate
- Stay scoped to the spec - don't implement or review things outside the scope
- Run actual commands and tests - don't assume results
- Always instruct subagents to `cd <subproject-dir> && uv run` for Python/pytest
- All review files live at `./reviews/REVIEW-{name}.md` — a consistent, predictable location

Begin by starting Subagent 1 for planning phase.
