---
description: Implements fixes according to review findings — DOES NOT update the review report
subtask: true
---

Implement fixes based on review findings. This command ONLY modifies source code — it does NOT update the review report. Status updates are handled by `review-verify` and `review-validate`.

> Load skill: review-implement (for applying fixes from findings)

**Query**: $1 (optional natural language query, focus, or explicit review file path. If not an explicit review path, default to `./reviews/REVIEW_{normalized_branch}.md`.)
**Focus Area (Optional)**: $2 (implement only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, implement fixes for ALL OPEN findings.

---

## Pre-Flight: Implement Preflight

> Load _common-preflight.md

Run the implement preflight to detect available reviews and check staleness:

```bash
# Default review file for this branch:
BRANCH=$(git branch --show-current)
NORMALIZED_BRANCH=${BRANCH//\//_}
REVIEW_FILE="./reviews/REVIEW_${NORMALIZED_BRANCH}.md"
uv run python .agents/scripts/preflight-review.py --implement --review-file "$REVIEW_FILE"
```

The preflight will:
- **File mode**: Check if the default review exists, verify commit range staleness and branch match.

**If the preflight reports a stale review, STOP. Do not implement stale findings. Tell the user directly: "This review is stale; please run `/review-verify` first so the report is validated against the latest commit."** Do not automatically run `review-verify` from this command. If the local checkout itself is behind remote, sync to latest first (fast-forward pull when possible; for rebased/diverged remote state, create a backup branch for local commits and stash dirty work before resetting to upstream), then re-run the implement preflight; if the review is still stale, stop with the same recommendation.

---

## Critical Rule

**DO NOT update the review report.** This command is purely for implementation. The review report is read-only input. Status updates (ADDRESSED, INVALID, OPEN) are handled by `review-verify` and `review-validate`.

---

## Instructions

1. **Read the Review**: Load `$REVIEW_FILE` from `./reviews/REVIEW_{normalized_branch}.md`. If it does not exist, stop and report that exact missing path; do not ask where the review file is.
2. **Filter Findings**: If `$2` is provided, only fix those findings
3. **Identify OPEN Findings**: Find all findings with status "OPEN"
4. **Review the Suggested Fix**: Read the "Suggested Fix" for each finding
5. **Implement Fixes**: For each OPEN finding:
   - Go to the location specified
   - Implement the fix as suggested
   - Run validation commands to confirm (use `uv run` for Python)
6. **Report**: Tell the user which findings were fixed and that `review-validate` should be run next

## Required Context

- Preflight: preflight-review.py (--implement mode)
- Skills: review-implement
- Rules: 002-code-standards.md
- Templates: none
- Mutates files: yes
- Mutates git history: no
- Mutates remote: no
- Requires user confirmation: no (stale review stops and recommends `/review-verify`)

## Important

- ONLY modify source code — do NOT touch the review report
- Never implement a stale review. Recommend `/review-verify` and stop instead.
- After fixing, run validation commands to confirm the fix works
- If validation fails, note what's still wrong
- Do not ask where the review file is. Default to `./reviews/REVIEW_{normalized_branch}.md`.
