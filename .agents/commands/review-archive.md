---
description: Logs a completed review cycle then archives the review report
subtask: true
---

Log a completed review cycle and archive the report. Creates a log entry in `./reviews/log/REVIEW_{normalized_branch}.md`, then moves the report to `./reviews/archives/`.

> Load skill: review-archive (for archiving resolved reviews)

**Query**: $1 (optional natural language query or explicit review file path. If not an explicit review path, default to `./reviews/REVIEW_{normalized_branch}.md`.)

## Pre-Flight

> Load _common-preflight.md — verify the review file exists and check for staleness

If the local checkout is behind remote, sync to latest first. Use fast-forward pull when possible; for rebased/diverged remote state, create a backup branch for local commits and stash dirty work before resetting to upstream. If the review commit range is stale, run `/review-verify` first to update the local report against latest HEAD before archiving. Do not archive stale review state.

## Workflow

### Step 1: Create Log Entry

Log the review findings using the review-log script:

```bash
uv run python .agents/scripts/review-log.py --log-create "$REVIEW_FILE"
```

This extracts all ADDRESSED, INVALID, and DEFERRED findings (skips OPEN) and appends a new entry to `./reviews/log/REVIEW_{normalized_branch}.md`. The output includes the entry ID (e.g., `REVIEW_3`).

If the review has 0 findings (approved), the script creates a clean-review approval entry in
the log — containing "0 findings — Approved" metadata with proper entry ID and timestamps,
so no review cycle is ever lost to traceability.

### Step 2: Determine Entry ID

Parse the log entry ID from the script output, or get it directly:

```bash
ENTRY_ID=$(uv run python .agents/scripts/review-log.py --next-id)
ENTRY_ID=$((ENTRY_ID - 1))  # next-id returns the next ID, so subtract 1 for the one just created
```

### Step 3: Archive the Report

Move the review report to the archives directory with the log ID in the filename:

```bash
BRANCH=$(git branch --show-current)
NORMALIZED_BRANCH=${BRANCH//\//_}
ARCHIVE_DIR="./reviews/archives"
mkdir -p "$ARCHIVE_DIR"
REVIEW_NAME="REVIEW_${NORMALIZED_BRANCH}"
mv "$REVIEW_FILE" "$ARCHIVE_DIR/${REVIEW_NAME}_${ENTRY_ID}.md"
```

### Step 4: Validate Log

```bash
uv run python .agents/scripts/review-log.py --validate "./reviews/log/REVIEW_${NORMALIZED_BRANCH}.md"
```

### Step 5: Confirm

Report:
- Log entry: `./reviews/log/REVIEW_{normalized_branch}.md` (entry REVIEW_{ID})
- Archived report: `./reviews/archives/REVIEW_{normalized_branch}_{ID}.md`
- Summary: N findings logged (X addressed, Y deferred, Z invalid)

> Use _common-closing-gate.md before final response.

## Required Context

- Preflight: preflight-review.py
- Skills: review-archive
- Rules: none
- Templates: none
- Mutates files: yes
- Mutates git history: no
- Mutates remote: no
- Requires user confirmation: no

## Important
- Only archive reviews where findings are ADDRESSED, INVALID, or DEFERRED — never with OPEN findings
- The log is append-only — never modify existing entries
- The archive preserves the original report with the log ID for traceability
- Archives directory is at `./reviews/archives/`, not in the main reviews directory
