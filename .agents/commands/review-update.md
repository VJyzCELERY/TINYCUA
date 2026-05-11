---
description: Updates the PR review from the local report — replies to inline comments, closes old threads, reposts a fresh review
subtask: true
---

Updates the PR review based on the local review report. For each linked finding, posts a reply to the inline comment documenting the current status, then resolves the thread. Non-inline (PR body) findings are minimized. Finally, a fresh review is posted reflecting the current local report — either a summary if all is resolved, or a full review with inline comments for still-open findings.

> Load skill: review-pr (for updating PR reviews after fixes)

**Query**: $1 (natural language query or review file path, e.g., "update the PR review from reviews/REVIEW_foo.md" or simply "reviews/REVIEW_foo.md")
**PR Number (Optional)**: $2 (if not provided, detect from current branch or parse from query)


## Overview

> Load _common-preflight.md
> Load skill: gh (for gh.py — all post/reply/close operations)

After fixes have been implemented and validated, this command:
1. Checks that the local report is up to date with the remote PR head
2. Replies to every linked inline comment with the current status (addressed or still open), then resolves the thread
3. Minimizes non-inline (PR body) findings
4. Posts a fresh review: a summary if all resolved, or a full review with inline comments for still-open findings
5. Re-links the local report to the new review URLs

---

## Instructions

### Pre-flight: Check staleness

Before updating, verify the review isn't stale by running the standard preflight:

> Load _common-preflight.md
> Run `uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"`
> If it exits non-zero or warns that HEAD has moved, tell the user to run `review-validate` first against the latest remote head before running `review-update`.

### Instructions

1. **Read the updated review report**: Load the REVIEW_{name}.md file — it contains each finding with `**PR Comment**` URLs and `**Status**` fields.
2. **Detect PR** (if not already done above):
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
   ```
3. **Check preflight** — if stale, warn and stop as described above.
4. **Separate findings by URL type**: Scan the entire report for URLs — check **PR Comment** fields on individual findings AND the **PR Review URL** field in the report header:
    - **Inline** (`#discussion_r` in URL): will be replied to and resolved
    - **Non-inline body** (`#pullrequestreview` in URL): will be minimized as outdated

5. **Reply and resolve all inline comments**: For each inline finding, post a reply documenting the current status, then resolve the thread. Always use `gh.py interact` — it accepts full URLs so no manual ID extraction needed.
   
   Use the `**PR Comment**` URL directly:
   ```bash
   ```bash
   # If ADDRESSED or INVALID
   cat > ./tmp/reply.md << 'EOF'
   ✅ **Resolved**: [brief validation result note — use markdown]
   EOF
   uv run python .agents/scripts/gh.py interact reply "$URL" ./tmp/reply.md
   uv run python .agents/scripts/gh.py interact resolve "$URL"
   
   # If still OPEN
   cat > ./tmp/reply.md << 'EOF'
   ❌ **Still open — will be re-reviewed**: [note on what's still needed]
   EOF
   uv run python .agents/scripts/gh.py interact reply "$URL" ./tmp/reply.md
   uv run python .agents/scripts/gh.py interact resolve "$URL"
   ```
   > Inline comments are **always resolved** after replying — the old thread is closed because a fresh review will be posted next.

6. **Minimize the previous review body**: Find the `**PR Review URL**` in the report header — this is the previous review body. Minimize it as outdated:
   ```bash
   uv run python .agents/scripts/gh.py interact minimize "$PR_REVIEW_URL" --classifier OUTDATED
   ```
   Also collect any non-inline `**PR Comment**` URLs from findings (those with `#pullrequestreview`) and minimize them the same way.

7. **Determine what to post next**: Check the report's findings:
   - **If ALL findings are ADDRESSED or INVALID**: Post a single summary review:
     ```bash
     cat > ./tmp/update-summary.md << 'BODY'
    Reviewed commit range: ${BASE_SHA:7}...${HEAD_SHA:7}

    **Assessment**: ✅ **Approved**

    All findings from the previous review have been addressed. No remaining open issues.
     BODY
     uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/update-summary.md --event APPROVE
     ```
   
   - **If some findings are still OPEN**: Post a full updated review following the **review-post** flow (steps 4-9). This includes:
     - Using `**[<issue-id>]** - **[<priority>]**` format for issue IDs
     - Using the **Inline Comment Format** and **Overall Assessment mapping** from review-post
     - Building inline comments JSON with proper markdown formatting
     - The review body should note which findings were resolved since the last review:
       ```
       **Review Update**: N of M findings resolved. N still open (see inline comments).
       ```

8. **Re-link the local report**: After posting, fetch the new review's URLs:
   ```bash
   uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER" --output ./tmp/updated-fetch.md
   ```
   Read the output, extract the new review URL and each inline comment URL, and update every finding's `**PR Comment**` field in the local report to point to the new URLs.

---

## Important

- This command works only with findings that have `**PR Comment**` URLs in the local report. Findings without a URL were never posted — use `review-post` instead.
- The commit range preflight prevents posting stale reviews. Always run `review-validate` first if the remote head has moved.
- Inline comments are **always resolved** after replying, even if still open. The fresh review replaces the old threads.
- Non-inline findings (PR body follow-ups) are minimized as outdated — they are replaced by the new review.
- **Always use `gh.py interact`** for all reply/resolve/minimize operations — it accepts full URLs and auto-detects the type. Do NOT use raw `gh api`.
- **Avoid reply doubling**: `gh.py interact reply` posts to the latest comment in the thread automatically.
- **Markdown**: All reply bodies and review bodies are markdown. Use proper formatting.
