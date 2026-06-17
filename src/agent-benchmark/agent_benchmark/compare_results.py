"""Side-by-side comparison of benchmark result sets.

Generalized to support any two agents (not just TinyCUA vs Hermes).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def compare_results(
    data_a: dict[str, Any],
    data_b: dict[str, Any],
    name_a: str = "agent_a",
    name_b: str = "agent_b",
) -> dict[str, Any]:
    """Compare two benchmark result sets side-by-side.

    Args:
        data_a: Summary dict from first agent run (with 'summary' and 'tasks').
        data_b: Summary dict from second agent run (with 'summary' and 'tasks').
        name_a: Display name for agent A.
        name_b: Display name for agent B.

    Returns:
        Comparison dict with per-task deltas and aggregate statistics.
    """
    tasks_a = _build_task_map(data_a.get("tasks", []))
    tasks_b = _build_task_map(data_b.get("tasks", []))

    all_task_ids = sorted(set(tasks_a.keys()) | set(tasks_b.keys()))

    per_task: list[dict[str, Any]] = []
    scores_a: list[float] = []
    scores_b: list[float] = []

    for task_id in all_task_ids:
        a = tasks_a.get(task_id, {})
        b = tasks_b.get(task_id, {})

        score_a = a.get("score")
        score_b = b.get("score")

        if score_a is not None:
            scores_a.append(float(score_a))
        if score_b is not None:
            scores_b.append(float(score_b))

        delta = None
        if score_a is not None and score_b is not None:
            delta = round(float(score_b) - float(score_a), 4)

        per_task.append(
            {
                "task_id": task_id,
                f"{name_a}_score": score_a,
                f"{name_a}_status": a.get("status"),
                f"{name_a}_elapsed": a.get("elapsed_time"),
                f"{name_b}_score": score_b,
                f"{name_b}_status": b.get("status"),
                f"{name_b}_elapsed": b.get("elapsed_time"),
                "delta": delta,
            }
        )

    avg_a = _safe_mean(scores_a)
    avg_b = _safe_mean(scores_b)
    aggregate_delta = (
        round(avg_b - avg_a, 4) if (avg_a is not None and avg_b is not None) else None
    )

    category_deltas: dict[str, dict[str, Any]] = {}
    for entry in per_task:
        cat = tasks_a.get(entry["task_id"], {}).get("task_category", "Uncategorized")
        if cat not in category_deltas:
            category_deltas[cat] = {
                f"{name_a}_scores": [],
                f"{name_b}_scores": [],
                "count": 0,
            }
        category_deltas[cat]["count"] += 1
        if entry[f"{name_a}_score"] is not None:
            category_deltas[cat][f"{name_a}_scores"].append(entry[f"{name_a}_score"])
        if entry[f"{name_b}_score"] is not None:
            category_deltas[cat][f"{name_b}_scores"].append(entry[f"{name_b}_score"])

    for cat in category_deltas:
        avg_cat_a = _safe_mean(category_deltas[cat][f"{name_a}_scores"])
        avg_cat_b = _safe_mean(category_deltas[cat][f"{name_b}_scores"])
        category_deltas[cat] = {
            "count": category_deltas[cat]["count"],
            f"{name_a}_average": avg_cat_a,
            f"{name_b}_average": avg_cat_b,
            "delta": round(avg_cat_b - avg_cat_a, 4)
            if (avg_cat_a is not None and avg_cat_b is not None)
            else None,
        }

    return {
        name_a: {
            "average_score": data_a.get("summary", {}).get("average_score"),
            "successful_tasks": data_a.get("summary", {}).get("successful_tasks"),
            "total_tasks": data_a.get("summary", {}).get("total_tasks"),
        },
        name_b: {
            "average_score": data_b.get("summary", {}).get("average_score"),
            "successful_tasks": data_b.get("summary", {}).get("successful_tasks"),
            "total_tasks": data_b.get("summary", {}).get("total_tasks"),
        },
        "per_task_comparison": per_task,
        "aggregate_delta": aggregate_delta,
        "category_deltas": category_deltas,
    }


def _build_task_map(tasks: list[dict]) -> dict[str, dict]:
    return {t["task_id"]: t for t in tasks if "task_id" in t}


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _load_json(path: str) -> dict:
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"Result file not found: {path}")
    try:
        with open(filepath) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Failed to parse {path}: {exc}") from exc


def main() -> None:
    r"""CLI entry point: compare two summary_all.json files.

    Usage:
        python -m agent_benchmark.compare_results <agent_a.json> <agent_b.json> \\
            --name-a openclaw --name-b hermesagent [--output comparison.json]
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare two benchmark result sets side-by-side."
    )
    parser.add_argument("file_a", help="Path to agent A summary_all.json")
    parser.add_argument("file_b", help="Path to agent B summary_all.json")
    parser.add_argument("--name-a", default="agent_a", help="Display name for agent A")
    parser.add_argument("--name-b", default="agent_b", help="Display name for agent B")
    parser.add_argument("--output", default="comparison.json", help="Output path")
    args = parser.parse_args()

    try:
        data_a = _load_json(args.file_a)
        data_b = _load_json(args.file_b)
    except (FileNotFoundError, ValueError) as exc:
        logger.error(str(exc))
        sys.exit(1)

    comparison = compare_results(data_a, data_b, args.name_a, args.name_b)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(comparison, f, indent=2)

    logger.info("Comparison written to %s", output_path)


if __name__ == "__main__":
    main()
