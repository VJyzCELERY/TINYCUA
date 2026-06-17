"""N-way comparison of benchmark results across multiple agents.

Produces a comparison dict with per-task scores for each agent and
aggregate statistics.
"""

from __future__ import annotations

import logging
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
