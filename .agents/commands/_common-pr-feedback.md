# Common PR Feedback

Read root `AGENTS.md`, load the `gh` skill, and acquire `$PR_INPUT` through
`_common-review-context.md`. Fetch complete review comments and reviews with
paginated repository-bound REST calls and review-thread state with paginated
GraphQL. Validate the PR head and response shapes before use.

Generated review bodies and reply or mutation payloads belong under `./tmp/`.
Preview them before authorization, post Markdown through `--body-file` where a
first-class command supports it, otherwise use validated JSON with
`gh api --input`, verify the resulting remote state, and remove every temporary
file. Preserve active human discussions, actor ownership, minimized/resolved
state, idempotent reply markers, and visible partial failures.
