---
description: Full review validation pipeline — clarifies vague findings, then verifies each one
subtask: true
---

Full review validation: first clarify vague findings, then verify each one's status.

> Load skill: review-core (for the full validation pipeline)

**Query**: $1 (optional natural language query, focus, or explicit review file path. If not an explicit review path, default to `./reviews/REVIEW_{normalized_branch}.md`.)
**Focus Area (Optional)**: $2 (validate only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, validate ALL OPEN findings.

## Pre-Flight

Before running, load the relevant skill and run the review pre-flight:

> Load _common-preflight.md

```bash
BRANCH=$(git branch --show-current)
NORMALIZED_BRANCH=${BRANCH//\//_}
REVIEW_FILE="./reviews/REVIEW_${NORMALIZED_BRANCH}.md"
uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"
```

If it exits non-zero, read `.agents/scripts/preflight-review.py` and inspect its `<EOF_DESC>` usage block to recover.

If local is behind remote, sync first. Use fast-forward pull when possible. If the remote rebased/diverged, create a backup branch for local commits and stash dirty work before resetting to upstream. If the review commit range is stale, continue: `review-validate` updates the report by clarifying/verifying against the latest commit.

---

## Cross-Reference Review Log

Before validating, check if a review log exists for this branch:

```bash
BRANCH=$(git branch --show-current)
LOG_PATH="./reviews/log/REVIEW_${BRANCH//\//_}.md"
if [ -f "$LOG_PATH" ]; then
    echo "Review log exists: $LOG_PATH"
fi
```

If the log exists, read it and cross-reference:
- **Previously deferred items**: If any deferred items reappear in this review, flag them for re-validation
- **Previously addressed items**: If any addressed items reappear, flag them — they may have regressed
- Note prior cycle findings in the clarify output to give context

---

## Role

`review-validate` runs the complete validation pipeline in two phases:

1. **Clarify** (delegates to `/review-clarify`): improve the precision of each finding
2. **Verify** (delegates to `/review-verify`): check if each finding is addressed, invalid, or still OPEN

---

## Instructions

Run both phases inline by default. Only delegate to subagents if the user explicitly says to use subagents.

### Phase 1: Clarify

Run `/review-clarify` directly:

> Run /review-clarify for "$REVIEW_FILE"

This improves finding descriptions, adds missing context, sharpens validation commands.

### Phase 2: Verify

Run `/review-verify` directly:

> Run /review-verify for "$REVIEW_FILE"

This runs each finding's validation command and determines its status (ADDRESSED, INVALID, or OPEN).

---

## Required Context

- Preflight: preflight-review.py
- Skills: review-core
- Rules: 004-review-standards.md
- Templates: none
- Mutates files: yes
- Mutates git history: no
- Mutates remote: no
- Requires user confirmation: no

## Important

- Always run clarify BEFORE verify — precise findings lead to accurate validation
- Stale review commit range is not a blocker. Validate against latest HEAD and refresh the report through `review-verify`.
- Do not ask where the review file is. Default to `./reviews/REVIEW_{normalized_branch}.md`.
- Run steps inline unless the user explicitly requests subagent delegation
- After verify returns, review the report to confirm all findings are properly statused
