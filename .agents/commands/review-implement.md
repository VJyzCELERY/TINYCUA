---
description: Implements fixes according to review findings
subtask: true
---

Implement fixes based on review findings.

**Review File**: $1 (path to the REVIEW-{name}.md file)
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
   - Run any validation commands provided
6. **Update Review Status**: After fixing each issue, update the finding status to "ADDRESSED"
7. **Update Validation Log**: Add entry to the Validation Log section

## Finding Status Definitions
- **ADDRESSED**: Issue has been fixed
- **INVALID**: Issue no longer exists or is no longer relevant
- **OPEN**: Issue still exists and needs fixing

## Validation
- After implementing each fix, run the "How to Test/Validate" command to verify
- If validation passes, mark as ADDRESSED
- If validation fails, note the issue and keep as OPEN

## Important
- Only fix OPEN findings - don't modify ADDRESSED or INVALID ones
- Run validation commands after each fix
- Update the review file with new status after each fix

Begin by reading the review file and implementing fixes for OPEN findings.