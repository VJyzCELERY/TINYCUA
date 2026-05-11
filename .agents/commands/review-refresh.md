---
description: Consolidates all existing PR reviews into one fresh review, marking old ones as outdated
subtask: true
---

Consolidate all existing reviews on a PR into a single fresh review. Old comments are batch-closed first (inline comments resolved, non-inline minimized), then a single fresh consolidated review is posted following the review-report and review-post flow.

> Load skill: review-pr (for PR review operations)
> Load skill: review-core (for review report generation)

**Query**: $1 (natural language query or PR number, e.g., "refresh PR #42" or simply "42")
**PR Number (Optional)**: $2 (if not provided, detect from current branch or parse from query)

---

## Overview

After multiple rounds of changes, old review comments may be stale, duplicated, or no longer apply to the current diff. This command closes all outdated comments, then posts a single fresh review that consolidates only the still-relevant findings.

---

## Instructions

> Load _common-preflight.md
> Load skill: gh (for gh.py — all fetch/close/post operations)

1. **Detect PR**: If `$2` is not provided, detect the PR number:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py "$1")
   ```

2. **Get current PR head** (the commit range for the refreshed review):
   ```bash
   HEAD_SHA=$(gh pr view "$PR_NUMBER" --json headRefOid --jq .headRefOid)
   BASE_SHA=$(gh pr view "$PR_NUMBER" --json baseRefOid --jq .baseRefOid)
   echo "Refreshing review at commit range: $(git rev-parse --short $BASE_SHA)...$(git rev-parse --short $HEAD_SHA)"
   ```

3. **Fetch all active (unminimized) comments and reviews**:
   ```bash
   uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER" --output ./tmp/refreshed-fetched.md
   ```
   Read `./tmp/refreshed-fetched.md` — it contains every non-minimized review grouped by author with all inline comments. Each review has its URL, state, and body. Each inline comment has its URL, location, and body.

4. **Batch close all outdated comments**: Build a batch JSON with every comment/review URL from the fetched output (except any that are part of an active human discussion). Inline comments get resolved; non-inline follow-up reviews get minimized.
   ```bash
   cat > ./tmp/batch-close.json << 'EOF'
   [
     {"url": "https://github.com/.../pull/26#discussion_r<id1>"},
     {"url": "https://github.com/.../pull/26#discussion_r<id2>"},
     {"url": "https://github.com/.../pull/26#pullrequestreview-<id3>", "classifier": "OUTDATED"}
   ]
   EOF
   uv run python .agents/scripts/gh.py batch close "$PR_NUMBER" ./tmp/batch-close.json
   ```
   Skip any thread that has replies from the PR author or other humans — active discussions should not be closed.

5. **Re-read the fetched output**: Read `./tmp/refreshed-fetched.md` again to extract all findings from the now-closed reviews. Each review body and inline comment contains finding details (issue code, severity, description, Why, Suggestion, How to Validate).

6. **Get the current PR diff** for validating finding locations:
   ```bash
   gh pr diff "$PR_NUMBER"
   ```

7. **Validate and consolidate findings**: For each finding extracted in step 5:
   - Run the finding's **How to Validate** command (from the inline comment or review body) against the current PR head
   - If the validation command succeeds, the finding is **resolved** — drop it
   - If the validation command fails, the finding is **still open** — keep it
   - If the finding has no validation command, check manually: does the file and line still exist in the current diff? Is the issue still present?
   - Deduplicate — if the same issue appears in multiple reviews, keep only one copy

8. **Build a consolidated review report**: Using the REVIEW-template.md structure, compile all kept (still open) findings into a single report saved as `./reviews/REVIEW_{branch}_refreshed.md`. Each finding keeps its original issue code, severity, and description. The review summary should note:
   - The commit range reviewed: `${BASE_SHA:7}...${HEAD_SHA:7}`
   - How many findings were carried forward vs resolved
   - That this is a consolidated refresh after batch-closing N prior comments

9. **Post the consolidated review**: Follow the review-post flow with the consolidated report:
   ```bash
   REVIEW_EVENT="COMMENT"  # default for refresh
   # Follow review-post steps 4-9 to build and post the review
   # The review body should include the commit range:
   #   Reviewed commit range: ${BASE_SHA:7}...${HEAD_SHA:7}
   ```

10. **Update the consolidated report with URLs**: After posting, fetch the new review's URLs:
    ```bash
    uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER" --output ./tmp/refreshed-result.md
    ```
    Read the output, extract the new review URL and each inline comment URL, and append them to the consolidated report.

---

## Important

- The goal is **consolidation**, not re-review. Keep existing findings that are still valid — don't add new ones unless they were already in a previous review.
- Skip findings that have clearly been addressed (the code/diff no longer shows the issue).
- Deduplicate aggressively — if the same issue code appears in multiple reviews, keep only the most recent/complete version.
- After refresh, the PR will have a single active review with all previous comments either resolved (inline) or minimized (non-inline).
