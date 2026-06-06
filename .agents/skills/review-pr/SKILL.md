---
name: review-pr
description: Post reviews via review-post, update via review-update, refresh via review-refresh
license: MIT
compatibility: opencode
metadata:
  type: command-skill
---

# Skill: review-pr — PR Review Operations

## Purpose

Manage the full review lifecycle: fetch/merge remote reviews, post reviews, update after fixes, consolidate all reviews. All posting goes through `review-post` which uses `.agents/templates/` for consistent formatting.

## Prerequisites

- Load skill: preflight (for preflight-pr.py)
- Load skill: gh (for gh.py — all posting/fetching/interact operations)

## Execution

### Post a review (review-post)
1. Detect PR: `PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)`
2. Get PR diff via `uv run python .agents/scripts/gh.py cmd pr diff "$PR_NUMBER"`
3. Read Overall Assessment from report header → determines review event + emote
4. Read `.agents/templates/review-body-snippet.md` and `.agents/templates/inline-comment-format.json` for structure
5. Read `.agents/templates/inline-comment-body-snippet.md` for inline comment body format
6. Build inline comments JSON in `./tmp/` using the templates
7. Post a single review with all inline comments + body: `uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/body.md ./tmp/comments.json --event "$EVENT"`
   - The review body (from `.agents/templates/review-body-snippet.md`) lists ALL findings — inline findings marked "Details inline", non-inline findings with full Why/Suggestion/How to Validate
8. Fetch posted comments, update local report with PR Comment URLs

### Fetch remote reviews (review-fetch)
1. Detect PR with `preflight-pr.py`.
2. Default the canonical local report to `./reviews/REVIEW_{normalized_branch}.md` where branch slashes become underscores.
3. Fetch every remote review/comment with `uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER" --all --output ./reviews/remote/REVIEW_{normalized_branch}_remote_raw_{ts}.md`.
4. Convert remote data into temporary review-format files under `./reviews/remote/` with preserved `**PR Comment**` and `**PR Review URL**` links.
5. Merge into the canonical local report, deduping duplicates. Remote findings outrank local findings without remote links; preserve useful local context.
6. If duplicate remote links exist for the same finding, keep the newest authoritative link and resolve/minimize older links using `gh.py interact` only.

### Update a review (review-update)
1. Preflight: check staleness. If local is behind remote, sync to latest first. Use fast-forward pull when possible; for rebased/diverged remote state, create a backup branch for local commits and stash dirty work before resetting to upstream. If the review commit range is stale, run `/review-verify` first to update the local report before posting remote updates.
2. For each `**PR Comment**` URL in the local report: reply + resolve inline threads, minimize review bodies
3. Run `review-post` to publish the updated verdict
4. Re-link URLs in the local report

### Refresh all reviews (review-refresh)
1. Fetch ALL active reviews from remote + read local report
2. Consolidate: deduplicate, validate, merge findings
3. Close all old comments (resolve inline, minimize review bodies)
4. Overwrite local review file with consolidated report
5. Run `review-post` to publish

## Event mapping
| Assessment | Emote | Event |
|-----------|-------|-------|
| Approved / Approved With Recommendation | ✅ | APPROVE |
| Addressed With Potential Follow-up | ✅ | APPROVE |
| Change Requested / Blocked | ⚠️ / ❌ | REQUEST_CHANGES |

## Common Pitfalls
- Always verify line numbers against current PR diff before posting
- Always update local report with PR URLs after posting
- Use `gh.py interact` for reply/resolve/minimize — it accepts full URLs
- Use `.agents/templates/` for consistent formatting across all review commands
- **Use markdown hyperlinks** when referencing previous reviews or comments — `[text](url)`, never raw IDs like `PRR_abc123`
- Do not ask where fetched reviews should go. Default to `./reviews/REVIEW_{normalized_branch}.md` and use `./reviews/remote/` only for temporary remote reports.
