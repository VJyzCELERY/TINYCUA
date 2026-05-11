---
description: Resolves or minimizes old review comments, then reposts the updated review fresh
subtask: true
---

Update a review by resolving/minimizing all previously linked comments, then reposting the entire review fresh. For each finding with a `**PR Comment**` URL, the old comment is resolved (if inline) or minimized (if non-inline). The updated review is then posted following the review-post flow, and the local report is re-linked to the new URLs.

> Load skill: review-pr (for updating PR reviews after fixes)

**Query**: $1 (natural language query or review file path, e.g., "update the PR review from reviews/REVIEW_foo.md" or simply "reviews/REVIEW_foo.md")
**PR Number (Optional)**: $2 (if not provided, detect from current branch or parse from query)


## Overview

> Load _common-preflight.md
> Load skill: gh (for gh.py — all update/post operations)

After fixes have been implemented and validated, this command refreshes the PR review: old comments are cleared (resolved or minimized), and a fresh review is posted with updated findings. The local report is updated with the new URLs.

---

## Instructions

1. **Read the updated review report**: Load the REVIEW_{name}.md file — it contains each finding with a `**PR Comment**` URL from the previous posting.
2. **Detect PR**: If `$2` is not provided, detect the PR number:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
   ```
3. **Resolve or minimize every previously linked comment**: For each finding that has a `**PR Comment**` URL:

   - **If the URL contains `#discussion_r`** (inline comment): resolve the thread:
     ```bash
     uv run python .agents/scripts/gh.py resolve "$PR_NUMBER" <comment-id>
     ```

   - **If the URL contains `#pullrequestreview`** (non-inline follow-up review comment): minimize as outdated:
     ```bash
     uv run python .agents/scripts/gh.py minimize "$PR_NUMBER" <comment-id> --classifier OUTDATED
     ```

   Extract the comment ID from the URL (the trailing number after `#discussion_r` or `#pullrequestreview`).

4. **Post the updated review fresh**: Follow the review-post flow (steps 4-9) to build and post a brand new review using the updated report. The new review body should mention:
   - How many previous findings are now resolved
   - How many remain open (if any)
   - Example:
     ```
     **Review Update**: 2 of 3 findings resolved. 1 still open (see inline comments).
     ```

5. **Re-link the local report**: After posting, fetch the new review's URLs:
   ```bash
   uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER" --output ./tmp/updated-fetch.md
   ```
   Read the output, extract the new review URL and each inline comment URL, and update every finding's `**PR Comment**` field in the local report to point to the new URLs.

---

## Important

- Read `.agents/scripts/gh.py` usage first — all PR operations go through it
- Read `.agents/skills/gh-review/SKILL.md` before updating — it contains the full gh review workflow reference
- Every finding that had a `**PR Comment**` URL from the previous post must be resolved or minimized before reposting
- After reposting, update ALL `**PR Comment**` fields in the local report to the new URLs from the fresh review
- **Markdown**: All review bodies are markdown. Use proper formatting — code blocks for commands, bullet lists, bold as appropriate.
