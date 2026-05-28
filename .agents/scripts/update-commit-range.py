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

    file_path = Path(sys.argv[1])
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

    # Replace the Commit Range line — handle both short and full SHA formats
    new_content = re.sub(
        r'^\*\*Commit Range\*\*:\s*\S+',
        f'**Commit Range**: {new_range}',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    if new_content == content:
        print(f"[WARN] No '**Commit Range**' line found in {file_path}", file=sys.stderr)
        # Add it after **Reviewer** or **Review Focus** line
        new_content = re.sub(
            r'^(\*\*Review(?:er|Focus| Date| Type).*\n)',
            f'\\1**Commit Range**: {new_range}\n',
            content,
            count=1,
            flags=re.MULTILINE,
        )
        if new_content == content:
            print("[FAIL] Could not find a place to insert Commit Range", file=sys.stderr)
            sys.exit(1)

    file_path.write_text(new_content, encoding="utf-8")
    print(f"[OK] Commit Range updated to {new_range} in {file_path}")


if __name__ == "__main__":
    main()
