import { tool } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import path from "path"

const runGh = (args: string[], worktree: string) => {
  const script = path.join(worktree, ".agents/scripts/gh.py")
  return execSync(`uv run python ${script} ${args.join(" ")}`, {
    cwd: worktree,
    encoding: "utf-8",
  }).trim()
}

export const gh_fetch = tool({
  description: "Fetch PR info, comments, or unresolved reviews from GitHub",
  args: {
    resource: tool.schema
      .enum(["pr", "comments", "unresolved", "url"])
      .describe("What to fetch: pr, comments, unresolved, url"),
    identifier: tool.schema.string().describe("PR number or URL"),
  },
  async execute(args, context) {
    return runGh(["fetch", args.resource, args.identifier], context.worktree)
  },
})

export const gh_post = tool({
  description: "Post a review, comment, reply, or inline comment on a PR",
  args: {
    type: tool.schema
      .enum(["review", "comment", "reply", "inline"])
      .describe("Type of post: review, comment, reply, inline"),
    pr: tool.schema.string().describe("PR number"),
    file: tool.schema.string().describe("Path to temp file with content"),
    event: tool.schema
      .string()
      .optional()
      .describe("Review event: REQUEST_CHANGES, APPROVE, COMMENT"),
    path: tool.schema.string().optional().describe("File path for inline comment"),
    line: tool.schema.number().optional().describe("Line number for inline comment"),
  },
  async execute(args, context) {
    const cmd = ["post", args.type, args.pr, args.file]
    if (args.event) cmd.push("--event", args.event)
    if (args.path) cmd.push("--path", args.path)
    if (args.line) cmd.push("--line", String(args.line))
    return runGh(cmd, context.worktree)
  },
})

export const gh_resolve = tool({
  description: "Resolve a PR review thread",
  args: {
    pr: tool.schema.string().describe("PR number"),
    commentId: tool.schema.string().describe("Comment ID to resolve"),
  },
  async execute(args, context) {
    return runGh(["resolve", args.pr, args.commentId], context.worktree)
  },
})

export const gh_create = tool({
  description: "Create a new GitHub PR",
  args: {
    title: tool.schema.string().describe("PR title in conventional commit format"),
    bodyFile: tool.schema.string().describe("Path to temp file with PR body"),
    head: tool.schema.string().optional().describe("Head branch (auto-detected if omitted)"),
    base: tool.schema.string().optional().describe("Base branch (auto-detected if omitted)"),
    draft: tool.schema.boolean().optional().describe("Create as draft PR"),
  },
  async execute(args, context) {
    const cmd = ["create", args.title, args.bodyFile]
    if (args.head) cmd.push("--head", args.head)
    if (args.base) cmd.push("--base", args.base)
    if (args.draft) cmd.push("--draft")
    return runGh(cmd, context.worktree)
  },
})

export const gh_update_body = tool({
  description: "Update a PR body",
  args: {
    pr: tool.schema.string().describe("PR number"),
    bodyFile: tool.schema.string().describe("Path to temp file with new body"),
  },
  async execute(args, context) {
    return runGh(["update", "body", args.pr, args.bodyFile], context.worktree)
  },
})

export const gh_update_title = tool({
  description: "Update a PR title",
  args: {
    pr: tool.schema.string().describe("PR number"),
    title: tool.schema.string().describe("New PR title"),
  },
  async execute(args, context) {
    return runGh(["update", "title", args.pr, args.title], context.worktree)
  },
})
