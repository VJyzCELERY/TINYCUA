"""Side-by-side comparison of two benchmark result sets (TinyCUA vs Hermes).

Produces a comparison dict with per-task score deltas and aggregate
statistics, written as comparison.json.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def compare_results(tinycua_data: dict[str, Any], hermes_data: dict[str, Any]) -> dict[str, Any]:
    """Compare two benchmark result sets side-by-side.

    Merges per-task scores, computes deltas, and produces aggregate
    statistics comparing TinyCUA and Hermes agent performance.

    Args:
        tinycua_data: Summary dict from TinyCUA benchmark run
            (with 'summary' and 'tasks' keys).
        hermes_data: Summary dict from Hermes benchmark run
            (with 'summary' and 'tasks' keys).

    Returns:
        Comparison dict with keys:
            - agent_a: TinyCUA summary metadata
            - agent_b: Hermes summary metadata
            - per_task_comparison: List of per-task comparisons
            - aggregate_delta: Overall score delta (agent_b - agent_a)
            - category_deltas: Per-category score deltas
    """
    tinycua_tasks = _build_task_map(tinycua_data.get("tasks", []))
    hermes_tasks = _build_task_map(hermes_data.get("tasks", []))

    all_task_ids = sorted(set(tinycua_tasks.keys()) | set(hermes_tasks.keys()))

    per_task: list[dict[str, Any]] = []
    tinycua_scores: list[float] = []
    hermes_scores: list[float] = []

    for task_id in all_task_ids:
        t = tinycua_tasks.get(task_id, {})
        h = hermes_tasks.get(task_id, {})

        t_score = t.get("score")
        h_score = h.get("score")

        if t_score is not None:
            tinycua_scores.append(float(t_score))
        if h_score is not None:
            hermes_scores.append(float(h_score))

        delta = None
        if t_score is not None and h_score is not None:
            delta = round(float(h_score) - float(t_score), 4)

        per_task.append({
            "task_id": task_id,
            "tinycua_score": t_score,
            "tinycua_status": t.get("status"),
            "tinycua_elapsed": t.get("elapsed_time"),
            "hermes_score": h_score,
            "hermes_status": h.get("status"),
            "hermes_elapsed": h.get("elapsed_time"),
            "delta": delta,
        })

    avg_tinycua = _safe_mean(tinycua_scores)
    avg_hermes = _safe_mean(hermes_scores)
    aggregate_delta = round(avg_hermes - avg_tinycua, 4) if (
        avg_tinycua is not None and avg_hermes is not None
    ) else None

    # Per-category deltas
    category_deltas: dict[str, dict[str, Any]] = {}
    for entry in per_task:
        cat = tinycua_tasks.get(entry["task_id"], {}).get("task_category", "Uncategorized")
        if cat not in category_deltas:
            category_deltas[cat] = {
                "tinycua_scores": [],
                "hermes_scores": [],
                "count": 0,
            }
        category_deltas[cat]["count"] += 1
        if entry["tinycua_score"] is not None:
            category_deltas[cat]["tinycua_scores"].append(entry["tinycua_score"])
        if entry["hermes_score"] is not None:
            category_deltas[cat]["hermes_scores"].append(entry["hermes_score"])

    for cat in category_deltas:
        ts = category_deltas[cat]["tinycua_scores"]
        hs = category_deltas[cat]["hermes_scores"]
        avg_t = _safe_mean(ts)
        avg_h = _safe_mean(hs)
        category_deltas[cat] = {
            "count": category_deltas[cat]["count"],
            "tinycua_average": avg_t,
            "hermes_average": avg_h,
            "delta": round(avg_h - avg_t, 4) if (
                avg_t is not None and avg_h is not None
            ) else None,
        }

    return {
        "agent_a": {
            "name": "tinycua",
            "average_score": tinycua_data.get("summary", {}).get("average_score"),
            "successful_tasks": tinycua_data.get("summary", {}).get("successful_tasks"),
            "total_tasks": tinycua_data.get("summary", {}).get("total_tasks"),
        },
        "agent_b": {
            "name": "hermes",
            "average_score": hermes_data.get("summary", {}).get("average_score"),
            "successful_tasks": hermes_data.get("summary", {}).get("successful_tasks"),
            "total_tasks": hermes_data.get("summary", {}).get("total_tasks"),
        },
        "per_task_comparison": per_task,
        "aggregate_delta": aggregate_delta,
        "category_deltas": category_deltas,
    }


def _build_task_map(tasks: list[dict]) -> dict[str, dict]:
    """Build a task_id -> task dict from a list of task results."""
    return {t["task_id"]: t for t in tasks if "task_id" in t}


def _safe_mean(values: list[float]) -> float | None:
    """Compute mean, returning None for empty lists."""
    if not values:
        return None
    return sum(values) / len(values)


def _load_json(path: str) -> dict:
    """Load and parse a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file cannot be parsed as JSON.
    """
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"Result file not found: {path}")
    try:
        with open(filepath) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Failed to parse {path}: {exc}") from exc


def main() -> None:
    """CLI entry point: compare two summary_all.json files.

    Usage:
        python -m hermes_benchmark.compare_results <tinycua_results.json> <hermes_results.json> [--output comparison.json]
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare TinyCUA and Hermes benchmark results side-by-side."
    )
    parser.add_argument("tinycua_file", help="Path to TinyCUA summary_all.json")
    parser.add_argument("hermes_file", help="Path to Hermes summary_all.json")
    parser.add_argument(
        "--output",
        default="comparison.json",
        help="Output path for comparison JSON (default: comparison.json).",
    )
    args = parser.parse_args()

    try:
        tinycua_data = _load_json(args.tinycua_file)
        hermes_data = _load_json(args.hermes_file)
    except (FileNotFoundError, ValueError) as exc:
        logger.error(str(exc))
        sys.exit(1)

    comparison = compare_results(tinycua_data, hermes_data)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(comparison, f, indent=2)

    logger.info("Comparison written to %s", output_path)


if __name__ == "__main__":
    main()
