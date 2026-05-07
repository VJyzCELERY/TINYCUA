---
description: Improves review precision — rewrites vague findings, adds context, sharpens validation commands
subtask: true
---

Improve the precision of a review: rewrite vague descriptions, add missing context, sharpen validation commands, and make every finding actionable.

**Query**: $1 (natural language query or review file path, e.g., "clarify the findings in reviews/REVIEW-foo.md" or simply "reviews/REVIEW-foo.md")
**Focus Area (Optional)**: $2 (clarify only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, clarify ALL OPEN findings.

---

## Role

`review-clarify` improves the quality of each finding without changing its status. A vague finding helps nobody — clarify makes it actionable.

---

## Pre-Flight Checks

Before starting, run the pre-flight script:

```bash
uv run python .agents/scripts/check-preflight.py "$REVIEW_FILE"
```

If the script exits non-zero, warn the user via the question/ask tool. Let them decide whether to continue or request a fresh review.

---

## Instructions

1. **Read the Review**: Load the review report
2. **Run pre-flight checks**: `uv run python .agents/scripts/check-preflight.py "$REVIEW_FILE"` — warn user if issues found
3. **Filter Findings**: If `$2` is provided, only clarify those findings
3. **Clarify Each Finding**: For each finding, check and improve:

   | Aspect | Check | Fix |
   |--------|-------|-----|
   | **Location** | Is the file:line precise? | Add missing file/line references |
   | **Description** | Vague language? ("bad code", "not ideal") | Replace with specific observations |
   | **Why It Matters** | Missing impact? | Add: "This causes X because Y" |
   | **Suggested Fix** | Too generic? | Add concrete code example or pattern |
   | **How to Validate** | Missing or broken command? | Add or fix the validation command (prefixed with `uv run`) |
   | **Severity** | Appropriate? | Adjust: CRITICAL/HIGH/MEDIUM/LOW |

4. **Update the Review Report**: Save the clarified version overwriting the original
5. **Save Changes**: Use Write to update the original review file

## Examples

**Before (vague):**
```
Location: src/agent.py
Description: The error handling could be better.
```

**After (precise):**
```
Location: src/agent.py:142
Description: Bare `except:` clause catches all exceptions including SystemExit.
Why It Matters: This masks unexpected errors and makes debugging impossible.
Suggested Fix: Catch specific exception types instead.
How to Validate: grep -n 'except:' src/agent.py
```

## Important

- Do NOT change finding status — only improve the finding's clarity and actionability
- Keep the original intent — don't rewrite the finding to say something different
- Add missing "How to Test/Validate" commands where absent
- Fix broken validation commands that wouldn't actually run
