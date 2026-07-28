# Common GitHub Ownership

Resolve the authenticated login with `gh api user --jq .login`; never infer it
from Git configuration or authorship. Fetch canonical issue or PR JSON with an
explicit `--repo OWNER/REPO`, preview the login and target numbers, and obtain
authorization immediately before writes unless `--auto` or inherited `/goal`
authorization applies.

Claim additively and preserve existing assignees. From the fetched JSON, skip the write when `<login>` is already assigned. Otherwise write `{"assignees":["<login>"]}` to `./tmp/assignees.json`, validate and preview that exact object, then use the same issue endpoint for an issue or PR:

```bash
gh api --method POST repos/OWNER/REPO/issues/<number>/assignees --input ./tmp/assignees.json
```

Fetch the resource again and require `<login>` in `assignees`; stop on partial
failure, and remove the payload after success or failure. Claim every selected
issue before implementation and every resolved or created PR. Repeated claims
are idempotent. New issues are unclaimed unless requested. New PRs include the
login and are drafts. Metadata updates preserve existing readiness; readiness
changes belong to a later explicit workflow.
