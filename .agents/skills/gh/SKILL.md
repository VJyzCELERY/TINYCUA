---
name: gh
description: Safe native GitHub CLI issue, PR, review, ownership, and Specs workflows
license: MIT
compatibility: opencode
metadata:
  type: infrastructure
---

# Native GitHub CLI

Prefer first-class `gh issue`, `gh pr`, and `gh repo` commands to `gh api`,
except PR edits, whose GraphQL preflight fails on removed Projects Classic
fields. Every repository operation uses `--repo OWNER/REPO`; API endpoints
include the same owner and repository. Request only required JSON fields and
reject nonzero commands, malformed JSON, foreign resource URLs, and incomplete
reads.

```bash
gh auth status
gh api user --jq .login
gh issue view <number> --repo OWNER/REPO --json number,title,body,state,url,labels,assignees
gh issue list --repo OWNER/REPO --state open --limit 1000 --json number,title,body,url,labels
gh pr view <number> --repo OWNER/REPO --json number,title,body,state,isDraft,url,headRefName,headRefOid,baseRefName,assignees
gh pr list --repo OWNER/REPO --state all --limit 1000 --json number,state,isDraft,url,headRefName,baseRefName
gh pr diff <number> --repo OWNER/REPO
gh api --paginate "repos/OWNER/REPO/issues/<number>/comments?per_page=100" --jq '.[]'
```

## File Inputs

Generated Markdown and structured payloads live under `./tmp/`. Require a
nonempty regular file inside the repository, validate its format, preview it
before authorization, and remove it after success or failure. Never pass
generated multiline content with `--body`, `-b`, shell interpolation, or
command substitution.

```bash
gh issue create --repo OWNER/REPO --title <title> --body-file ./tmp/issue-body.md
gh issue edit <number> --repo OWNER/REPO --body-file ./tmp/issue-body.md
gh pr create --repo OWNER/REPO --head <branch> --base <base> --draft --title <title> --body-file ./tmp/pr-body.md
gh api --method PATCH repos/OWNER/REPO/pulls/<number> --input ./tmp/pr-metadata.json
gh api --method POST repos/OWNER/REPO/pulls/<number>/reviews --input ./tmp/review.json
```

Use `gh api --input` for generated REST and GraphQL JSON. Scalar GraphQL
variables may use `-F`; generated queries or mutations use validated JSON.

## Ownership

Resolve the actor with `gh api user --jq .login`. Read current assignees and
skip the write when the actor is already present. Otherwise add without
replacement through the issue endpoint, which also owns PR assignees, then
fetch again and require the actor in `assignees`:

```bash
gh api --method POST repos/OWNER/REPO/issues/<number>/assignees --input ./tmp/assignees.json
```

New issues are unclaimed unless their workflow says otherwise. New PRs are
drafts. Never run `gh pr ready` during metadata updates; verify `isDraft` is
unchanged.

## Reviews

Use paginated REST reads for reviews and comments and paginated GraphQL
`reviewThreads` for resolution and minimization state. Verify the PR head before
every write. Post generated reviews through `gh api --input`. Reply through a
JSON input file, resolve only the matched thread node, and minimize only an
actor-owned review node. Re-fetch complete state after each write. Never clean
up active human discussion; report partial completion and stop on head drift.

## Indexed Specs

Fetch the Specs issue and all comments with
`gh api --paginate "repos/OWNER/REPO/issues/<number>/comments?per_page=100" --jq '.[]'`.
Parse and validate every nonempty NDJSON line; reject malformed output.
Validate the open `spec` issue, primary marker, exactly four unique
repository-bound indexed comment URLs, and comment presence before mutation.
Create only missing comments, preserve established URLs, edit only changed
comments, and update the issue index only after all comment writes verify.
Generated bodies use `./tmp/*.md` with `--body-file`; generated API JSON uses
`gh api --input`.

Check every exit status and response shape. An empty result is valid only after
a successful exhaustive read.
