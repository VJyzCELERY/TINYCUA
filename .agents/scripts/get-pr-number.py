"""Detect PR number from current branch or return explicit PR number.

Usage:
    uv run python .agents/scripts/get-pr-number.py [pr-number-or-branch]

If no argument given, detects from current branch via `gh`.
Outputs PR number to stdout, exits with 0 if found, 1 if not.
"""

import subprocess
import sys


def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except subprocess.CalledProcessError:
        return ""
    except FileNotFoundError:
        return ""


def get_current_branch() -> str:
    return run(["git", "branch", "--show-current"])


def detect_pr_number(branch: str | None = None) -> str | None:
    if not branch:
        branch = get_current_branch()
    if not branch:
        return None
    return run([
        "gh", "pr", "list",
        "--head", branch,
        "--state", "open",
        "--json", "number",
        "--jq", ".[0].number"
    ]) or None


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        # If it looks like a number, use it directly
        if arg.isdigit():
            print(arg)
            sys.exit(0)
        # Otherwise treat as branch name
        pr = detect_pr_number(arg)
    else:
        pr = detect_pr_number()

    if pr:
        print(pr)
        sys.exit(0)
    else:
        print("No PR found for current branch.")
        sys.exit(1)


if __name__ == "__main__":
    main()
