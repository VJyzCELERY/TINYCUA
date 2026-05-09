# Skill: review-log

# Skill: Review Logging

## Purpose

Archive a completed review cycle into the permanent review log. Each review cycle becomes an entry in `./reviews/log/REVIEW_{branch}.md`, delimited by `[REVIEW_{ID}_START]` / `[REVIEW_{ID}_END]`.

## Prerequisites

- A completed review report at `./reviews/REVIEW_{branch}.md`
- All findings must be addressed, invalid, or deferred (no OPEN statuses)

## Execution

### Step 1: Read the review report

Read `./reviews/REVIEW_{branch}.md` and extract:

- **Scope** from header (`**Scope**: ...`)
- **All findings** that have status ADDRESSED, INVALID, or DEFERRED
- Skip any findings with status OPEN

### Step 2: Determine log path and next entry ID

```bash
# Get next entry ID
uv run python .agents/scripts/review-log.py --next-id
```

The log path is always `./reviews/log/REVIEW_{branch}.md`.

### Step 3: Generate the entry

Use `.agents/templates/REVIEW_LOG-template.md` as reference.

Each entry format:

```
[REVIEW_{ID}_START]
---
**Review Date**: YYYY-MM-DD
**Scope**: {scope}
**Cycle**: {ID}
**Total Findings**: N | **Resolved**: N | **Deferred**: N | **Invalid**: N
---
### F-001: Title
- **Severity**: high | **Category**: correctness
- **Status**: addressed
- **Problem**: Description
- **Validation**: How validated
- **Resolution**: What was done
- **Reasoning**: Why this fix
---
[REVIEW_{ID}_END]
```

### Step 4: Append to log

- If `./reviews/log/REVIEW_{branch}.md` doesn't exist, create with `# Review Log: {branch}` header
- Append the new entry at the end

### Step 5: Validate

```bash
uv run python .agents/scripts/review-log.py --validate ./reviews/log/REVIEW_{branch}.md
```

### Step 6: Confirm

Report back:
- Log file path: `./reviews/log/REVIEW_{branch}.md`
- Entry ID: `REVIEW_{ID}`
- Summary: N findings (X addressed, Y deferred, Z invalid)

## Common Pitfalls

- Do NOT log OPEN findings — they must be resolved first
- Do NOT modify existing entries — the log is append-only
- Do NOT delete the review report after logging — it stays in `./reviews/`
- If the review has zero non-OPEN findings, skip logging entirely
