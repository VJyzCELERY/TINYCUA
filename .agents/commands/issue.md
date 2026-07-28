---
description: Selects or creates one local or GitHub issue
subtask: true
---

# Issue

**Query**: `$1` `existing <number-or-url>`, `create <bug|feature>`, or `local <lower-kebab-id>`. **Context**: `$2` issue details.

Read root `AGENTS.md`, `.github/ISSUE_TEMPLATE/`, the planning templates, and the `gh` skill. Roadmap and `spec`-labelled issues are not implementation goals. A local target is an ignored `.agents/local/issues/<lower-kebab-id>/` bundle managed by `local_issue.py`; it contains `draft.md`, `spec.md`, `design.md`, `implementation-plan.md`, and `task.md` plus local lifecycle facts. It never claims a remote issue before implementation.

1. For `existing`, fetch JSON with `gh issue view <issue> --repo OWNER/REPO --json number,title,body,state,url,labels,assignees`. Require an open, non-roadmap, non-`spec`-labelled issue in the current repository.
2. For `create`, choose `bug_report.yml` or `feature_request.yml`, collect every required form field, render `./tmp/issue-body.md` with the form's headings, and search open and closed issues for duplicate titles, terms, and scope. Present likely duplicates instead of creating another issue.
3. Perform a readiness check: one coherent outcome, identified project/subproject, testable acceptance behavior, constraints, and no unresolved blocking ambiguity. Ask concise questions until ready; do not silently expand scope.
4. Preview the exact title, body, labels, and unclaimed status. Ask for confirmation immediately before `gh issue create --repo OWNER/REPO --title <title> --body-file ./tmp/issue-body.md --label <labels>`. Verify the returned issue is unclaimed and remove the body file.
5. Fetch the returned issue and require its canonical URL, repository, open state, non-roadmap status, and no assignees. Return its normalized `OWNER/REPO#NUMBER` identity and URL. `/implement` or `/goal` claims the issue only when work begins.
6. For `local`, render its draft from the selected issue form and its four planning documents from the matching templates under `./tmp/`, then create or validate exactly one safe bundle with `uv run python .agents/scripts/local_issue.py create <lower-kebab-id> <current-branch> --worktree "$PWD" --draft ./tmp/draft.md --spec ./tmp/spec.md --design ./tmp/design.md --implementation-plan ./tmp/implementation-plan.md --task ./tmp/task.md`. Resolve clarification markers before promotion. Return `local:<lower-kebab-id>` and the validated recorded branch/worktree. Local planning, implementation, tests, commits, and review require no GitHub write.

## Required Context

- Root `AGENTS.md`; `gh` skill; applicable human issue form; native issue operations.

## Mutations

- Optional confirmed GitHub issue creation and temporary body, or one ignored local bundle. No claim, worktree, source, commit, push, or PR mutation.

## Confirmation

- Confirmation is required immediately before `create-issue`. Existing issue reads and duplicate/readiness checks are read-only.

## Failure

- Stop on malformed GitHub JSON, repository mismatch, closed/roadmap issue, duplicate risk, incomplete form, failed readiness, or rejected confirmation. Never treat a failed fetch as issue absence.
