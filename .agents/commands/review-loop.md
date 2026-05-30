---
description: Review loop orchestrator — delegates each step to subagents with minimal interference
subtask: true
---

Run the review loop: review-report → review-validate → review-implement → review-verify → repeat until clean → review-archive.

**Query**: $1 (— specify what to review, scope, focus, or any custom prompt for review-report, e.g., "review src/my-sdk for security issues" or "src/my-subproject/")

---

## Role: Review Orchestrator

You are the **review orchestrator**. Your job is to follow the loop below, delegating **each step to a fresh subagent**. You do not load skills, read AGENTS.md yourself, or specify review directories — the subagents handle all of that. Minimal interference.

Each subagent command follows this format by default:

| Step | Command |
|------|---------|
| Review-Report | `run @.agents/commands/review-report.md <scope>` or `run @.agents/commands/review-report.md <user_prompt>` |
| Review-Validate | `run @.agents/commands/review-validate.md` |
| Review-Verify | `run @.agents/commands/review-verify.md` |
| Review-Archive | `run @.agents/commands/review-archive.md` |

---

## Initial Question

Ask the user for the review-report prompt/scope before starting the loop:

> "What should the review report scope be? (e.g., 'src/my-sdk' or 'review auth module for security')"

Once answered, the rest of the loop runs fully automated.

---

## Instructions

Enter the loop and follow these steps in order:

### Step 1: Review Report (Subagent)

Delegate to a fresh subagent using the user-provided prompt:

```
run @.agents/commands/review-report.md <user_prompt>
```

- If the review report returns **no OPEN issues** (clean) → proceed to **Step 6** (Archive).
- If the review report returns **OPEN issues** → proceed to **Step 2**.

### Step 2: Review Validate (Subagent)

Delegate to a fresh subagent:

```
run @.agents/commands/review-validate.md
```

### Step 3: Review Implement (Subagent) + Commit

Delegate to a fresh subagent:

```
run @.agents/commands/review-implement.md
```

After the subagent finishes, the orchestrator **commits the changes** locally:

```bash
git add -A && git commit -m "review: apply fixes from review cycle"
```

> **Important**: Do NOT push. This is a local commit only.

> **Early push optimization**: If the review report agent keeps flagging "unpushed commits" as an issue across cycles, the orchestrator may **squash all unpushed commits into one and push early** after this step (does NOT terminate the loop). See Step 7 for squash+push approach.

Proceed to **Step 4**.

### Step 4: Review Verify (Subagent)

Delegate to a fresh subagent:

```
run @.agents/commands/review-verify.md
```

- If **all issues are ADDRESSED** → proceed to **Step 5** → Step 1 (fresh review).
- If **issues are still OPEN** → go back to **Step 3** (Implement again).

### Step 5: Goto Step 1

After all issues are addressed and the inner fix loop exits, go back to **Step 1** for a fresh review report to check if fixes introduced new issues.

### Step 6: Review Archive (Subagent)

Only reached when Step 1 returns a clean report (no OPEN issues).

Delegate to a fresh subagent:

```
run @.agents/commands/review-archive.md
```

Proceed to **Step 7**.

### Step 7: Squash Unpushed Commits → Push → Terminate

Check for unpushed local commits:

```bash
git log @{u}..HEAD --oneline
```

If there are unpushed commits:
1. **Squash** all unpushed commits into a single commit using `git reset --soft @{u}` + `git commit`
2. **Push** with a normal `git push` (no force push)

> **Critical rule**: This must NOT require `--force` or `--force-with-lease`. If a force push would be needed, the agent is doing something wrong. In that case, do NOT push — abort and report the situation.

Once push succeeds, the review loop is complete and terminates.

> **Note on early push**: If the review report repeatedly flags "unpushed commits" as an issue, the orchestrator may apply this squash+push early (after Step 3) without terminating the loop. This silences the false-positive review finding so the loop can continue cleanly.

---

## Loop Flow Diagram

```
Step 1: Review Report
  ├── Has OPEN issues → Step 2
  └── No issues (clean) → Step 6

Step 2: Review Validate → Step 3

Step 3: Review Implement → git commit (NO PUSH) → Step 4
  └── (Early squash+push if review report flags unpushed commits)

Step 4: Review Verify
  ├── All ADDRESSED → Step 5 → Step 1 (fresh review)
  └── Still OPEN → Step 3 (fix again)

Step 5: Goto Step 1

Step 6: Review Archive → Step 7

Step 7: Squash unpushed commits → Push → Terminate
```

---

## Required Context

- Preflight: none (subagents handle their own preflights)
- Skills: none (subagents load their own skills)
- Rules: none (subagents load their own rules)
- Templates: none
- Mutates files: yes (orchestrator commits after review-implement)
- Mutates git history: yes (orchestrator commits and squashes)
- Mutates remote: yes (orchestrator pushes at Step 7 or early push)
- Requires user confirmation: yes (initial question for review-report prompt)

## Important

- Delegate **each step** to a **fresh subagent** — never do the work yourself.
- Wait for each subagent to complete before proceeding.
- Do **not** instruct subagents to read AGENTS.md — they handle that themselves.
- Do **not** specify review directories — subagents determine paths independently.
- Do **not** load skills for the review steps — subagents load their own.
- Use the minimal command format shown in the table above.
- The initial question is the **only** user interaction — the loop runs fully automated after that.
- The review-report prompt is entirely user-determined — pass it verbatim to the subagent.
- **After Step 3** (review-implement): orchestrator always commits the changes locally. Do NOT push.
- **Step 7**: Squash ALL unpushed commits into a single commit, then push normally. Must NOT require `--force`.
- **Early push optimization**: If the review report keeps flagging "unpushed commits" as an issue, squash+push early after the next Step 3 commit. This does NOT terminate the loop — the loop continues normally.
- If a squash+push would require force push, the agent is doing it wrong — abort and report.
