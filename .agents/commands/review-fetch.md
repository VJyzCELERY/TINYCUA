---
description: Fetches all active PR comments into a local review report file
subtask: true
---

Fetch every remote review/comment from a GitHub PR, write temporary remote review reports, then merge them into the canonical local review report for the current branch.

> Load skill: review-pr (for pulling PR comments into local review)

**Query**: $1 (optional PR number/URL. If omitted, auto-detect the PR for the current branch.)
**Output File**: Always defaults to `./reviews/REVIEW_{normalized_branch}.md`; do not ask where to write it. `normalized_branch` is the current branch name with `/` replaced by `_`.


## Instructions

1. **Compute canonical paths**:
   ```bash
   BRANCH=$(git branch --show-current)
   NORMALIZED_BRANCH=${BRANCH//\//_}
   REVIEW_FILE="./reviews/REVIEW_${NORMALIZED_BRANCH}.md"
   REMOTE_DIR="./reviews/remote"
   mkdir -p "$REMOTE_DIR"
   ```
   Do not ask the user where the review file should be created or merged. Use `$REVIEW_FILE`.

2. **Detect PR**: If `$1` is not provided, detect the PR number:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
   ```
   If `$1` is a PR number or URL, pass it to `preflight-pr.py` to normalize it:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py "$1")
   ```

3. **Read the existing local report first**: If `$REVIEW_FILE` already exists, read it before fetching/merging. Preserve all non-duplicate local findings and all useful local-only context.

   If local is behind remote, sync to latest first. Use fast-forward pull when possible. If the remote rebased/diverged, create a backup branch for local commits and stash dirty work before resetting to upstream. If the existing local review commit range is stale, that is expected: this command updates the canonical report while merging remote findings against the latest commit.

4. **Fetch every remote review/comment**:
   ```bash
   TS=$(date +%s)
   RAW_REMOTE="${REMOTE_DIR}/REVIEW_${NORMALIZED_BRANCH}_remote_raw_${TS}.md"
   uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER" --all --output "$RAW_REMOTE"
   ```
   `--all` is required because this command reconciles every remote review that exists, not only active unresolved comments.

5. **Write temporary remote review reports**: Convert the fetched remote data into one or more temporary files under `./reviews/remote/`. These temporary files MUST follow `.agents/templates/REVIEW-template.md` / `review-report` finding format and MUST preserve links:
   - Use `REMOTE-001`, `REMOTE-002`, ... issue codes unless the remote body already contains a stable issue code.
   - Preserve inline comment links as `**PR Comment**: <url>`.
   - Preserve parent review links as `**PR Review URL**: <url>`.
   - Include reviewer, submitted timestamp, review state, location, severity, suggested fix, and validation guidance when present.
   - Keep these files local-only under `./reviews/remote/`; never commit them.

6. **Merge remote + local findings into `$REVIEW_FILE`**:
   - Start from the existing local report if it exists; otherwise start from `.agents/templates/REVIEW-template.md`.
   - Add all remote findings and preserve all unique local findings.
   - Recompute summary counts and overall assessment after merging.
   - Update the header branch and commit range to the current PR/base state when available.

7. **Deduplicate findings**. Treat findings as duplicates when they describe the same root issue, especially when they share the same location plus substantially equivalent description/suggested fix/validation command. Apply these precedence rules:
   - Remote findings have higher authority than local findings without remote links. If a remote finding duplicates a local finding that has no `**PR Comment**` or `**PR Review URL**`, replace the local finding with the remote finding while incorporating any useful extra context from the local finding.
   - If the existing local finding already has the same remote link, do not add the remote finding again.
   - If the same finding has different remote links, compare link metadata by fetching both with `gh.py fetch url` and keep the newest authoritative link in `$REVIEW_FILE`.
   - For the older duplicate link, resolve/close it if it is not already resolved/minimized:
     - For inline comments, first reply that the finding is now tracked by the kept/newer review and is resolved, then resolve the thread:
       ```bash
       uv run python .agents/scripts/gh.py interact reply "$OLDER_URL" ./tmp/reply.md
       uv run python .agents/scripts/gh.py interact resolve "$OLDER_URL"
       ```
     - For top-level review bodies, minimize the older duplicate:
       ```bash
       uv run python .agents/scripts/gh.py interact minimize "$OLDER_URL" --classifier OUTDATED
       ```
     - All remote interactions MUST use `.agents/scripts/gh.py`; do not use raw `gh` for reply/resolve/minimize.
   - When replacing a local finding, do not discard useful details. Incorporate extra impact, validation, examples, or suggested fix details into the retained finding.

8. **Write the canonical merged report** to `$REVIEW_FILE`. Report the canonical path and any remote links that were deduped/resolved.

---

## Required Context

- Preflight: preflight-pr.py
- Skills: review-pr, gh
- Rules: none
- Templates: REVIEW-template.md
- Mutates files: yes
- Mutates git history: no
- Mutates remote: yes (only when deduping older duplicate remote links; uses gh.py interact)
- Requires user confirmation: no

## Important

- Always fetch with `--all` for reconciliation.
- Distinguish between inline comments (file-specific) and top-level review summaries (general).
- Respect review state: CHANGES_REQUESTED reviews have actionable findings; COMMENTED reviews are informational.
- If the PR has no remote reviews/comments, keep any existing local report and report that no remote findings were found.
- Do not ask where the review file is. Default to `./reviews/REVIEW_{normalized_branch}.md`.
