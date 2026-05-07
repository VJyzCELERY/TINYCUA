# Agent Commands Guide (Human Readable)

## Available Commands

| Command | What it does |
|---------|-------------|
| `/begin-workflow <dir>` | Full pipeline: plan → implement → review → cleanup |
| `/plan <dir>` | Creates implementation plan + task list from spec & design |
| `/implement <dir>` | Executes plan tasks using TDD (red → green → refactor) |
| `/review-report <dir>` | Scoped code review of current branch changes |
| `/review-validate <file>` | Re-checks review findings (marks fixed/stale) |
| `/review-implement <file>` | Applies fixes for review findings |
| `/review-post <file>` | Posts review as a GitHub PR review with inline comments |
| `/review-update <file>` | Follows up on PR review (resolve threads, flag remaining) |
| `/review-fetch [pr]` | Pulls unresolved PR comments into a local review file |
| `/review-cleanup <file>` | Archives resolved review reports |
| `/setup-project <dir>` | Bootstraps `.agents/` structure in a new project |

---

## When to Run What

| You want to... | Run this |
|----------------|----------|
| Automate the whole feature cycle (spec → code → review → PR) | `/begin-workflow specs/my-feature/` |
| Break a spec into actionable tasks | `/plan specs/my-feature/` |
| Write code following a plan | `/implement specs/my-feature/` |
| Check if your branch code is clean before merging | `/review-report src/my-subproject/` |
| Re-check if previously flagged issues are actually fixed | `/review-validate reviews/REVIEW-foo.md` |
| Fix issues found by a review | `/review-implement reviews/REVIEW-foo.md` |
| Publish review results on a GitHub PR | `/review-post reviews/REVIEW-foo.md` |
| Update a PR review after fixes landed | `/review-update reviews/REVIEW-foo.md` |
| Get PR review comments into a local file for tracking | `/review-fetch 42` |
| Archive a review where all issues are resolved | `/review-cleanup reviews/REVIEW-foo.md` |
| Set up a fresh project with the `.agents/` structure | `/setup-project ./my-new-project` |

---

## Typical Workflows

### New Feature (Full Automation)

```bash
/begin-workflow specs/my-feature/
```

This runs the entire pipeline automatically: `plan` → `implement` → review loop (review-report → review-validate → review-implement → ... until clean) → `review-cleanup`.

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
| `/review-report` | `./reviews/REVIEW-{name}.md` |
| `/review-validate` | Updates `./reviews/REVIEW-{name}.md` |
| `/review-implement` | Code changes + updates `./reviews/REVIEW-{name}.md` |
| `/review-post` | Posts on GitHub PR |
| `/review-update` | Comments/resolutions on GitHub PR |
| `/review-fetch` | `./reviews/REVIEW-{name}-fetched.md` |
| `/review-cleanup` | Archives to `./reviews/archived/` |
