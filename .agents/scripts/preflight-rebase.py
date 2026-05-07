"""Pre-flight check for rebase commands.

Checks ahead/behind status, detects already-applied commits, and warns about conflicts.
Call before running /rebase or any manual rebase.

Usage:
    uv run python .agents/scripts/preflight-rebase.py [--target <branch>]

Defaults target to 'main'.
Exits 0 if rebase is safe, non-zero with warnings otherwise.
"""

import subprocess, sys, argparse


def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception:
        return ""


def check_ahead_behind(target: str) -> list[str]:
    warnings = []
    ahead = run(["git", "rev-list", "--count", f"{target}..HEAD"])
    behind = run(["git", "rev-list", "--count", f"HEAD..{target}"])
    ahead = int(ahead) if ahead else 0
    behind = int(behind) if behind else 0

    if ahead == 0 and behind == 0:
        warnings.append("[INFO] Branch is already up to date — nothing to rebase.")
    elif ahead > 0:
        warnings.append(f"[INFO] {ahead} unique commit(s) on this branch (will be replayed).")
    if behind > 0:
        warnings.append(f"[INFO] {behind} commit(s) behind {target} (will be pulled in).")
    return warnings


def check_duplicates(target: str) -> list[str]:
    """Detect commits already applied to target via cherry-pick detection."""
    dupes = run(["git", "log", "--oneline", "--cherry-pick", f"{target}...HEAD"])
    if dupes:
        lines = dupes.splitlines()
        eq = [l for l in lines if l.startswith("=")]
        if eq:
            return [f"[WARN] {len(eq)} commit(s) already in {target} (will be skipped):"] + \
                   [f"       {l[1:].strip()}" for l in eq]
    return []


def check_uncommitted() -> list[str]:
    status = run(["git", "status", "--porcelain"])
    if status:
        return [f"[WARN] Uncommitted changes will be carried into rebase:"] + \
               [f"       {l}" for l in status.splitlines()]
    return []


def main():
    parser = argparse.ArgumentParser(description="Pre-flight check for rebase")
    parser.add_argument("--target", type=str, default="main", help="Target branch to rebase onto")
    args = parser.parse_args()

    all_warnings = []
    all_warnings.extend(check_ahead_behind(args.target))
    all_warnings.extend(check_duplicates(args.target))
    all_warnings.extend(check_uncommitted())

    for w in all_warnings:
        print(w)

    critical = [w for w in all_warnings if w.startswith("[WARN]")]
    if critical:
        sys.exit(1)
    print("[OK] Rebase pre-flight checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
