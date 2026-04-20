---
description: Cleans up reviews that have been fully addressed
subtask: true
---

Clean up reviews that have been fully addressed (all findings resolved).

**Reviews Directory**: $1 (path to reviews folder, e.g., "reviews/" or ".agents/reviews/")
**Archive Directory (Optional)**: $2 (where to move resolved reviews, defaults to "reviews/archived/")

## Instructions

1. **Locate Reviews**: Use Glob to find all REVIEW-*.md files in `$1`
2. **Read Each Review**: For each review file:
   - Check if all findings have status "ADDRESSED" or "INVALID"
   - If all findings are ADDRESSED/INVALID, mark review as "RESOLVED"
3. **Archive Resolved Reviews**: For reviews with all issues resolved:
   - Create archive directory if it doesn't exist
   - Move the review file to archive directory
   - Rename to indicate it's resolved (e.g., REVIEW-name-RESOLVED.md)
4. **Generate Summary**: Create a summary of cleaned up reviews

## Review Status Definitions
- **RESOLVED**: All findings have been ADDRESSED or INVALID
- **IN PROGRESS**: Some findings still OPEN

## Output

```markdown
# Review Cleanup Summary

**Date**: YYYY-MM-DD
**Reviews Processed**: N

## Resolved Reviews (Archived)

| Review | Findings | Date Resolved |
|--------|----------|---------------|
| REVIEW-name.md | N issues | YYYY-MM-DD |

## Still Active Reviews

| Review | Open Issues |
|--------|-------------|
| REVIEW-name.md | N issues |
```

## Important
- Only archive reviews where ALL findings are ADDRESSED or INVALID
- Don't delete reviews - move to archive
- Keep a summary of what was cleaned up

Begin by scanning the reviews directory and cleaning up resolved reviews.