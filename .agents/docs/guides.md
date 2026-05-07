# Agent Commands Guide (Human Readable)

## Available Commands

| Command | What it does |
|---------|-------------|
| `/begin-workflow` | Full pipeline: plan → implement → review → cleanup |
| `/plan` | Creates implementation plan + task list from spec & design |
| `/implement` | Executes plan tasks using TDD (red → green → refactor) |
| `/review-loop` | Review cycle: report → validate → fix → fresh → cleanup |
| `/review-report` | Scoped code review of current branch changes |
| `/review-validate` | Full pipeline: clarify vague findings → verify statuses |
| `/review-clarify` | Improves review precision — rewrites vague findings |
| `/review-verify` | Checks each finding: addressed, invalid, or still OPEN |
| `/review-implement` | Applies fixes for review findings |
| `/review-post` | Posts review as a GitHub PR review with inline comments |
| `/review-update` | Follows up on PR review (resolve threads, flag remaining) |
| `/review-fetch` | Pulls unresolved PR comments into a local review file |
| `/review-cleanup` | Archives resolved review reports |
| `/rebase` | Safely rebases branch onto target (avoids commit duplication) |
| `/commit-cleanup` | Cleans up commit history — squashes fixups, removes duplicates |
| `/begin-worktree` | Creates a new worktree + branch for feature development |
| `/worktree-prune` | Removes inactive worktrees (checks PR status) |
| `/worktree-cleanup` | Cleans up local artifacts (reviews, tmp, caches) in current worktree |
| `/setup-project` | Bootstraps `.agents/` structure in a new project |

---

## When to Run What

| You want to... | Run this |
|----------------|----------|
| Automate the whole feature cycle (spec → code → review → PR) | `/begin-workflow specs/my-feature/` |
| Break a spec into actionable tasks | `/plan specs/my-feature/` |
| Write code following a plan | `/implement specs/my-feature/` |
| Run the full review loop (report → fix → fresh report) until clean | `/review-loop src/my-subproject/` |
| Check if your branch code is clean before merging | `/review-report src/my-subproject/` |
| Run full validation (clarify + verify) on a review | `/review-validate reviews/REVIEW-foo.md` |
| Improve vague review findings to be more precise | `/review-clarify reviews/REVIEW-foo.md` |
| Check if previously flagged issues are actually fixed | `/review-verify reviews/REVIEW-foo.md` |
| Fix issues found by a review | `/review-implement reviews/REVIEW-foo.md` |
| Publish review results on a GitHub PR | `/review-post reviews/REVIEW-foo.md` |
| Update a PR review after fixes landed | `/review-update reviews/REVIEW-foo.md` |
| Get PR review comments into a local file for tracking | `/review-fetch 42` |
| Archive a review where all issues are resolved | `/review-cleanup reviews/REVIEW-foo.md` |
| Safely rebase current branch without duplicating commits | `/rebase` or `/rebase main` |
| Create a new worktree + branch for feature development | `/begin-worktree feat/new-feature` |
| Remove inactive/stale worktrees (checks PRs) | `/worktree-prune` |
| Clean up local artifacts (reviews, caches, tmp) | `/worktree-cleanup` |
| Set up a fresh project with the `.agents/` structure | `/setup-project ./my-new-project` |

---

## Typical Workflows

### New Feature (Full Automation)

```bash
/begin-workflow specs/my-feature/
```

This runs the entire pipeline automatically: `plan` → `implement` → `review-loop` → `review-cleanup`.

### Review Loop (Standalone)

```bash
/review-loop src/my-subproject/            # Run review cycle until clean
```

This runs: review-report → review-validate → review-implement → ... → fresh review-report → ... → review-cleanup.

### Manual PR Review Cycle

```bash
/review-report src/my-subproject/       # 1. Generate a scoped review of your branch
/review-post reviews/REVIEW-foo.md      # 2. Post on the PR as inline comments
                                        #    (developer fixes the code)
/review-validate reviews/REVIEW-foo.md  # 3. Re-check if fixes actually work
/review-update reviews/REVIEW-foo.md    # 4. Update PR review: resolve fixed, flag remaining
                                        #    (repeat 3-4 until all clean)
/review-cleanup reviews/REVIEW-foo.md   # 5. Archive the resolved review
```

### Reviewing Someone Else's PR

```bash
/review-fetch 42                        # 1. Pull PR #42 comments into a review file
                                        #    (read and assess the findings)
/review-post reviews/REVIEW-fetched.md  # 2. Post your review with inline comments on the PR
```

---

## Command Outputs

| Command | Creates / Updates |
|---------|------------------|
| `/plan` | `implementation-plan.md` + `task.md` in the target directory |
| `/implement` | Code changes + updates `task.md` |
| `/review-loop` | Runs report → validate → fix → cleanup cycle |
| `/review-report` | `./reviews/REVIEW-{name}.md` |
| `/review-validate` | Clarifies + verifies: updates `./reviews/REVIEW-{name}.md` |
| `/review-clarify` | Rewrites vague findings in `./reviews/REVIEW-{name}.md` |
| `/review-verify` | Updates statuses in `./reviews/REVIEW-{name}.md` |
| `/review-implement` | Code changes + updates `./reviews/REVIEW-{name}.md` |
| `/review-post` | Posts on GitHub PR |
| `/review-update` | Comments/resolutions on GitHub PR |
| `/review-fetch` | `./reviews/REVIEW-{name}-fetched.md` |
| `/review-cleanup` | Archives to `./reviews/archived/` |
| `/rebase` | Rebases current branch onto target |
| `/begin-worktree` | Creates `.worktrees/<branch>/` with matching branch |
| `/worktree-prune` | Removes stale `.worktrees/` directories |
| `/worktree-cleanup` | Deletes `./reviews/`, `./tmp/`, `./dev/`, caches |
| `preflight-review.py` | Pre-flight: stale review + unstaged changes + scope |
| `preflight-pr.py` | PR number detection |
| `preflight-rebase.py` | Rebase safety check |
| `gh.py` | GitHub PR/review helper (fetch, post, inline, reply, resolve, update, create) |
