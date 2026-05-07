"""Pre-flight check for review commands.

Checks: stale review (commit range mismatch), unstaged changes, and scope alignment.
Call this before running review-report, review-verify, review-clarify, or review-validate.

Usage:
    uv run python .agents/scripts/preflight-review.py [--mode validate|verify|report] [--review-file <path>]

Options:
    --mode MODE       What the review is about to do (validate, verify, or report).
                      Different modes check different conditions.
    --review-file     Path to the REVIEW-*.md file (for stale check).

If --review-file is provided, checks if the commit range in the report matches HEAD.
Always checks for unstaged changes.
Exits 0 if all clear, non-zero with warnings otherwise.
<EOF_DESC>
"""

import subprocess, sys, re, argparse


def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception:
        return ""


def check_stale(review_file: str) -> list[str]:
    warnings = []
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


def check_scope():
    """Basic scope info for review context."""
    branch = run(["git", "branch", "--show-current"])
    info = [f"[INFO] Current branch: {branch}"]
    # Check if ahead/behind main
    behind = run(["git", "rev-list", "--count", "main..HEAD@\{u\}"]) if branch != "main" else "0"
    if behind and behind != "0":
        info.append(f"[INFO] Branch is {behind} commit(s) behind remote.")
    return info


def main():
    parser = argparse.ArgumentParser(description="Pre-flight check for review commands")
    parser.add_argument("--mode", choices=["validate", "verify", "report"], default="report")
    parser.add_argument("--review-file", type=str, default=None)
    args = parser.parse_args()

    warnings = []
    info_lines = []

    if args.review_file:
        warnings.extend(check_stale(args.review_file))
    info_lines.extend(check_scope())
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
