---
name: review-loop
description: Orchestrate review-until-clean cycles with fresh subagents per step
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/review-loop.md
---

# Skill: review-loop — Orchestrate Review-Until-Clean Cycles

## Purpose

Run the full review loop: review-report → review-validate → review-implement → fresh review → repeat until clean → review-cleanup. You are the workflow-orchestrator; delegate each step to a fresh subagent.

## Prerequisites

- Load skill: preflight (for preflight-review.py)
- Load skill: gh-pr-management (for PR context)

## Execution

1. Run preflight: `uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"`
2. Delegate `/review-report` → wait → read report
3. Delegate `/review-validate` → if OPEN issues exist → delegate `/review-implement` → return to step 3
4. If VALIDATE returns CLEAN → run FRESH `/review-report` (new subagent, zero context)
5. If fresh review has issues → return to step 3 for re-validation
6. If fresh review CLEAN → exit loop → delegate `/review-cleanup`

## Common Pitfalls

- Each step gets a fresh subagent with zero prior context
- Do NOT fix code yourself — always delegate to subagents
- At least 4 full-scope cycles before tightening
- After validation returns clean, ALWAYS run one more fresh review
- Subagents must read AGENTS.md first and load relevant skills
