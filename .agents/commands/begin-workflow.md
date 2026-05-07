---
description: Automates the complete specs implementation process using subagents for each phase
subtask: true
---

Automate the complete specs implementation process: planning → implementation → review loop → cleanup.

**Target Directory**: $1 (directory containing spec.md and design.md)
**Additional Context (Optional)**: $2 (any additional context or priorities)

---

## Workflow-Orchestrator Role

The agent that executes this command is the **workflow-orchestrator**. You (the running agent) are the workflow-orchestrator — you use the Task tool to delegate to **fresh subagents** for every single step. You own the loop, apply oversight rules, and make go/no-go decisions.

### Critical Rule: Every Step Uses a Fresh Subagent with Clean Context

**Every step in this workflow uses a dedicated subagent that starts with zero context from any prior step.** Subagents are intentionally kept free of prior context to ensure fresh perspectives. This applies to:

- `/plan` → Subagent 1
- `/implement` → Subagent 2
- `/review-report` → Subagent 3, 6, 9, ...
- `/review-validate` → Subagent 4, 7, 10, ...
- `/review-implement` → Subagent 5, 8, 11, ...
- `/review-cleanup` → Subagent N

Each subagent is a clean, independent invocation. Do NOT pass prior findings, fix history, or any context between them. The workflow-orchestrator alone maintains the bookkeeping.

---

## Overview

```
Planning (Subagent 1) → Implementation (Subagent 2) → Review Loop → Cleanup

Review Loop:
  Review-report (Subagent 3)
       ↓
  Review-validate (Subagent 4) → If OPEN: Review-implement (Subagent 5) → Review-validate (Subagent 6) → repeat
       ↓
  If CLEAN → Fresh Review-report (Subagent 7) ← independent, zero prior context
       ↓
  If NEW ISSUES → Return to Validate
  If CLEAN (zero issues) → Exit Loop → Review-cleanup (Subagent N)
```

---

## Important Global Rule: Use `uv run` for Python

All subagents MUST `cd <subproject-dir> && uv run` for Python/pytest commands.
Bare `python` or `pytest` may import from the wrong worktree.

---

## Instructions

### Phase 1: Planning (Subagent 1)

Use Task tool to invoke a fresh subagent:

```
Task: Run /plan for $1
```

Wait for the subagent to complete and verify implementation-plan.md and task.md are created.

### Phase 2: Implementation (Subagent 2)

Use Task tool to invoke a fresh subagent:

```
Task: Run /implement for $1
```

Wait for the subagent to complete and verify tasks are marked complete in task.md.

### Phase 3: Review Loop

Enter a loop that continues until truly clean (no issues found in a FRESH review):

**Step 1: Review-report (Subagent 3)**

Use Task tool to invoke a fresh subagent:
```
Task: Run /review-report for $1 with focus on code quality and spec compliance
```

**Step 2: Review-validate (Subagent 4)**

Use Task tool — review file is always at `./reviews/REVIEW-{name}.md`:
```
Task: Run /review-validate for ./reviews/REVIEW-{name}.md
```

**Step 3: If OPEN issues exist → Review-implement (Subagent 5)**

Use Task tool:
```
Task: Run /review-implement for ./reviews/REVIEW-{name}.md
```

After fixing, return to Step 2 for re-validation (this uses a NEW subagent — Subagent 6, then 8, then 10, etc.).

**Step 4: If VALIDATE returns CLEAN (no OPEN issues) → Run FRESH Review-report (Subagent N)**

This MUST be a fresh, independent review. Do NOT give the subagent any context about previous reviews or findings:
```
Task: Run /review-report for $1 - perform a FRESH independent review. Do NOT use any context from previous reviews. Treat this as a brand new review and check for any remaining issues from scratch.
```

**Step 5: Check Fresh Review Result**
- If fresh review has ANY new issues → return to Step 2 (Validate → Implement → Validate → Fresh Review)
- If fresh review returns CLEAN (zero issues) → Exit Review Loop and proceed to Cleanup

### Phase 4: Review-cleanup (Subagent N)

Use Task tool to invoke a fresh subagent:
```
Task: Run /review-cleanup for ./reviews/
```

---

## Workflow Summary (Subagent Sequence)

```
Subagent 1:  /plan
Subagent 2:  /implement
  ── Review Loop ──
Subagent 3:  /review-report                               (initial review)
Subagent 4:  /review-validate                             (validate findings)
Subagent 5:  /review-implement                            (fix open issues)
Subagent 6:  /review-validate                             (re-validate after fix)
             ...repeat 4-6 as needed...
Subagent N:  /review-report                               (fresh, independent review)
             if issues → back to Subagent N+1 (validate)
             if clean → proceed to cleanup
Subagent N:  /review-cleanup                              (archive resolved reviews)
```

---

## Review Loop Oversight Rules (Workflow-Orchestrator Responsibilities)

The **workflow-orchestrator** (you) owns the loop and must apply these rules. The subagents are intentionally kept free of prior context to ensure fresh perspectives.

> **Rule of thumb**: The workflow-orchestrator says "no, we already fixed that" or "that's out of scope now" to prevent infinite loops. Subagents are useful idiots — they generate creative thoroughness that the workflow-orchestrator filters.

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

As the loop progresses and findings become increasingly nitpicky, the orchestrator should tighten review scope:

- **First 1-2 cycles**: Full scope — all spec compliance, code quality, test coverage.
- **Cycles 3-4**: Narrow to spec compliance and correctness issues. Defer cosmetic/style suggestions.
- **Cycles 5+**: Only accept findings that represent **real bugs**, **spec violations**, or **test gaps that would let actual bugs through**.

### 4. Workflow-Orchestrator Validation Gate

After each fresh review, before passing findings to the validate-fix pipeline:

1. Run each finding through the ledger (rule 1).
2. Check for reopened issues with code diff verification (rule 2).
3. Assess severity against current cycle scope (rule 3).
4. Produce a filtered findings list — only genuinely new, in-scope, non-duplicate issues proceed to validation.

---

## Important

- The **workflow-orchestrator** (you) is responsible for applying the Review Loop Oversight Rules. Do NOT pass oversight context to subagents.
- Use Task tool to invoke each subagent for each phase.
- Wait for each subagent to complete before proceeding.
- After validation returns clean, ALWAYS run one more fresh review.
- For FRESH review: explicitly tell subagent to be independent with no prior context.
- The orchestrator filters and gates fresh review findings through the oversight rules before passing to validate.
- Stay scoped to the spec — don't implement or review things outside the scope.
- Run actual commands and tests — don't assume results.
- Always instruct subagents to `cd <subproject-dir> && uv run` for Python/pytest.
- Always instruct subagents to read the relevant rules from `.agents/docs/` first (both `agents/` and `project_rules/`), then check `.agents/templates/` before generating documents — rules define conventions, templates define structure.
- All review files live at `./reviews/REVIEW-{name}.md` — a consistent, predictable location.

Begin by starting Subagent 1 for the planning phase.
