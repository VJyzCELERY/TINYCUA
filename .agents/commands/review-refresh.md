---
description: Consolidates all existing PR reviews into one fresh review, marking old ones as outdated
subtask: true
---

Consolidate all existing reviews on a PR into a single fresh review. Each finding is validated against the current PR head — stale/inapplicable findings are dropped. All previous reviews are minimized as `OUTDATED`, then a new consolidated review is posted following the review-report and review-post flow.

> Load skill: review-pr (for PR review operations)
> Load skill: review-core (for review report generation)

**Query**: $1 (natural language query or PR number, e.g., "refresh PR #42" or simply "42")
**PR Number (Optional)**: $2 (if not provided, detect from current branch or parse from query)

---

## Overview

After multiple rounds of changes, old review comments may be stale, duplicated, or no longer apply to the current diff. This command fetches every existing review, consolidates all still-relevant findings into one report, hides every previous review as outdated, and posts a single fresh review.

---

## Instructions

> Load _common-preflight.md
> Load skill: gh (for gh.py — all fetch/minimize/post operations)

1. **Detect PR**: If `$2` is not provided, detect the PR number:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py "$1")
   ```

2. **Get current PR head**:
   ```bash
   HEAD_SHA=$(gh pr view "$PR_NUMBER" --json headRefOid --jq .headRefOid)
   ```

3. **Fetch all existing reviews and comments**:
   ```bash
   uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER" --output ./tmp/refreshed-fetched.md
   ```
   Read `./tmp/refreshed-fetched.md` — it contains every review grouped by author with all inline comments. Each review has its URL, state, and body. Each inline comment has its URL, location, and body.

4. **Get the current PR diff** for validating finding locations:
   ```bash
   gh pr diff "$PR_NUMBER"
   ```

5. **Consolidate findings**: For each review in the fetched output, extract its findings (from both the review body and inline comments). For each finding:
   - Check if the file and line still exist in the current diff
   - Check if the finding's issue is still relevant (the suggestion may already be addressed)
   - **Keep** if the issue is still valid and the location (if inline) still exists
   - **Drop** if the issue is resolved or the location no longer exists in the diff
   - Deduplicate — if the same issue appears in multiple reviews, keep only one copy

6. **Build a consolidated review report**: Using the REVIEW-template.md structure, compile all kept findings into a single report saved as `./reviews/REVIEW_{branch}_refreshed.md`. Each finding keeps its original issue code, severity, and description. Add a note that this is a consolidated refresh.

7. **Minimize all previous reviews as outdated**: For every review and inline comment that was fetched (except the one you're about to post), minimize it:
   ```bash
   uv run python .agents/scripts/gh.py minimize "$PR_NUMBER" <comment-id> --classifier OUTDATED
   uv run python .agents/scripts/gh.py minimize "$PR_NUMBER" <review-comment-id> --classifier OUTDATED
   ```
   Note: inline comments are minimized individually by their comment ID. Review-level comments (overall review bodies) are not individually minimizable — only their inline child comments can be hidden.

8. **Post the new consolidated review**: Use the review-post flow with the consolidated report:
   ```bash
   REVIEW_EVENT="COMMENT"  # default for refresh
   # Follow review-post steps 4-8 to build and post the review
   # Use the consolidated report as the source
   ```

9. **Update the consolidated report with URLs**: After posting, fetch the new review's URLs:
   ```bash
   uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER" --output ./tmp/refreshed-result.md
   ```
   Read the output, extract the new review URL and each inline comment URL, and append them to the consolidated report.

---

## Important

- The goal is **consolidation**, not re-review. Keep existing findings that are still valid — don't add new ones unless they were already in a previous review.
- Skip findings that have clearly been addressed (the code/diff no longer shows the issue).
- Deduplicate aggressively — if the same issue code appears in multiple reviews, keep only the most recent/complete version.
- Per-review inline comments are minimized individually by comment ID (the number from `#discussion_r<id>`).
- Review-level summaries (the overall review body) cannot be minimized via the REST/GraphQL API for pull request reviews — only inline pull request review comments can be minimized. Focus on minimizing the inline comments.
- After refresh, the PR will have a single active review plus all the minimized (greyed out) older comments.
