#!/usr/bin/env python3
"""WildClawBench batch evaluation runner.

Loads task definitions, creates agent instances, runs tasks sequentially
or in parallel, and saves results to output/<harness>/.

Usage:
    python3 eval/run_batch.py --harness opencode --category all
    python3 eval/run_batch.py --harness openclaw --model qwen3.5-9b
    python3 eval/run_batch.py --category 02_Code_Intelligence --parallel 2
    python3 eval/run_batch.py --no-score --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import statistics
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = PROJECT_DIR / "tasks"
OUTPUT_DIR = PROJECT_DIR / "output"

CATEGORY_ALL = "all"
CATEGORIES = [
    "01_Productivity_Flow",
    "02_Code_Intelligence",
    "03_Search_Retrieval",
    "04_Data_Processing",
    "05_Safety_Alignment",
]

DEFAULT_TIMEOUT = 600


def _random_id(length: int = 6) -> str:
    return "".join(random.choices(string.hexdigits[:16], k=length))


def _load_env(env_path: Path) -> dict[str, str]:
    """Load .env file into a dict."""
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip("\"'")
    return env


def _load_tasks(tasks_dir: Path, category: str, default_timeout: int | None = None) -> list[dict]:
    """Load all task definitions from tasks/ directory, filtered by category."""
    if not tasks_dir.exists():
        logger.warning("Tasks directory not found: %s", tasks_dir)
        return []

    if default_timeout is None:
        default_timeout = DEFAULT_TIMEOUT

    tasks: list[dict] = []
    for task_file in sorted(tasks_dir.rglob("*.yaml")):
        try:
            with open(task_file) as f:
                task = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as exc:
            logger.warning("Failed to load task %s: %s", task_file, exc)
            continue

        if not isinstance(task, dict):
            continue

        task_category = task.get("category", "")
        if category != CATEGORY_ALL and task_category != category:
            continue

        task.setdefault("task_id", task_file.stem)
        task.setdefault("category", task_category)
        task.setdefault("prompt", "")
        task.setdefault("timeout", default_timeout)
        tasks.append(task)

    for task_file in sorted(tasks_dir.rglob("*.json")):
        try:
            with open(task_file) as f:
                task = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load task %s: %s", task_file, exc)
            continue

        if not isinstance(task, dict):
            continue

        task_category = task.get("category", "")
        if category != CATEGORY_ALL and task_category != category:
            continue

        task.setdefault("task_id", task_file.stem)
        task.setdefault("category", task_category)
        task.setdefault("prompt", "")
        task.setdefault("timeout", default_timeout)
        tasks.append(task)

    return tasks


def _get_model(harness: str, model_override: str | None, env: dict[str, str]) -> str:
    """Resolve model name for the given harness."""
    if model_override:
        return model_override
    default = env.get("DEFAULT_MODEL", "")
    if default:
        return default
    if harness in ("opencode", "hermesagent"):
        return "qwen3.5-9b"
    return "qwen3.5-9b"


def _build_agent(
    harness: str, model: str, env: dict[str, str]
):
    """Create an agent instance for the given harness."""
    from agent_benchmark import get_agent
    from agent_benchmark.providers.base import ProviderConfig
    from agent_benchmark.providers.registry import get_provider

    # Get provider config from environment (bash exports PROVIDER_* into os.environ)
    provider_name = os.environ.get("PROVIDER_NAME", env.get("PROVIDER_NAME", "lm-studio"))
    api_base = os.environ.get("PROVIDER_API_BASE", env.get("PROVIDER_API_BASE", "http://localhost:1234/v1"))
    api_key_env = os.environ.get("PROVIDER_API_KEY_ENV", env.get("PROVIDER_API_KEY_ENV", "LM_STUDIO_API_KEY"))
    
    # Create provider config
    config = ProviderConfig(
        name=provider_name,
        api_base=api_base,
        api_key_env=api_key_env,
        model=model,
    )
    
    # Get provider instance
    provider = get_provider(provider_name, config)
    
    if harness == "hermesagent":
        return get_agent("hermesagent", provider=provider)

    if harness == "opencode":
        return get_agent("opencode", provider=provider)

    if harness == "openclaw":
        return get_agent("openclaw", provider=provider)

    return get_agent(harness)


def _create_default_config(
    path: Path, model: str, api_key_env: str, env: dict[str, str]
) -> None:
    """Create a default agent config file (kept for backward compatibility)."""
    api_base = env.get("API_BASE", "http://localhost:1234/v1")
    config = {
        "model": model,
        "api_base": api_base,
        "api_key_env": api_key_env,
        "temperature": 0.0,
        "max_tokens": 4096,
        "timeout": 120,
        "cost_per_token": 0.0000025,
    }
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    logger.info("Created default config: %s", path)


def _run_single_task(
    agent,
    task: dict,
    model: str,
    output_base: Path,
    enable_scoring: bool = True,
    verbose: bool = False,
    progress_callback=None,
) -> dict:
    """Run a single task and return result dict.

    Args:
        agent: Agent instance to run the task.
        task: Task definition dict.
        model: Model name.
        output_base: Base output directory.
        enable_scoring: Whether to run scoring after task completion.
        verbose: Whether to print detailed scoring output.

    Returns:
        Result dict with task_id, status, score, etc.
    """
    from agent_benchmark.base_agent import AgentTaskSpec
    from agent_benchmark.scoring.criteria import get_verification
    from agent_benchmark.scoring.engine import save_score, score_task

    task_id = task["task_id"]
    category = task.get("category", "uncategorized")
    prompt = task.get("prompt", "")
    timeout = task.get("timeout", DEFAULT_TIMEOUT)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = _random_id()
    model_short = model.rsplit("/", 1)[-1].replace(":", "_")
    run_dir_name = f"{model_short}_{timestamp}_{run_id}"

    output_dir = output_base / category / task_id / run_dir_name
    workspace_dir = Path(f"/tmp/wildclawbench/workspace/{task_id}_{run_id}")
    workspace_dir.mkdir(parents=True, exist_ok=True)

    spec = AgentTaskSpec(
        task_id=task_id,
        task=task,
        workspace_path=str(workspace_dir),
        prompt=prompt,
        timeout_seconds=timeout,
        output_dir=output_dir,
        model=model,
    )

    logger.info("Running task %s (%s)...", task_id, category)
    start = time.monotonic()
    execution = agent.run_task(spec)
    elapsed = time.monotonic() - start

    result: dict = {
        "task_id": task_id,
        "category": category,
        "model": model,
        "elapsed_time": round(elapsed, 2),
        "status": "error" if execution.error else "success",
    }

    if execution.error:
        result["error"] = execution.error
        result["score"] = 0.0
        logger.error("Task %s failed: %s", task_id, execution.error)
    else:
        usage = agent.collect_usage(task_id, output_dir, elapsed)
        result["usage"] = usage
        logger.info("Task %s completed in %.1fs", task_id, elapsed)

        # Run scoring if enabled
        if enable_scoring:
            verification = get_verification(task_id)
            if verification:
                llm_response_path = output_dir / "llm_response.txt"
                score_result = score_task(
                    task_id=task_id,
                    workspace_dir=workspace_dir,
                    output_dir=output_dir,
                    llm_response_path=llm_response_path,
                    verification=verification,
                )
                result["score"] = score_result.score
                result["raw_score"] = score_result.raw_score
                result["max_score"] = score_result.max_score

                # Save score.json
                save_score(score_result, output_dir)

                # Verbose output
                if verbose:
                    logger.info(
                        "  Score: %.2f (%.0f/%.0f points)",
                        score_result.score,
                        score_result.raw_score,
                        score_result.max_score,
                    )
                    for c in score_result.criteria:
                        status = "✓" if c.passed else "✗"
                        logger.info("    %s %s: %.0f/%.0f - %s", status, c.name, c.points, c.max_points, c.details)
            else:
                result["score"] = None
                logger.debug("No verification rules for task %s", task_id)
        else:
            result["score"] = None

    usage_path = output_dir / "usage.json"
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    with open(usage_path, "w") as f:
        json.dump(result, f, indent=2)

    if progress_callback:
        progress_callback(result)

    return result


def _save_summary(results: list[dict], harness: str, model: str) -> Path:
    """Save summary_all.json with aggregate stats.

    Computes average_score, min_score, max_score, and per-category breakdowns
    from individual task scores.
    """
    total = len(results)
    successful = sum(1 for r in results if r["status"] == "success")
    errors = total - successful

    # Compute aggregate scores
    scored_tasks = [r for r in results if r.get("score") is not None]
    scores = [r["score"] for r in scored_tasks]

    average_score = statistics.mean(scores) if scores else None
    min_score = min(scores) if scores else None
    max_score = max(scores) if scores else None

    # Per-category breakdown
    category_scores: dict[str, dict] = {}
    for result in results:
        cat = result.get("category", "uncategorized")
        if cat not in category_scores:
            category_scores[cat] = {"scores": [], "count": 0}
        category_scores[cat]["count"] += 1
        if result.get("score") is not None:
            category_scores[cat]["scores"].append(result["score"])

    # Compute per-category averages
    for cat in category_scores:
        cat_scores = category_scores[cat]["scores"]
        category_scores[cat] = {
            "count": category_scores[cat]["count"],
            "average_score": statistics.mean(cat_scores) if cat_scores else None,
            "min_score": min(cat_scores) if cat_scores else None,
            "max_score": max(cat_scores) if cat_scores else None,
        }

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "harness": harness,
        "model": model,
        "total_tasks": total,
        "successful_tasks": successful,
        "failed_tasks": errors,
        "average_score": average_score,
        "min_score": min_score,
        "max_score": max_score,
        "category_scores": category_scores,
        "tasks": results,
    }

    output_file = OUTPUT_DIR / harness / "summary_all.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("Summary saved to %s", output_file)
    return output_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WildClawBench batch evaluation runner"
    )
    parser.add_argument(
        "--harness",
        default="openclaw",
        choices=["openclaw", "opencode", "hermesagent"],
        help="Agent harness to evaluate (default: openclaw)",
    )
    parser.add_argument(
        "--category",
        default=CATEGORY_ALL,
        help="Task category filter (default: all)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model to evaluate (default: from .env)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel tasks (default: 1)",
    )
    parser.add_argument(
        "--no-score",
        action="store_true",
        help="Disable scoring (skip evaluation of task output)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging"
    )
    parser.add_argument(
        "--timeout",
        type=str,
        default=None,
        help="Task timeout: number in seconds, or 'unlimited' (default: 600)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    env = _load_env(PROJECT_DIR / ".env")
    os.environ.update(env)

    model = _get_model(args.harness, args.model, env)
    enable_scoring = not args.no_score

    # Resolve timeout: CLI flag > env var > default
    def parse_timeout(value: str | None) -> int | None:
        """Parse timeout value. Returns None for unlimited, int for seconds."""
        if value is None:
            return DEFAULT_TIMEOUT
        value = value.strip().lower()
        if value in ("unlimited", "none", "inf", "infinite"):
            return None
        try:
            return int(value)
        except ValueError:
            logger.warning("Invalid timeout value '%s', using default %ds", value, DEFAULT_TIMEOUT)
            return DEFAULT_TIMEOUT

    if args.timeout is not None:
        task_timeout = parse_timeout(args.timeout)
    else:
        task_timeout = parse_timeout(env.get("TIMEOUT", str(DEFAULT_TIMEOUT)))
    
    if task_timeout is None:
        logger.info("Timeout: unlimited")
    else:
        logger.info("Timeout: %ds per task", task_timeout)

    logger.info("Harness: %s, Model: %s, Category: %s", args.harness, model, args.category)
    if enable_scoring:
        logger.info("Scoring: enabled")
    else:
        logger.info("Scoring: disabled")

    tasks = _load_tasks(TASKS_DIR, args.category, task_timeout)
    if not tasks:
        logger.error("No tasks found for category '%s' in %s", args.category, TASKS_DIR)
        logger.info("Create task files in tasks/ directory (YAML or JSON).")
        raise SystemExit(1)

    logger.info("Loaded %d tasks", len(tasks))

    agent = _build_agent(args.harness, model, env)
    results: list[dict] = []
    total_tasks = len(tasks)
    completed_tasks = [0]

    def progress_callback(result):
        completed_tasks[0] += 1
        status = "✓" if result["status"] == "success" else "✗"
        score_str = f" ({result['score']:.2f})" if result.get("score") is not None else ""
        logger.info(
            "[%d/%d] %s %s%s - %.1fs",
            completed_tasks[0],
            total_tasks,
            status,
            result["task_id"],
            score_str,
            result["elapsed_time"],
        )

    if args.parallel > 1:
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures = {
                pool.submit(
                    _run_single_task,
                    agent,
                    task,
                    model,
                    OUTPUT_DIR / args.harness,
                    enable_scoring,
                    args.verbose,
                    progress_callback,
                ): task
                for task in tasks
            }
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    task = futures[future]
                    logger.error("Task %s raised: %s", task.get("task_id"), exc)
                    results.append({
                        "task_id": task.get("task_id", "unknown"),
                        "category": task.get("category", ""),
                        "model": model,
                        "elapsed_time": 0,
                        "status": "error",
                        "error": str(exc),
                        "score": 0.0,
                    })
    else:
        for task in tasks:
            try:
                result = _run_single_task(
                    agent,
                    task,
                    model,
                    OUTPUT_DIR / args.harness,
                    enable_scoring,
                    args.verbose,
                    progress_callback,
                )
                results.append(result)
            except Exception as exc:
                logger.error("Task %s raised: %s", task.get("task_id"), exc)
                results.append({
                    "task_id": task.get("task_id", "unknown"),
                    "category": task.get("category", ""),
                    "model": model,
                    "elapsed_time": 0,
                    "status": "error",
                    "error": str(exc),
                    "score": 0.0,
                })

    summary_path = _save_summary(results, args.harness, model)

    successful = sum(1 for r in results if r["status"] == "success")
    total = len(results)
    scored = sum(1 for r in results if r.get("score") is not None)
    avg_score = statistics.mean([r["score"] for r in results if r.get("score") is not None]) if scored > 0 else None

    logger.info("Completed %d/%d tasks successfully", successful, total)
    if avg_score is not None:
        logger.info("Average score: %.2f (%d tasks scored)", avg_score, scored)
    logger.info("Results: %s", summary_path)


if __name__ == "__main__":
    main()
