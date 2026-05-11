"""Update the **Commit Range** line in a review report to the current PR head.

Usage:
    uv run python .agents/scripts/update-commit-range.py <path/to/review-file.md>

Reads the review file, detects the PR from the current branch, fetches the full
BASE and HEAD SHAs, then replaces the **Commit Range** line in place.
<EOF_DESC>
"""

import re
import sys
import subprocess
from pathlib import Path

import repo_guard


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return r.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python .agents/scripts/update-commit-range.py <review-file.md>", file=sys.stderr)
        sys.exit(1)

    file_path = repo_guard.assert_inside_repo(sys.argv[1])
    if not file_path.exists():
        print(f"[FAIL] File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    content = file_path.read_text(encoding="utf-8")

    # Detect PR from current branch
    pr_number = run(["gh", "pr", "view", "--json", "number", "--jq", ".number"])
    if not pr_number:
        print("[FAIL] No open PR for current branch", file=sys.stderr)
        sys.exit(1)

    # Fetch full SHAs — headRefOid is available directly, base SHA needs API
    head_sha = run(["gh", "pr", "view", pr_number, "--json", "headRefOid", "--jq", ".headRefOid"])
    owner_repo = run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    if not owner_repo:
        print("[FAIL] Could not detect repository", file=sys.stderr)
        sys.exit(1)
    base_sha = run(["gh", "api", f"repos/{owner_repo}/pulls/{pr_number}", "--jq", ".base.sha"])

    if not head_sha or not base_sha:
        print(f"[FAIL] Could not fetch SHAs for PR #{pr_number}", file=sys.stderr)
        print(f"       head={head_sha!r} base={base_sha!r}", file=sys.stderr)
        sys.exit(1)

    # Validate SHAs look correct (40 hex chars)
    if not re.match(r'^[0-9a-f]{40}$', head_sha) or not re.match(r'^[0-9a-f]{40}$', base_sha):
        print(f"[FAIL] SHAs are not full 40-char hex: base={base_sha} head={head_sha}", file=sys.stderr)
        sys.exit(1)

    new_range = f"{base_sha}...{head_sha}"

    # Check if already up to date — extract current commit range from file
    existing = re.search(r'^\*\*Commit Range\*\*:\s*(\S+)', content, re.MULTILINE)
    if existing and existing.group(1) == new_range:
        print(f"[OK] Commit Range already up to date: {new_range}")
        sys.exit(0)

    # Remove all existing **Commit Range** lines (handles duplicates)
    cleaned = re.sub(r'^\*\*Commit Range\*\*:\s*\S+\s*\n?', '', content, flags=re.MULTILINE)

    # Find the right insertion point — after **Reviewer**, **Review Focus**, **Review Date**, or **Review Type**
    inserted = re.sub(
        r'^(\*\*Review(?:er|Focus| Date| Type).*\n)',
        f'\\1**Commit Range**: {new_range}\n',
        cleaned,
        count=1,
        flags=re.MULTILINE,
    )

    if inserted == cleaned:
        # Fallback: insert at the top, after the title
        inserted = re.sub(
            r'^(# .*\n)',
            f'\\1**Commit Range**: {new_range}\n',
            cleaned,
            count=1,
        )

    if inserted == cleaned:
        print("[FAIL] Could not find a place to insert Commit Range", file=sys.stderr)
        sys.exit(1)

    file_path.write_text(inserted, encoding="utf-8")
    print(f"[OK] Commit Range updated to {new_range} in {file_path}")


if __name__ == "__main__":
    main()
