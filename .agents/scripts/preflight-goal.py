"""Report whether one /goal target has valid local state and role configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import goal_roles
import local_issue
import workflow_state


def _state(root: Path, goal: dict[str, str]) -> str:
    if goal["kind"] == "local":
        local_issue.validate_bundle(root, goal["goal"].removeprefix("local:"))
        return "valid"
    if goal["kind"] == "issue":
        issue = workflow_state._issue(goal["goal"])
        path = workflow_state._state_path(root, issue)
        if not path.exists():
            return "missing"
        workflow_state._load(root, issue)
        return "valid"
    target = workflow_state._pr(goal["goal"])
    path = workflow_state._pr_state_path(root, target)
    if not path.exists():
        return "missing"
    workflow_state._load_pr(root, target)
    return "valid"


def main(
    argv: list[str] | None = None,
    *,
    root: Path | None = None,
    output: Callable[[str], None] = print,
    error: Callable[[str], None] = print,
) -> int:
    """Initialize template-backed goal state and report its readiness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("goal")
    parser.add_argument("--title")
    parser.add_argument("--url")
    parser.add_argument("--objective")
    parser.add_argument("--format", choices=("human", "json"), default="human")
    try:
        args = parser.parse_args(argv)
        repository = (root or Path(__file__).resolve().parents[2]).resolve()
        if not repository.is_dir() or repository.is_symlink():
            raise ValueError("repository root is missing or unsafe")
        goal = goal_roles.parse_goal(args.goal)
        goal_roles.initialize_template(repository, goal)
        configuration = "valid" if goal_roles._is_confirmed(repository, goal) else "missing"
        if configuration == "valid":
            goal_roles._configuration(repository, goal)
        metadata = (args.title, args.url, args.objective)
        if any(metadata):
            if goal["kind"] != "issue" or not all(metadata):
                raise ValueError("state initialization requires issue title, URL, and objective")
            state_output: list[str] = []
            state_error: list[str] = []
            code = workflow_state.main(
                [
                    "init",
                    goal["goal"],
                    "--title",
                    args.title,
                    "--url",
                    args.url,
                    "--objective",
                    args.objective,
                ],
                root=repository,
                output=state_output.append,
                error=state_error.append,
            )
            if code:
                raise ValueError("; ".join(state_error))
        result = {"goal": goal["goal"], "state": _state(repository, goal), "configuration": configuration}
        output(json.dumps(result, sort_keys=True) if args.format == "json" else str(result))
        return 0
    except (OSError, ValueError, goal_roles.RoleError, argparse.ArgumentError) as exc:
        error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
