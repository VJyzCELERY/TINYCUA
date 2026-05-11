---
description: Posts a review report as a PR review with inline comments and tracks URLs
subtask: true
---

Post a completed review report as a GitHub PR review with inline comments. After posting, update the local review report with the URLs of each posted comment.

> Load skill: review-pr (for posting reviews as PR inline comments)

**Query**: $1 (natural language query or review file path, e.g., "post the review from reviews/REVIEW_foo.md to PR #42" or simply "reviews/REVIEW_foo.md")
**PR Number (Optional)**: $2 (if not provided, detect from current branch or parse from query)

---

## Overview

This command reads a review report from `$1`, extracts each finding, and posts them as a structured PR review. After posting, it updates the local review report to track the URL of each comment so future commands (verify, clarify) can reply and resolve them automatically.

---

## Instructions

> Load _common-preflight.md
> Load skill: gh (for gh.py — all posting operations)

1. **Read the review report**: Load the REVIEW_{name}.md file
2. **Detect PR**: If `$2` is not provided, detect the PR number:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
   ```
3. **Get PR diff**: Download the PR diff to map line numbers:
   ```bash
    gh pr diff "$PR_NUMBER"   # gh.py doesn't have diff command yet
   ```
 4. **Read Overall Assessment**: Extract the `**Overall Assessment**` field from the review report header. This determines the PR review event and the emote.
 5. **Get commit range**: Determine the commit range reviewed:
    ```bash
    BASE_SHA=$(gh pr view "$PR_NUMBER" --json baseRefOid --jq .baseRefOid)
    HEAD_SHA=$(gh pr view "$PR_NUMBER" --json headRefOid --jq .headRefOid)
    ```
 6. **Classify findings**: For each finding, try to map the **Location** to the current diff:
    - **Inline-capable**: has a valid `file:line` that exists in the current diff → will be posted as an inline comment
    - **Non-inline**: targets PR metadata (title, body, etc.) or the line no longer exists in the diff → full details MUST be preserved in a review body
 7. **Build inline comments**: For each inline-capable finding, build an inline comment with `path`, `line`, `side`, and `body`. Every `body` field and the entire review body is **markdown** — use fenced code blocks for commands, bullet lists, bold, etc. Issue IDs should follow `{TEXT}-{NUMBER}` format (e.g. `F-001`, `MED-001`, `ISSUE-001`) — keep them short and consistent within this review. The inline body MUST start with `**[<issue-id>]** - **[<priority>]** - <short description>` (e.g., `**F-001** - **HIGH** - Serialization Plan Reuses Non-Serializable Agent Config`).
 8. **Post the review(s)**:
    - Post main review with all inline comments and a body listing all findings
    - If there are non-inline findings, post a follow-up review with their full details as the body (no inline comments) using the same event

    ```bash
     REVIEW_FILE="$1"
     REVIEW_EVENT="APPROVE"  # default
     if grep -q "Change Requested\|Blocked" "$REVIEW_FILE"; then
       REVIEW_EVENT="REQUEST_CHANGES"
     elif grep -q "Approved With Recommendation" "$REVIEW_FILE"; then
       REVIEW_EVENT="APPROVE"
     fi

     # Map assessment to emote
     ASSESSMENT=$(grep -oP '\*\*Overall Assessment\*\*:\s*\K.*' "$REVIEW_FILE" | head -1)
     case "$ASSESSMENT" in
       *Approved*) EMOTE="✅" ;;
       *Approved With Recommendation*) EMOTE="✅" ;;
       *Change Requested*) EMOTE="⚠️" ;;
       *Blocked*) EMOTE="❌" ;;
       *) EMOTE="" ;;
     esac

     # --- Main review: inline comments + body ---
     # IMPORTANT: The review body is markdown. Use proper markdown formatting (fenced code blocks, lists, bold, etc.)
     cat > ./tmp/review-body.md << 'BODY'
    Reviewed commit range: ${BASE_SHA:7}...${HEAD_SHA:7}

    **Assessment**: ${EMOTE} **${ASSESSMENT}**

    [Brief overall assessment summary — total findings, severity breakdown, key reasoning]

    ### Findings

    **[<issue-id>]** - **[<priority>]** - <short description>
    **Why**: <why it matters>
    **Suggestion**: <suggested fix>

    **[<issue-id>]** - **[<priority>]** - <short description>
    **Why**: <why it matters>
    **Suggestion**: <suggested fix>

    Detailed inline comments follow for findings that map to current diff lines.
    BODY
     cat > ./tmp/review-comments.json << 'COMMENTS'
    [
      {
        "path": "src/file.py",
        "line": 42,
        "side": "RIGHT",
        "body": "**[<issue-id>]** - **[<priority>]** - <short description>\n\n**Why**: <why it matters>\n\n**Suggestion**: <suggested fix>\n\n**How to Validate**: <how to validate>"
      }
    ]
    COMMENTS
     uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/review-body.md ./tmp/review-comments.json --event "$REVIEW_EVENT"

      # --- Follow-up review: non-inline findings (if any) ---
      # If any findings could not be posted inline (e.g. they target PR metadata, not a diff line),
      # post them as a separate review with the same event so no information is lost.
      # IMPORTANT: Format the body in markdown.
      # gh.py will fall back to COMMENT if the event is rejected (e.g. own PR author).
      if [ "${#non_inline_findings[@]}" -gt 0 ]; then
        cat > ./tmp/review-noninline-body.md << 'BODY'
    Additional findings that could not be posted as inline comments:

    ---

    ### **[<issue-id>]** - **[<priority>]** - <short description>

     **Why**: <why it matters>

     **Suggestion**: <suggested fix>

     **How to Validate**: <how to validate>
       uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/review-noninline-body.md --event "$REVIEW_EVENT"
     fi
    ```
 9. **Fetch posted comments to get URLs**: After posting all reviews, fetch the PR comments to verify posting and capture links:
    ```bash
    uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER" --output ./tmp/fetched-review.md
    ```
    Read `./tmp/fetched-review.md` — it contains the full posted review with inline comments grouped under each review section, each with its `URL:` link. Match each inline comment to its finding by file path, line number, and issue code. Extract:
    - The PR review URL from the overall review header
    - Each inline comment's URL from its `URL:` line
10. **Update the local review report**: For each finding that was posted, append a `**PR Comment**` field:
   ```
   **PR Comment**: https://github.com/owner/repo/pull/<number>#discussion_r<comment-id>
   ```
   Also add a `**PR Review**` field for the overall review:
   ```
   **PR Review URL**: https://github.com/owner/repo/pull/<number>#pullrequestreview-<review-id>
   ```
   Save the updated review report. This links every finding to its PR comment so future commands can reply and resolve automatically.

---

## Inline Comment Format

```json
{
  "path": "src/file.py",
  "line": 42,
  "side": "RIGHT",
  "body": "**[<issue-id>]** - **[<priority>]** - <short description>\n\n**Why**: <why it matters>\n\n**Suggestion**: <suggested fix>\n\n**How to Validate**: <how to validate>"
}
```

> **Important**: The entire review body and all inline comment bodies are **markdown**. Use proper markdown formatting throughout — fenced code blocks for commands, bullet lists, bold/italic as appropriate. Issue IDs use `{TEXT}-{NUMBER}` format (e.g. `F-001`, `MED-001`) and must be unique within the review.

## Overall Assessment to Review Event Mapping

| Overall Assessment | Emote | Review Event |
|-------------------|-------|--------------|
| Approved | ✅ | `APPROVE` |
| Approved With Recommendation | ✅ | `APPROVE` (with inline comment notes) |
| Change Requested | ⚠️ | `REQUEST_CHANGES` |
| Blocked | ❌ | `REQUEST_CHANGES` |

The assessment is read from the `**Overall Assessment**` field in the review report header. Include the emote in the assessment line: `**Assessment**: ✅ **Approved**`

## Important

- Read `.agents/scripts/gh.py` usage before posting — all PR writes go through it
- Always verify line numbers against the current PR diff before posting
- **After posting, MUST update the local review report** with PR comment URLs — this enables automatic reply/resolve in review-verify and review-clarify
- Do NOT post reviews with empty inline comments — skip findings that can't be mapped to the diff
