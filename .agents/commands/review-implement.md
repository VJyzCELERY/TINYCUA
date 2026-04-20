---
description: Implements fixes according to review findings
subtask: true
---

Implement fixes based on review findings.

**Review File**: $1 (path to the REVIEW-{name}.md file)

## Instructions

1. **Read the Review**: Use the Read tool to load the review report
2. **Identify OPEN Findings**: Find all findings with status "OPEN"
3. **Review the Suggested Fix**: Read the "Suggested Fix" for each finding
4. **Implement Fixes**: For each OPEN finding:
   - Go to the location specified
   - Implement the fix as suggested
   - Run any validation commands provided
5. **Update Review Status**: After fixing each issue, update the finding status to "ADDRESSED"
6. **Update Validation Log**: Add entry to the Validation Log section

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

Begin by reading the review file and implementing fixes for all OPEN findings.