"""N-way comparison of benchmark results across multiple agents.

Produces a comparison dict with per-task scores for each agent and
aggregate statistics.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def compare_agents(
    agent_results: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Compare benchmark results across N agents.

    Args:
        agent_results: Mapping of agent_name -> list of task result dicts.
            Each task dict must contain at least 'task_id'. Optional keys:
            'score', 'status', 'elapsed_time'.

    Returns:
        Comparison dict with keys:
            - agents: List of agent names.
            - per_task_comparison: List of per-task dicts with scores per agent.
            - aggregate: Per-agent aggregate stats.
    """
    if not agent_results:
        return {"agents": [], "per_task_comparison": [], "aggregate": {}}

    agent_names = sorted(agent_results.keys())
    task_maps = {
        name: _build_task_map(results) for name, results in agent_results.items()
    }

    all_task_ids: set[str] = set()
    for tm in task_maps.values():
        all_task_ids.update(tm.keys())

    per_task: list[dict[str, Any]] = []
    for task_id in sorted(all_task_ids):
        entry: dict[str, Any] = {"task_id": task_id}
        for name in agent_names:
            task = task_maps[name].get(task_id, {})
            entry[f"{name}_score"] = task.get("score")
            entry[f"{name}_status"] = task.get("status")
        per_task.append(entry)

    aggregate: dict[str, Any] = {}
    for name in agent_names:
        scores = [
            float(t.get("score"))
            for t in task_maps[name].values()
            if t.get("score") is not None
        ]
        aggregate[name] = {
            "total_tasks": len(task_maps[name]),
            "average_score": round(sum(scores) / len(scores), 4) if scores else None,
            "successful_tasks": sum(
                1 for t in task_maps[name].values() if t.get("status") == "success"
            ),
        }

    return {
        "agents": agent_names,
        "per_task_comparison": per_task,
        "aggregate": aggregate,
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
        with filepath.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Failed to parse {path}: {exc}") from exc


def main() -> None:
    """CLI entry point: compare agent result files.

    Usage:
        python -m agents_benchmark.compare --results-dir ./output --output comparison.json
    """
    import argparse

    parser = argparse.ArgumentParser(description="Compare agent benchmark results.")
    parser.add_argument(
        "--results-dir",
        default="output",
        help="Directory containing agent result files.",
    )
    parser.add_argument(
        "--output",
        default="comparison.json",
        help="Output path for comparison JSON.",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        logger.error("Results directory not found: %s", results_dir)
        sys.exit(1)

    agent_results: dict[str, list[dict]] = {}
    for result_file in sorted(results_dir.glob("*_results.json")):
        agent_name = result_file.name.replace("_results.json", "")
        try:
            data = _load_json(str(result_file))
            agent_results[agent_name] = data.get("tasks", [])
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("Skipping %s: %s", agent_name, exc)

    comparison = compare_agents(agent_results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(comparison, f, indent=2)

    logger.info("Comparison written to %s", output_path)


if __name__ == "__main__":
    main()
