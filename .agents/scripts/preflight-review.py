"""Pre-flight check for review commands.

Checks scope (PR/branch/other), stale review, and unstaged changes.
Call before running review-report, review-verify, review-clarify, or review-validate.

Usage:
    uv run python .agents/scripts/preflight-review.py [--scope pr|branch|other] [--review-file <path>]

Options:
    --scope SCOPE      What scope to check:
                       - pr:      Fetches PR info, uses PR base for diff (recommended for PR reviews)
                       - branch:  Checks local vs remote, diffs against merge-base (recommended for local reviews)
                       - other:   Basic info only, agent asks user (default)
    --review-file      Path to the REVIEW-*.md file (for stale check).

In --scope pr mode, the script detects the PR from the current branch and provides
the base branch, changed files, and other PR context automatically.
In --scope branch mode, it checks local vs remote and diffs against merge-base.

If --review-file is provided, checks if the commit range in the report matches HEAD.
Always checks for unstaged changes.
Exits 0 if all clear, non-zero with warnings otherwise.
<EOF_DESC>
"""

import subprocess, sys, re, argparse, json
from pathlib import Path


def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except subprocess.CalledProcessError:
        return ""
    except Exception:
        return ""


def check_stale(review_file: str) -> list[str]:
    warnings = []
    if not review_file:
        return warnings
    p = Path(review_file)
    if not p.exists():
        warnings.append(f"[WARN] Review file not found: {review_file} — skipping stale check.")
        return warnings
    if p.is_dir():
        warnings.append(f"[WARN] Expected a review file but got a directory: {review_file} — skipping stale check.")
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
    """PR mode: detect PR, get base branch, changed files."""
    info = []
    branch = run(["git", "branch", "--show-current"])
    info.append(f"[INFO] Current branch: {branch}")

    # Detect PR
    pr_data = run(["gh", "pr", "list", "--head", branch, "--state", "open",
                    "--json", "number,headRefName,baseRefName,title", "--jq", ".[0]"])
    if not pr_data:
        info.append("[WARN] No open PR found for this branch. Falling back to branch scope.")
        return scope_branch()

    try:
        pr = json.loads(pr_data)
        info.append(f"[INFO] PR #{pr['number']}: {pr.get('title','')}")
        info.append(f"[INFO] PR base: {pr['baseRefName']}")
        info.append(f"[INFO] PR head: {pr['headRefName']}")

        # Get changed files in the PR
        files_out = run(["gh", "pr", "diff", str(pr['number']), "--name-only"])
        if files_out:
            files = [f for f in files_out.splitlines() if f.strip()]
            info.append(f"[INFO] {len(files)} file(s) changed in PR:")
            for f in files[:20]:  # limit to 20 files
                info.append(f"       {f}")
            if len(files) > 20:
                info.append(f"       ... and {len(files)-20} more")

        # Get diff base commit
        merge_base = run(["git", "merge-base", pr['baseRefName'], "HEAD"])
        if merge_base:
            info.append(f"[INFO] Diff base (merge-base): {merge_base}")
            info.append(f"[INFO] Diff range: {merge_base}...HEAD")
    except json.JSONDecodeError:
        info.append("[WARN] Could not parse PR data.")
    return info


def scope_branch() -> list[str]:
    """Branch mode: check local vs remote, ahead/behind, diff against merge-base."""
    info = []
    branch = run(["git", "branch", "--show-current"])
    info.append(f"[INFO] Current branch: {branch}")

    # Ahead/behind vs remote
    ahead = run(["git", "rev-list", "--count", f"origin/{branch}..HEAD"])
    behind = run(["git", "rev-list", "--count", f"HEAD..origin/{branch}"])
    ahead = int(ahead) if ahead else 0
    behind = int(behind) if behind else 0
    if ahead or behind:
        info.append(f"[INFO] {ahead} ahead, {behind} behind remote.")
    else:
        info.append("[INFO] Branch is up to date with remote.")

    # Diff against merge-base with main
    merge_base = run(["git", "merge-base", "main", "HEAD"])
    if merge_base:
        diff_files = run(["git", "diff", "--name-only", f"{merge_base}..HEAD"])
        if diff_files:
            files = [f for f in diff_files.splitlines() if f.strip()]
            info.append(f"[INFO] {len(files)} file(s) changed vs main:")
            for f in files[:20]:
                info.append(f"       {f}")
            if len(files) > 20:
                info.append(f"       ... and {len(files)-20} more")
        info.append(f"[INFO] Diff range: {merge_base}...HEAD")

    return info


def scope_other() -> list[str]:
    """Default: basic info, agent asks user for scope."""
    info = []
    branch = run(["git", "branch", "--show-current"])
    info.append(f"[INFO] Current branch: {branch}")
    info.append("[INFO] No scope specified. Use --scope pr or --scope branch for detailed scope info.")
    return info


def main():
    parser = argparse.ArgumentParser(description="Pre-flight check for review commands")
    parser.add_argument("--scope", choices=["pr", "branch", "other"], default="other",
                        help="Scope: pr (PR context), branch (local branch), other (default, ask user)")
    parser.add_argument("--review-file", type=str, default=None)
    args = parser.parse_args()

    warnings = []
    info_lines = []
    getattr(sys.stdout, 'reconfigure', lambda: None)()

    # Scope check
    if args.scope == "pr":
        info_lines.extend(scope_pr())
    elif args.scope == "branch":
        info_lines.extend(scope_branch())
    else:
        info_lines.extend(scope_other())

    # Stale review check
    if args.review_file:
        warnings.extend(check_stale(args.review_file))

    # Unstaged changes
    warnings.extend(check_unstaged())

    for line in info_lines:
        print(line)
    if warnings:
        for w in warnings:
            print(w)
        sys.exit(1)
    print("[OK] Pre-flight checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
