"""Pre-flight checks for review commands: stale review detection + unstaged changes.

Usage:
    uv run python .agents/scripts/check-preflight.py <review-file>

Exits with 0 if all checks pass, non-zero if warnings found.
Outputs structured messages to stdout.
"""

import subprocess
import sys
import re
from pathlib import Path


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def check_stale_review(review_file: str) -> list[str]:
    warnings = []
    try:
        with open(review_file) as f:
            content = f.read()
        match = re.search(r'Commit Range:\s*([0-9a-f]+)\.\.\.([0-9a-f]+)', content)
        if not match:
            warnings.append("No Commit Range found in review header — cannot check staleness.")
            return warnings
        review_head = match.group(2)
        current_head = run(["git", "rev-parse", "HEAD"])
        if review_head != current_head:
            warnings.append(f"⚠ Review is stale — HEAD has moved since review was created.")
            warnings.append(f"  Review was on: {review_head}")
            warnings.append(f"  Current HEAD:  {current_head}")
            new_commits = run(["git", "log", "--oneline", f"{review_head}..{current_head}"])
            for line in new_commits.splitlines():
                warnings.append(f"  + {line}")
    except FileNotFoundError:
        warnings.append(f"Review file not found: {review_file}")
    except Exception as e:
        warnings.append(f"Error checking staleness: {e}")
    return warnings


def check_unstaged() -> list[str]:
    warnings = []
    try:
        status = run(["git", "status", "--porcelain"])
        if status:
            warnings.append("⚠ There are unstaged or uncommitted changes in the working tree.")
            for line in status.splitlines():
                warnings.append(f"  {line}")
    except Exception as e:
        warnings.append(f"Error checking unstaged changes: {e}")
    return warnings


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python .agents/scripts/check-preflight.py <review-file>")
        sys.exit(1)

    review_file = sys.argv[1]
    all_warnings = []
    all_warnings.extend(check_stale_review(review_file))
    all_warnings.extend(check_unstaged())

    if all_warnings:
        for w in all_warnings:
            print(w)
        sys.exit(1)
    else:
        print("✅ Pre-flight checks passed — review is up to date, working tree is clean.")
        sys.exit(0)


if __name__ == "__main__":
    main()
