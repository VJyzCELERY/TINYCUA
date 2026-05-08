"""Pre-flight check for review commands.

Checks scope (PR/branch/other), stale review, and unstaged changes.
In --scope pr|branch mode with --init-review, pre-generates the review file header
with Commit Range pre-filled so agents don't need to figure it out.

Usage:
    uv run python .agents/scripts/preflight-review.py [--scope pr|branch|other] [--review-file <path>] [--init-review] [--review-name <name>]

Options:
    --scope SCOPE      pr (PR context), branch (local branch), other (default)
    --review-file      Path to REVIEW-*.md file (for stale check)
    --init-review      Pre-generate review file header with Commit Range
    --review-name      Name for the review file (defaults to branch name)

Exits 0 if all clear, non-zero with warnings.
With --init-review, also prints the review file path so the agent knows where to write.
<EOF_DESC>
"""

import subprocess, sys, re, argparse, json, datetime
from pathlib import Path


_commit_base = None


def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception:
        return ""


def check_stale(review_file: str) -> list[str]:
    warnings = []
    if not review_file:
        return warnings
    p = Path(review_file)
    if not p.exists():
        warnings.append(f"[WARN] Review file not found: {review_file}")
        return warnings
    if p.is_dir():
        warnings.append(f"[WARN] Expected a review file but got a directory: {review_file}")
        return warnings
    try:
        with open(review_file) as f:
            content = f.read()
        m = re.search(r'Commit Range:\s*([0-9a-f]+)\.\.\.([0-9a-f]+)', content)
        if not m:
            warnings.append("[WARN] No Commit Range in review header.")
            return warnings
        review_head = m.group(2)
        current_head = run(["git", "rev-parse", "HEAD"])
        if review_head != current_head:
            warnings.append("[WARN] Review is stale — HEAD has moved.")
            warnings.append(f"       Review was on: {review_head}")
            warnings.append(f"       Current HEAD:  {current_head}")
            for line in run(["git", "log", "--oneline", f"{review_head}..{current_head}"]).splitlines():
                warnings.append(f"       + {line}")
    except FileNotFoundError:
        warnings.append(f"[WARN] Review file not found: {review_file}")
    return warnings


def check_unstaged() -> list[str]:
    status = run(["git", "status", "--porcelain"])
    if status:
        lines = status.splitlines()
        return [f"[WARN] {len(lines)} unstaged/uncommitted file(s):"] + [f"       {l}" for l in lines]
    return []


def scope_pr() -> list[str]:
    global _commit_base
    info = []
    branch = run(["git", "branch", "--show-current"])
    info.append(f"[INFO] Current branch: {branch}")

    pr_data = run(["gh", "pr", "list", "--head", branch, "--state", "open",
                    "--json", "number,headRefName,baseRefName,title", "--jq", ".[0]"])
    if not pr_data:
        info.append("[WARN] No open PR found. Falling back to branch scope.")
        return scope_branch()

    try:
        pr = json.loads(pr_data)
        info.append(f"[INFO] PR #{pr['number']}: {pr.get('title','')}")
        info.append(f"[INFO] PR base: {pr['baseRefName']}")
        info.append(f"[INFO] PR head: {pr['headRefName']}")

        files_out = run(["gh", "pr", "diff", str(pr['number']), "--name-only"])
        if files_out:
            files = [f for f in files_out.splitlines() if f.strip()]
            info.append(f"[INFO] {len(files)} file(s) changed in PR:")
            for f in files[:20]:
                info.append(f"       {f}")
            if len(files) > 20:
                info.append(f"       ... and {len(files)-20} more")

        merge_base = run(["git", "merge-base", pr['baseRefName'], "HEAD"])
        if merge_base:
            _commit_base = merge_base
            info.append(f"[INFO] Diff base: {_commit_base}")
            info.append(f"[INFO] Commit Range: {_commit_base}...HEAD")
    except json.JSONDecodeError:
        info.append("[WARN] Could not parse PR data.")
    return info


