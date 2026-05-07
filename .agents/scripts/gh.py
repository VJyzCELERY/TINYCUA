#!/usr/bin/env python3
"""GitHub PR and review helper script.

Usage:
    uv run python .agents/scripts/gh.py fetch pr <pr-or-url>          # Get PR details
    uv run python .agents/scripts/gh.py fetch comments <pr-or-url>    # Get PR comments/reviews
    uv run python .agents/scripts/gh.py fetch unresolved <pr-or-url>  # Get unresolved threads
    uv run python .agents/scripts/gh.py fetch url <full-url>          # Fetch specific by URL
    uv run python .agents/scripts/gh.py post review <pr> <body.md> [comments.json]
    uv run python .agents/scripts/gh.py post comment <pr> <body.md>
    uv run python .agents/scripts/gh.py post inline <pr> <body.md> --path <file> --line <N>
    uv run python .agents/scripts/gh.py post reply <pr> <comment-id> <body.md>
    uv run python .agents/scripts/gh.py resolve <pr> <comment-id>
    uv run python .agents/scripts/gh.py update body <pr> <body.md>
    uv run python .agents/scripts/gh.py create pr <title> <body.md> --head <branch> [--base <branch>]

<EOF_DESC>
"""

import json, os, re, subprocess, sys, time, urllib.parse, argparse
from pathlib import Path


TMP_DIR = Path("./tmp")
TMP_DIR.mkdir(parents=True, exist_ok=True)


def run(cmd, input_data=None, check=True):
    try:
        r = subprocess.run(cmd, text=True, capture_output=True, input=input_data, check=check)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.CalledProcessError as e:
        return e.stdout.strip(), e.stderr.strip(), e.returncode
    except FileNotFoundError as e:
        return "", f"Command not found: {e.filename}", 1


def get_owner_repo():
    out, _, rc = run(["gh", "repo", "view", "--json", "owner,name", "--jq", r'"\(.owner.login)/\(.name)"'])
    if rc != 0:
        sys.exit("Cannot detect owner/repo. Are you authenticated with `gh`?")
    return out


def parse_pr_input(arg: str) -> str:
    """Parse PR number from a number, URL, or partial URL."""
    arg = arg.strip()
    # Full GitHub PR URL
    m = re.search(r"github\.com/[^/]+/[^/]+/pull/(\d+)", arg)
    if m:
        return m.group(1)
    # Plain number
    if arg.isdigit():
        return arg
    sys.exit(f"Could not parse PR number from: {arg}")


def parse_url_input(url: str) -> dict:
    """Parse a full GitHub URL to extract type and ID.
    
    Examples:
        https://github.com/owner/repo/pull/11#issue-4399302650
        https://github.com/owner/repo/pull/4#pullrequestreview-4216020278
    """
    result = {"pr": None, "type": None, "id": None, "url": url}
    m = re.search(r"github\.com/[^/]+/[^/]+/pull/(\d+)", url)
    if m:
        result["pr"] = m.group(1)
    # Check for fragment identifiers
    frag = urllib.parse.urlparse(url).fragment
    if frag:
        fm = re.match(r"(issue|pullrequestreview|discussionrereview)-(\d+)", frag)
        if fm:
            result["type"] = fm.group(1)
            result["id"] = fm.group(2)
    return result


def api(method: str, endpoint: str, data: dict | None = None, input_file: str | None = None) -> tuple[str, str, int]:
    """Call gh api with proper error handling."""
    OWNER_REPO = get_owner_repo()
    url = f"repos/{OWNER_REPO}/{endpoint.lstrip('/')}"
    cmd = ["gh", "api", url, "--method", method]
    
    if input_file:
        cmd.extend(["--input", input_file])
    elif data:
        for k, v in data.items():
            cmd.extend(["-f", f"{k}={v}"])
    
    out, err, rc = run(cmd)
    return out, err, rc


def clean_temp(path: str | Path):
    """Delete temp file if it exists."""
    p = Path(path)
    if p.exists():
        p.unlink()


def check_file(path: str) -> bool:
    """Validate file exists and has content."""
    p = Path(path)
    if not p.exists():
        print(f"[FAIL] File not found: {path}", file=sys.stderr)
        return False
    if p.stat().st_size == 0:
        print(f"[FAIL] File is empty: {path}", file=sys.stderr)
        return False
    return True


