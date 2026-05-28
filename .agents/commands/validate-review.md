---
description: Validates findings from a previous review and updates the report
subtask: true
---

Validate findings from a previous review and update the report with validation results.

**Review File**: $1 (path to the REVIEW-{name}.md file)
**Focus Area (Optional)**: $2 (validate only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, validate ALL OPEN findings.

## Instructions

1. **Read the Review**: Use the Read tool to load and analyze the review report
2. **Filter Findings**: If $2 is provided, only validate those findings
3. **Validate Each Finding**: For each OPEN finding:
   - Execute the "How to Test/Validate" command provided in the finding
   - Determine if the issue has been ADDRESSED, INVALID, or remains OPEN
   - Document evidence from the validation command output
4. **Update the Review Report**:
   - Add a "Validation Log" section if not present
   - Update each finding's status
   - Include validation date and notes
5. **Save Changes**: Use the Write tool to update the original review file

## Status Definitions
- **ADDRESSED**: Issue has been fixed (validation command passes)
- **INVALID**: Issue no longer exists or is no longer relevant
- **OPEN**: Issue still exists and is valid

## Important
- Run actual validation commands - don't just assume
- Document evidence from command output
- Be accurate in determining status

Begin by reading the review file, then validate each finding.