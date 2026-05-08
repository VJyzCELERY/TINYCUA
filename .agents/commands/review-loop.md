---
description: Runs the review loop independently: review → validate → fix → fresh review → cleanup
subtask: true
---

Run the review loop independently: review-report → review-validate → review-implement → fresh review → repeat until clean → review-cleanup.

> Load skill: review-loop (for orchestrating review cycles)

**Query**: $1 (natural language query — specify what to review, e.g., "review the changes in src/tinycua-sdk" or simply "src/my-subproject/")
**Review Name**: $2 (optional — defaults to directory name from query)
**Unscoped (Optional)**: $3 (set to "unscoped" to bypass branch diff scoping)

## Initial Questions

**Use the question/ask tool to ask these (priority). Only write inline if your harness has no such tool.**

1. **Scope tightening**: "Do you want to tighten the review scope as iterations progress (narrow to critical issues after 3-4 cycles), or keep every cycle as a full fresh review?" Default is tighten if not specified.
2. **Any other clarifications**: If the query is ambiguous, ask for specifics.

Once answered, the rest of the loop runs fully automated.

---

## Pre-Flight

Before starting the loop, run the review pre-flight:

```bash
uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"
```

---


## Workflow-Orchestrator Role

The agent that executes this command is the **workflow-orchestrator**. You delegate to **fresh subagents** for every single step. You own the loop, apply oversight rules, and make go/no-go decisions.

### Every Step Uses a Fresh Subagent

- `/review-report` → Subagent 1, 4, 7, ...
- `/review-validate` → Subagent 2, 5, 8, ...
- `/review-implement` → Subagent 3, 6, 9, ...
- `/review-cleanup` → Subagent N

---

## Important Global Rule: Use `uv run` for Python

All subagents MUST `cd <subproject-dir> && uv run` for Python/pytest commands.
Bare `python` or `pytest` may import from the wrong worktree.

---

## Instructions

Enter a loop that continues until truly clean (no issues found in a FRESH review):

**Step 1: Review-report (Subagent 1)**

Delegate to a fresh subagent:

> Run /review-report for $1 with focus on code quality and spec compliance — read the PR body and title first, adjust scope accordingly, and check PR body/title compliance against specs

The review file is written to `./reviews/REVIEW-{name}.md`.

**Step 2: Review-validate (Subagent 2)**

Delegate:

> Run /review-validate for ./reviews/REVIEW-{name}.md

**Step 3: If OPEN issues exist → Review-implement (Subagent 3)**

Delegate:

> Run /review-implement for ./reviews/REVIEW-{name}.md

After fixing, return to Step 2 for re-validation (new subagent each time).

**Step 4: If VALIDATE returns CLEAN → Run FRESH Review-report (Subagent N)**

This MUST be a fresh, independent review. No prior context:

> Run /review-report for $1 - perform a FRESH independent review. Do NOT use any context from previous reviews. Treat this as a brand new review and check for any remaining issues from scratch — also read the PR body and title, adjust scope, and check PR body/title compliance

**Step 5: Check Fresh Review Result**
- If fresh review has ANY new issues → return to Step 2
- If fresh review returns CLEAN (zero issues) → Exit Review Loop → proceed to Cleanup

**Step 6: Review-cleanup (Subagent N)**

> Run /review-cleanup for ./reviews/

---

## Review Loop Oversight Rules (Workflow-Orchestrator)

### 1. Bookkeep Review History

Maintain a running ledger of every finding across all cycles. For each new fresh review:

1. Check each finding against the ledger — has this been raised and addressed before?
2. If yes → Invalidate: mark it INVALID with note: "Already addressed in cycle N"
3. If no → Keep as OPEN

**Do NOT invalidate simply because a finding looks similar or overlaps.** Only invalidate if the exact same issue (same file, same line, same description) was previously addressed.

### 2. Handle Reopened Issues

- If **code has changed** since the fix, treat as valid new OPEN finding
- If **code has NOT changed**, the reviewer is wrong — invalidate

### 3. Tighten Scope as Issues Shrink

Bias toward keeping scope wide:

- **First 4 cycles**: Full scope — spec compliance, code quality, test coverage
- **Cycles 5-8**: Narrow to spec compliance and correctness issues
- **Cycles 9+**: Only real bugs, spec violations, or test gaps

### 4. Orchestrator Validation Gate

After each fresh review, before passing to validate-fix: filter through ledger, check reopen status, assess severity against current cycle scope. **Pass all remaining findings through** — do NOT proactively filter or dismiss. Let review-validate and review-verify make the final determination. The orchestrator only removes true duplicates (exact same finding from prior cycle) and out-of-scope items (findings about code not in the diff).

---

## Important

- Delegate each step to a fresh subagent
- Wait for each subagent to complete before proceeding
- After validation returns clean, ALWAYS run one more fresh review
- **Do NOT fix code yourself** — always delegate implementation to subagents via review-implement. The orchestrator owns the loop, not the code
- For FRESH review: explicitly tell subagent to be independent with no prior context
- Stay scoped to the target directory
- Run actual commands and tests — don't assume results
- Always instruct subagents to read this AGENTS.md file first — they start with zero context and won't know the rules otherwise
- Always instruct subagents to load the relevant skill (e.g., `gh-pr-management`, `preflight`) before running tools — list available skills with `ls .agents/skills/` if unsure
- Always instruct subagents to `cd <subproject-dir> && uv run` for Python/pytest
- When delegating review-report, instruct the subagent to read the PR body and title to understand scope and check PR body/title compliance
- All review files live at `./reviews/REVIEW-{name}.md`
