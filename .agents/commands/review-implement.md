---
description: Implements fixes according to review findings and updates report statuses
subtask: true
---

Implement fixes based on review findings and update the review report statuses.

**Review File**: $1 (path to the REVIEW-{name}.md file — look in `./reviews/` first if not found)
**Focus Area (Optional)**: $2 (implement only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, implement fixes for ALL OPEN findings.

## Instructions

1. **Read the Review**: Use the Read tool to load the review report
2. **Filter Findings**: If $2 is provided, only fix those findings
3. **Identify OPEN Findings**: Find all findings with status "OPEN" (or filtered set)
4. **Review the Suggested Fix**: Read the "Suggested Fix" for each finding
5. **Implement Fixes**: For each OPEN finding:
   - Go to the location specified
   - Implement the fix as suggested
   - Run any validation commands provided (use `uv run` for Python)
6. **SHOULD Update Review Statuses**: After fixing each issue, update the finding status to "ADDRESSED" or "INVALID" in the review file
7. **SHOULD Update Validation Log**: Add entry to the Validation Log section documenting what was fixed

## Python Usage

This project uses `uv` for Python environment management. Always use `uv run`:

```bash
# ✅ Correct
cd <subproject-dir> && uv run python -c "..."
cd <subproject-dir> && uv run pytest tests/

# ❌ Wrong
python ...
pytest ...
```

## Finding Status Definitions
- **ADDRESSED**: Issue has been fixed
- **INVALID**: Issue no longer exists or is no longer relevant
- **OPEN**: Issue still exists and needs fixing

## Validation
- After implementing each fix, run the "How to Test/Validate" command to verify
- If validation passes, mark as ADDRESSED
- If validation fails, note the issue and keep as OPEN

## Important
- SHOULD update the review file with new statuses after each fix
- Only fix OPEN findings - don't modify ADDRESSED or INVALID ones
- Run validation commands after each fix
- Do NOT rewrite finding content — only update statuses and append to the Validation Log

Begin by reading the review file and implementing fixes for OPEN findings.