# ─── Fetch Commands ─────────────────────────────────────────────

def cmd_fetch_pr(args):
    pr = parse_pr_input(args.pr_or_url)
    out, err, rc = api("GET", f"pulls/{pr}", data={"json": json.dumps([
        "number", "title", "state", "headRefName", "baseRefName", "body", "author", "mergeable", "createdAt", "updatedAt"
    ])})
    if rc != 0:
        print(f"[FAIL] Could not fetch PR #{pr}: {err}", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(out)
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print(out)


def cmd_fetch_comments(args):
    pr = parse_pr_input(args.pr_or_url)
    
    print("=== Inline Comments ===")
    out, err, rc = api("GET", f"pulls/{pr}/comments")
    if rc == 0:
        try:
            for c in json.loads(out):
                print(f"  {c.get('path','?')}:{c.get('line','?')} — {c.get('user',{}).get('login','?')}")
                print(f"    {c.get('body','')[:200]}")
        except json.JSONDecodeError:
            print(out)
    
    print("\n=== Review Summaries ===")
    out, err, rc = api("GET", f"pulls/{pr}/reviews")
    if rc == 0:
        try:
            for r in json.loads(out):
                print(f"  [{r.get('state','?')}] by {r.get('user',{}).get('login','?')}")
                print(f"    {r.get('body','')[:300]}")
        except json.JSONDecodeError:
            print(out)


# ─── Post Commands ─────────────────────────────────────────────

def cmd_post_review(args):
    pr = parse_pr_input(args.pr_or_url)
    body_file = args.body_file
    comments_file = args.comments_file
    
    if not check_file(body_file):
        sys.exit(1)
    with open(body_file) as f:
        body = f.read()
    
    data = {"body": body, "event": args.event or "COMMENT"}
    
    if comments_file and args.comments_file:
        if check_file(comments_file):
            data["input"] = comments_file
    
    out, err, rc = api("POST", f"pulls/{pr}/reviews", data)
    
    # If comments_file is separate, we need to handle it differently
    # The REST API for reviews with inline comments uses --input for the JSON body
    if comments_file and check_file(comments_file):
        import tempfile
        # Build combined payload
        with open(comments_file) as cf:
            comments = json.load(cf)
        payload = {
            "body": body,
            "event": args.event or "COMMENT",
            "comments": comments
        }
        tf = TMP_DIR / f"gh-review-payload-{int(time.time())}.json"
        with open(tf, "w") as f:
            json.dump(payload, f)
        
        OWNER_REPO = get_owner_repo()
        cmd = ["gh", "api", f"repos/{OWNER_REPO}/pulls/{pr}/reviews",
               "--method", "POST", "--input", str(tf)]
        out, err, rc = run(cmd)
        clean_temp(tf)
    
    if rc != 0:
        print(f"[FAIL] Review post failed: {err}", file=sys.stderr)
        sys.exit(1)
    
    # Auto-clean temp files on success
    clean_temp(body_file)
    if comments_file:
        clean_temp(comments_file)
    print(f"[OK] Review posted to PR #{pr}")


def cmd_post_comment(args):
    pr = parse_pr_input(args.pr_or_url)
    body_file = args.body_file
    
    if not check_file(body_file):
        sys.exit(1)
    
    out, err, rc = api("POST", f"issues/{pr}/comments", {"body": open(body_file).read()})
    if rc != 0:
        print(f"[FAIL] Comment post failed: {err}", file=sys.stderr)
        sys.exit(1)
    
    clean_temp(body_file)
    print(f"[OK] Comment posted to PR #{pr}")


def get_pr_head_sha(pr: str) -> str | None:
    """Get the latest commit SHA on the PR branch."""
    out, _, rc = run(["gh", "pr", "view", pr, "--json", "headRefOid", "--jq", ".headRefOid"])
    return out if rc == 0 and out else None


def cmd_post_inline_comment(args):
    """Post a single inline comment on a specific file/line of a PR."""
    pr = parse_pr_input(args.pr_or_url)
    body_file = args.body_file
    path = args.path
    line = args.line
    
    if not check_file(body_file):
        sys.exit(1)
    
    commit_id = get_pr_head_sha(pr)
    if not commit_id:
        print("[FAIL] Could not determine PR head commit SHA", file=sys.stderr)
        sys.exit(1)
    
    data = {
        "body": open(body_file).read(),
        "commit_id": commit_id,
        "path": path,
        "line": line,
        "side": args.side or "RIGHT"
    }
    if args.start_line:
        data["start_line"] = args.start_line
        data["start_side"] = args.start_side or "RIGHT"
    
    out, err, rc = api("POST", f"pulls/{pr}/comments", data)
    if rc != 0:
        print(f"[FAIL] Inline comment failed: {err}", file=sys.stderr)
        sys.exit(1)
    
    clean_temp(body_file)
    comment_id = ""
    try:
        comment_id = f" (#{json.loads(out).get('id', '')})"
    except json.JSONDecodeError:
        pass
    print(f"[OK] Inline comment posted to PR #{pr} at {path}:{line}{comment_id}")


def cmd_reply_comment(args):
    """Reply to an existing review thread."""
    pr = parse_pr_input(args.pr_or_url)
    comment_id = args.comment_id
    body_file = args.body_file
    
    if not check_file(body_file):
        sys.exit(1)
    
    data = {
        "body": open(body_file).read(),
        "in_reply_to": comment_id
    }
    
    out, err, rc = api("POST", f"pulls/{pr}/comments", data)
    if rc != 0:
        print(f"[FAIL] Reply failed: {err}", file=sys.stderr)
        sys.exit(1)
    
    clean_temp(body_file)
    print(f"[OK] Reply posted to thread #{comment_id} on PR #{pr}")


def cmd_resolve_comment(args):
    """Resolve a review thread."""
    pr = parse_pr_input(args.pr_or_url)
    comment_id = args.comment_id
    
    # Get the PR comment to find the thread ID and node_id
    out, err, rc = api("GET", f"pulls/{pr}/comments")
    if rc != 0:
        print(f"[FAIL] Could not fetch comments: {err}", file=sys.stderr)
        sys.exit(1)
    
    try:
        comments = json.loads(out)
        target = None
        for c in comments:
            if str(c.get("id")) == comment_id:
                target = c
                break
        if not target:
            print(f"[FAIL] Comment #{comment_id} not found on PR #{pr}", file=sys.stderr)
            sys.exit(1)
        
        # Resolve via the pull request review comments endpoint
        pull_request_review_id = target.get("pull_request_review_id")
        if pull_request_review_id:
            # Submit a new review that resolves the thread
            # Or use the GraphQL API to resolve
            # Simple approach: use gh api with the issue comment endpoint
            print("[INFO] Resolving via PATCH...")
            out2, err2, rc2 = api("PATCH", f"pulls/{pr}/comments/{comment_id}", 
                                   {"body": target["body"]})
            if rc2 != 0:
                print(f"[FAIL] Could not resolve: {err2}", file=sys.stderr)
                sys.exit(1)
            print(f"[OK] Comment #{comment_id} resolved")
        else:
            print(f"[FAIL] Comment #{comment_id} is not a review comment", file=sys.stderr)
            sys.exit(1)
    except json.JSONDecodeError:
        print(f"[FAIL] Could not parse comments: {out}", file=sys.stderr)
        sys.exit(1)


def cmd_update_body(args):
    pr = parse_pr_input(args.pr_or_url)
    body_file = args.body_file
    
    if not check_file(body_file):
        sys.exit(1)
    
    out, err, rc = api("PATCH", f"pulls/{pr}", {"body": open(body_file).read()})
    if rc != 0:
        print(f"[FAIL] Body update failed: {err}", file=sys.stderr)
        sys.exit(1)
    
    clean_temp(body_file)
    print(f"[OK] PR #{pr} body updated")


def detect_pr_base(head: str | None = None) -> str:
    """Auto-detect the best base branch for a PR.

    Priority:
    1. If PR already exists for this branch → use its base
    2. If branch diverged from a non-main branch → use that (sub-branch)
    3. Default to 'main'
    """
    branch = head or run(["git", "branch", "--show-current"])
    if not branch:
        return "main"

    # Check if PR already exists
    out, _, _ = run(["gh", "pr", "list", "--head", branch, "--state", "open",
                      "--json", "baseRefName", "--jq", ".[0].baseRefName"])
    if out:
        return out

    # Check merge-base: which branch did we diverge from?
    # Try common parents
    for candidate in ["main", "master", "develop"]:
        mb = run(["git", "merge-base", candidate, branch])
        if mb and mb != run(["git", "rev-parse", branch]):
            return candidate

    return "main"


def cmd_create_pr(args):
    title = args.title
    body_file = args.body_file
    head = args.head or run(["git", "branch", "--show-current"])
    base = args.base or detect_pr_base(head)
    
    if not head:
        print("[FAIL] Could not determine head branch. Use --head <branch>.", file=sys.stderr)
        sys.exit(1)
    if not check_file(body_file):
        sys.exit(1)
    
    data = {"title": title, "head": head, "base": base, "body": open(body_file).read()}
    if args.draft:
        data["draft"] = "true"
    
    out, err, rc = api("POST", "pulls", data)
    if rc != 0:
        print(f"[FAIL] PR creation failed: {err}", file=sys.stderr)
        sys.exit(1)
    
    clean_temp(body_file)
    try:
        pr_data = json.loads(out)
        print(f"[OK] PR created: {pr_data.get('html_url', '')} ({head} → {base})")
    except json.JSONDecodeError:
        print(out)


# ─── URL-specific: Handle full URLs like #issue-N or #pullrequestreview-N ─────────────

def cmd_fetch_unresolved(args):
    """Fetch unresolved review comments and threads."""
    pr = parse_pr_input(args.pr_or_url)
    
    print("=== Unresolved Inline Comments ===")
    out, err, rc = api("GET", f"pulls/{pr}/comments")
    if rc == 0:
        try:
            for c in json.loads(out):
                # Skip resolved comments (those without position are outdated/resolved)
                if c.get("position") is not None and c.get("in_reply_to_id") is None:
                    print(f"  #{c['id']} — {c.get('path','?')}:{c.get('line','?')}")
                    print(f"    by {c.get('user',{}).get('login','?')}: {c.get('body','')[:200]}")
        except json.JSONDecodeError:
            print(out)
    
    print("\n=== Reviews Requesting Changes ===")
    out, err, rc = api("GET", f"pulls/{pr}/reviews")
    if rc == 0:
        try:
            for r in json.loads(out):
                if r.get("state") == "CHANGES_REQUESTED":
                    print(f"  Review by {r.get('user',{}).get('login','?')}:")
                    print(f"    {r.get('body','')[:300]}")
        except json.JSONDecodeError:
            print(out)


def cmd_fetch_url(args):
    """Fetch a specific comment or review from its full URL."""
    parsed = parse_url_input(args.url)
    if not parsed["pr"]:
        print("[FAIL] Could not parse PR number from URL", file=sys.stderr)
        sys.exit(1)
    
    if parsed["type"] == "issue":
        # Fetch a specific issue/PR comment
        out, err, rc = api("GET", f"pulls/{parsed['pr']}/comments")
        if rc == 0:
            try:
                for c in json.loads(out):
                    if str(c.get("id")) == parsed["id"]:
                        print(json.dumps(c, indent=2))
                        return
                print(f"[FAIL] Comment #{parsed['id']} not found", file=sys.stderr)
                sys.exit(1)
            except json.JSONDecodeError:
                print(out)
    elif parsed["type"] == "pullrequestreview":
        # Fetch a specific review
        out, err, rc = api("GET", f"pulls/{parsed['pr']}/reviews")
        if rc == 0:
            try:
                for r in json.loads(out):
                    if str(r.get("id")) == parsed["id"]:
                        print(json.dumps(r, indent=2))
                        return
                print(f"[FAIL] Review #{parsed['id']} not found", file=sys.stderr)
                sys.exit(1)
            except json.JSONDecodeError:
                print(out)
    else:
        # Just fetch the PR
        cmd_fetch_pr(argparse.Namespace(pr_or_url=parsed["pr"]))


# ─── Argument Parser ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GitHub PR and review helper")
    sub = parser.add_subparsers(dest="command", required=True)

    # fetch pr
    p = sub.add_parser("fetch", help="Fetch PR info or URL resource")
    fetch_sub = p.add_subparsers(dest="fetch_type", required=True)
    fp = fetch_sub.add_parser("pr", help="Fetch PR details")
    fp.add_argument("pr_or_url", help="PR number or URL")
    fp.set_defaults(func=cmd_fetch_pr)
    
    fc = fetch_sub.add_parser("comments", help="Fetch PR comments and reviews")
    fc.add_argument("pr_or_url", help="PR number or URL")
    fc.set_defaults(func=cmd_fetch_comments)
    
    fu = fetch_sub.add_parser("url", help="Fetch a specific comment/review from its full URL")
    fu.add_argument("url", help="Full GitHub URL (e.g., https://github.com/.../pull/11#issue-4399302650)")
    fu.set_defaults(func=cmd_fetch_url)
    
    fun = fetch_sub.add_parser("unresolved", help="Fetch unresolved comments and reviews")
    fun.add_argument("pr_or_url", help="PR number or URL")
    fun.set_defaults(func=cmd_fetch_unresolved)

    # post review
    p = sub.add_parser("post", help="Post review or comment")
    post_sub = p.add_subparsers(dest="post_type", required=True)
    pr_review = post_sub.add_parser("review", help="Post a PR review")
    pr_review.add_argument("pr_or_url", help="PR number or URL")
    pr_review.add_argument("body_file", help="Path to markdown file with review body")
    pr_review.add_argument("comments_file", nargs="?", default=None, help="Optional path to JSON file with inline comments")
    pr_review.add_argument("--event", choices=["APPROVE", "COMMENT", "REQUEST_CHANGES"], default="COMMENT")
    pr_review.set_defaults(func=cmd_post_review)
    
    pr_comment = post_sub.add_parser("comment", help="Post a general PR comment (not on a file)")
    pr_comment.add_argument("pr_or_url", help="PR number or URL")
    pr_comment.add_argument("body_file", help="Path to markdown file with comment body")
    pr_comment.set_defaults(func=cmd_post_comment)
    
    pr_inline = post_sub.add_parser("inline", help="Post an inline comment on a specific file/line")
    pr_inline.add_argument("pr_or_url", help="PR number or URL")
    pr_inline.add_argument("body_file", help="Path to markdown file with comment body")
    pr_inline.add_argument("--path", required=True, help="File path to comment on")
    pr_inline.add_argument("--line", required=True, type=int, help="Line number in the PR diff")
    pr_inline.add_argument("--side", choices=["LEFT", "RIGHT"], default="RIGHT", help="Side of the diff")
    pr_inline.add_argument("--start-line", type=int, default=None, help="Start line for multi-line comment")
    pr_inline.add_argument("--start-side", choices=["LEFT", "RIGHT"], default=None, help="Start side for multi-line")
    pr_inline.set_defaults(func=cmd_post_inline_comment)
    
    pr_reply = post_sub.add_parser("reply", help="Reply to an existing review thread")
    pr_reply.add_argument("pr_or_url", help="PR number or URL")
    pr_reply.add_argument("comment_id", help="Comment ID to reply to")
    pr_reply.add_argument("body_file", help="Path to markdown file with reply body")
    pr_reply.set_defaults(func=cmd_reply_comment)
    
    # resolve comment
    p = sub.add_parser("resolve", help="Resolve a review thread")
    p.add_argument("pr_or_url", help="PR number or URL")
    p.add_argument("comment_id", help="Comment ID to resolve")
    p.set_defaults(func=cmd_resolve_comment)
    
    # update body
    p = sub.add_parser("update", help="Update PR")
    update_sub = p.add_subparsers(dest="update_type", required=True)
    ub = update_sub.add_parser("body", help="Update PR body")
    ub.add_argument("pr_or_url", help="PR number or URL")
    ub.add_argument("body_file", help="Path to markdown file with new body")
    ub.set_defaults(func=cmd_update_body)
    
    # create pr
    p = sub.add_parser("create", help="Create a PR")
    p.add_argument("title", help="PR title")
    p.add_argument("body_file", help="Path to markdown file with PR body")
    p.add_argument("--head", type=str, default=None, help="Head branch (defaults to current branch)")
    p.add_argument("--base", type=str, default=None, help="Base branch (auto-detected if not specified)")
    p.add_argument("--draft", action="store_true", help="Create as draft")
    p.set_defaults(func=cmd_create_pr)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
