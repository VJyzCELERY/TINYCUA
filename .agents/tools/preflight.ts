import { tool } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import path from "path"

const runScript = (script: string, args: string[], worktree: string) => {
  const spath = path.join(worktree, `.agents/scripts/${script}`)
  return execSync(`uv run python ${spath} ${args.join(" ")}`, {
    cwd: worktree,
    encoding: "utf-8",
  }).trim()
}

export const preflight_start = tool({
  description: "Detect OS and establish project boundary at session start",
  args: {},
  async execute(_args, context) {
    return runScript("preflight-start.py", [], context.worktree)
  },
})

export const preflight_review = tool({
  description: "Check review scope, staleness, and unstaged changes before reviewing",
  args: {
    scope: tool.schema
      .enum(["pr", "branch", "other"])
      .optional()
      .describe("Scope: pr, branch, or other"),
    reviewFile: tool.schema
      .string()
      .optional()
      .describe("Path to existing review file for staleness check"),
    initReview: tool.schema
      .boolean()
      .optional()
      .describe("Pre-generate review file header with Commit Range"),
    reviewName: tool.schema
      .string()
      .optional()
      .describe("Name for the review file (defaults to branch name)"),
  },
  async execute(args, context) {
    const cmd = []
    if (args.scope) cmd.push("--scope", args.scope)
    if (args.reviewFile) cmd.push("--review-file", args.reviewFile)
    if (args.initReview) cmd.push("--init-review")
    if (args.reviewName) cmd.push("--review-name", args.reviewName)
    return runScript("preflight-review.py", cmd, context.worktree)
  },
})

export const preflight_pr = tool({
  description: "Detect PR number from current branch or validate a given PR number",
  args: {
    pr: tool.schema
      .string()
      .optional()
      .describe("PR number, branch name, or URL (omit for auto-detect)"),
  },
  async execute(args, context) {
    const cmd = args.pr ? [args.pr] : []
    return runScript("preflight-pr.py", cmd, context.worktree)
  },
})

export const preflight_rebase = tool({
  description: "Check rebase safety — detect conflicts and list commits",
  args: {
    target: tool.schema.string().describe("Target branch (e.g., main)"),
    listCommits: tool.schema
      .boolean()
      .optional()
      .describe("List commits that will be rebased"),
  },
  async execute(args, context) {
    const cmd = ["--target", args.target]
    if (args.listCommits) cmd.push("--list-commits")
    return runScript("preflight-rebase.py", cmd, context.worktree)
  },
})