def scope_branch() -> list[str]:
    global _commit_base
    info = []
    branch = run(["git", "branch", "--show-current"])
    info.append(f"[INFO] Current branch: {branch}")

    ahead = run(["git", "rev-list", "--count", f"origin/{branch}..HEAD"])
    behind = run(["git", "rev-list", "--count", f"HEAD..origin/{branch}"])
    ahead = int(ahead) if ahead else 0
    behind = int(behind) if behind else 0
    if ahead or behind:
        info.append(f"[INFO] {ahead} ahead, {behind} behind remote.")

    merge_base = run(["git", "merge-base", "main", "HEAD"])
    if merge_base:
        _commit_base = merge_base
        diff_files = run(["git", "diff", "--name-only", f"{merge_base}..HEAD"])
        if diff_files:
            files = [f for f in diff_files.splitlines() if f.strip()]
            info.append(f"[INFO] {len(files)} file(s) changed vs main:")
            for f in files[:20]:
                info.append(f"       {f}")
            if len(files) > 20:
                info.append(f"       ... and {len(files)-20} more")
        info.append(f"[INFO] Diff base: {_commit_base}")
        info.append(f"[INFO] Commit Range: {_commit_base}...HEAD")
    return info


def scope_other() -> list[str]:
    info = []
    branch = run(["git", "branch", "--show-current"])
    info.append(f"[INFO] Current branch: {branch}")
    info.append("[INFO] No scope specified. Use --scope pr or --scope branch for detailed scope info.")
    return info


def init_review(review_name: str, review_dir: str = "./reviews") -> str | None:
    """Generate a review file with pre-filled header. Returns the file path or None."""
    if not _commit_base:
        return None

    head_sha = run(["git", "rev-parse", "HEAD"])
    if not head_sha:
        return None

    rev_dir = Path(review_dir)
    rev_dir.mkdir(parents=True, exist_ok=True)
    rev_path = rev_dir / f"REVIEW-{review_name}.md"

    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    branch = run(["git", "branch", "--show-current"])

    header = f"""# Review Report: {review_name}

**Directory Reviewed**: [fill in]
**Review Date**: {date_str}
**Branch**: {branch}
**Scope**: [branch diff | PR #N | unscoped]
**Commit Range**: {_commit_base}...{head_sha}

---

## Summary

[Brief summary of what was reviewed]

- **Total Findings**: [N]
- **Critical Issues**: [N]
- **High Issues**: [N]
- **Medium Issues**: [N]
- **Low Issues**: [N]

---

## Findings

### [ISSUE-001] - [SEVERITY] - [Issue Name]

**Status**: OPEN

**Severity**: [CRITICAL | HIGH | MEDIUM | LOW]

[Description]

**Location**: [file:line]

**Why It Matters**:
[Impact]

**Suggested Fix**:
[Fix description]

**How to Validate**:
```bash
[command]
```

---

*Generated by preflight-review.py*
*Fill in findings and sections marked [fill in] or [N] above*
"""

    rev_path.write_text(header)
    return str(rev_path)


def main():
    parser = argparse.ArgumentParser(description="Pre-flight check for review commands")
    parser.add_argument("--scope", choices=["pr", "branch", "other"], default="other",
                        help="Scope: pr (PR), branch (local), other (default)")
    parser.add_argument("--review-file", type=str, default=None)
    parser.add_argument("--init-review", action="store_true",
                        help="Pre-generate review file header with Commit Range")
    parser.add_argument("--review-name", type=str, default=None,
                        help="Review name (defaults to branch name)")
    args = parser.parse_args()

    if args.review_file and args.init_review:
        print("[ERROR] --review-file and --init-review are mutually exclusive.", file=sys.stderr)
        print("[ERROR] Use --init-review for a NEW review (pre-generates header).", file=sys.stderr)
        print("[ERROR] Use --review-file to check an EXISTING review for staleness.", file=sys.stderr)
        sys.exit(1)

    warnings = []
    info_lines = []

    if args.scope == "pr":
        info_lines.extend(scope_pr())
    elif args.scope == "branch":
        info_lines.extend(scope_branch())
    else:
        info_lines.extend(scope_other())

    if args.review_file:
        warnings.extend(check_stale(args.review_file))

    warnings.extend(check_unstaged())

    for line in info_lines:
        print(line)

    # Init review if requested
    if args.init_review and _commit_base:
        name = args.review_name or run(["git", "branch", "--show-current"]) or "review"
        name = name.replace("/", "-").replace("_", "-")
        rev_path = init_review(name)
        if rev_path:
            print(f"[INFO] Review file initialized: {rev_path}")
            print(f"[INFO] Fill in the findings section and update [fill in] placeholders.")

    if warnings:
        for w in warnings:
            print(w)
        sys.exit(1)
    print("[OK] Pre-flight checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
