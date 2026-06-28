"""Count token usage from tinycua stdout logs.

Parses `[<node>] usage: input_tokens=N output_tokens=N total_tokens=N`
lines from one or more log files (or stdin) and prints a terminal summary
with total input, total output, and total combined tokens, plus a
per-node breakdown.

Usage:
    uv run python count_tokens.py evaluation-results/tinycua/experiment-2/run_logs/stdout.txt
    cat evaluation-results/.../stdout.txt | uv run python count_tokens.py
    uv run python count_tokens.py evaluation-results/tinycua/experiment-*/run_logs/stdout.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

# Anchored, exact: matches only `[node] usage: input_tokens=N output_tokens=N
# total_tokens=N` lines. Everything else in the log (live-stream markers, tool
# results, agent reasoning) is silently skipped.
_USAGE_RE = re.compile(
    r"^\[(.+?)\] usage: input_tokens=(\d+) output_tokens=(\d+) total_tokens=(\d+)$"
)


def parse_log(lines: list[str]) -> dict:
    """Parse usage lines and return a summary dict.

    Args:
        lines: Iterable of log lines (the script reads files via this).

    Returns:
        Dict with keys: calls, input, output, combined (ints), and nodes
        (list of (name, calls, input, output, combined) tuples sorted by
        combined descending). Returns calls=0 if no usage lines found.
    """
    calls = 0
    total_in = 0
    total_out = 0
    total_combined = 0
    per_node: dict[str, dict[str, int]] = {}

    for line in lines:
        m = _USAGE_RE.match(line)
        if not m:
            continue
        node, in_t, out_t, comb_t = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        calls += 1
        total_in += in_t
        total_out += out_t
        total_combined += comb_t
        nd = per_node.setdefault(node, {"calls": 0, "input": 0, "output": 0, "combined": 0})
        nd["calls"] += 1
        nd["input"] += in_t
        nd["output"] += out_t
        nd["combined"] += comb_t

    nodes_sorted = sorted(
        ((name, d["calls"], d["input"], d["output"], d["combined"]) for name, d in per_node.items()),
        key=lambda x: x[4],
        reverse=True,
    )
    return {
        "calls": calls,
        "input": total_in,
        "output": total_out,
        "combined": total_combined,
        "nodes": nodes_sorted,
    }


def _fmt(n: int) -> str:
    """Format an int with thousands separators."""
    return f"{n:,}"


def print_block(header: str, summary: dict, *, by_node: bool = True) -> None:
    """Print one summary block to stdout."""
    print(header)
    if summary["calls"] == 0:
        print("  no usage lines found")
        return
    print(f"  LLM calls:        {_fmt(summary['calls'])}")
    print(f"  total input:      {_fmt(summary['input'])}")
    print(f"  total output:     {_fmt(summary['output'])}")
    print(f"  total combined:   {_fmt(summary['combined'])}")
    if by_node and summary["nodes"]:
        print("  by node:")
        for name, c, i, o, comb in summary["nodes"]:
            print(
                f"    {name:<18} {_fmt(c):>6} calls  "
                f"{_fmt(i):>10} in  / {_fmt(o):>8} out  / {_fmt(comb):>10} combined"
            )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "files",
        nargs="*",
        help="One or more stdout.txt paths. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "--no-by-node",
        action="store_true",
        help="Skip the per-node breakdown.",
    )
    args = parser.parse_args(argv)

    by_node = not args.no_by_node
    summaries: list[tuple[str, dict]] = []

    if args.files:
        for path in args.files:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    summary = parse_log(f)
            except OSError as exc:
                print(f"warning: cannot read {path}: {exc}", file=sys.stderr)
                continue
            summaries.append((path, summary))
    else:
        summary = parse_log(sys.stdin)
        summaries.append(("<stdin>", summary))

    if not summaries:
        return 1

    for header, summary in summaries:
        print_block(header, summary, by_node=by_node)
        print()

    # Grand total across multiple files.
    if len(summaries) > 1:
        grand = {
            "calls": sum(s["calls"] for _, s in summaries),
            "input": sum(s["input"] for _, s in summaries),
            "output": sum(s["output"] for _, s in summaries),
            "combined": sum(s["combined"] for _, s in summaries),
            "nodes": [],
        }
        print_block(f"TOTAL ({len(summaries)} files)", grand, by_node=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())