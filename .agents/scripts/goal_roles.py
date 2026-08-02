"""Manage explicit, local-only role configuration for one /goal target."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Callable

SCHEMA_VERSION = 2
ROLES = ("planner", "worker", "reviewer")
HARNESSES = ("current", "opencode", "codex", "claude")
PROVIDER_COMMANDS = {"opencode": "opencode", "codex": "codex", "claude": "claude"}
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
SECRET_RE = re.compile(
    r"(?i)(?:\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|secret|"
    r"password|credential|authorization|bearer)\b|\bgh[pousr]_[A-Za-z0-9_]{12,}|"
    r"\bgithub_pat_[A-Za-z0-9_]{12,}|\bsk-[A-Za-z0-9_-]{12,})"
)
ENV_ASSIGNMENT_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}=")
REMOTE_RE = re.compile(
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?)/"
    r"(?P<repo>[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?)(?P<separator>[#!])"
    r"(?P<number>[1-9][0-9]*)\Z"
)
LOCAL_RE = re.compile(r"local:(?P<identifier>[a-z0-9]+(?:-[a-z0-9]+)*)\Z")


class RoleError(ValueError):
    """A role configuration or target is unsafe or malformed."""


class ArgumentParser(argparse.ArgumentParser):
    """Report CLI usage errors without terminating callers."""

    def error(self, message: str) -> None:
        raise argparse.ArgumentError(None, message)


def _text(value: object, field: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoleError(f"{field} must be a non-empty string")
    if len(value) > maximum:
        raise RoleError(f"{field} is too long")
    if CONTROL_RE.search(value) or SECRET_RE.search(value) or ENV_ASSIGNMENT_RE.search(value):
        raise RoleError(f"{field} contains unsafe data")
    return value


def parse_goal(value: object) -> dict[str, str]:
    """Normalize a remote issue/PR or local goal identity."""
    text = _text(value, "goal", 256)
    if match := REMOTE_RE.fullmatch(text):
        owner = match["owner"].lower()
        repo = match["repo"].lower()
        number = match["number"]
        kind = "issue" if match["separator"] == "#" else "pr"
        key = f"{owner}_{repo}_{number}" if kind == "issue" else f"{owner}_{repo}_pr_{number}"
        return {"goal": f"{owner}/{repo}{match['separator']}{number}", "key": key, "kind": kind}
    if match := LOCAL_RE.fullmatch(text):
        identifier = match["identifier"]
        return {"goal": f"local:{identifier}", "key": f"local_{identifier}", "kind": "local"}
    raise RoleError("goal must be OWNER/REPO#NUMBER, OWNER/REPO!NUMBER, or local:<id>")


def _safe_path(root: Path, path: Path, field: str) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise RoleError(f"{field} escapes the repository") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise RoleError(f"{field} is a symlink")
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise RoleError(f"{field} escapes the repository") from exc


def _roles_path(root: Path, goal: dict[str, str]) -> Path:
    path = root / ".agents/local/state/goals" / goal["key"] / "roles.json"
    _safe_path(root, path, "goal role configuration")
    return path


def _confirmation_path(root: Path, goal: dict[str, str]) -> Path:
    path = root / ".agents/local/state/goals" / goal["key"] / "roles.confirmed"
    _safe_path(root, path, "goal role confirmation")
    return path


def _load_json(path: Path, field: str) -> object:
    if path.is_symlink() or not path.is_file():
        raise RoleError(f"{field} is missing or unsafe")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RoleError(f"{field} is malformed") from exc


def _selection(value: object, field: str) -> dict[str, str | None]:
    if not isinstance(value, dict) or set(value) not in ({"harness", "model"}, {"harness", "model", "variant"}):
        raise RoleError(f"{field} has unknown or missing fields")
    harness = _text(value["harness"], "harness", 32)
    if harness not in HARNESSES:
        raise RoleError("harness is unsupported")
    model = value["model"]
    variant = value.get("variant")
    if harness == "current":
        if model is not None or variant is not None:
            raise RoleError("current harness requires null model and variant")
    else:
        model = _text(model, "model")
    if variant is not None:
        variant = _text(variant, "variant", 64)
    return {"harness": harness, "model": model, "variant": variant}


def _parse_configuration(value: object, field: str) -> dict[str, dict[str, str | None]]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "roles"}:
        raise RoleError(f"{field} has unknown or missing fields")
    if value["schema_version"] not in {1, SCHEMA_VERSION} or isinstance(value["schema_version"], bool):
        raise RoleError(f"{field} schema_version is invalid")
    roles = value["roles"]
    if not isinstance(roles, dict) or set(roles) != set(ROLES):
        raise RoleError(f"{field} roles has unknown or missing fields")
    return {role: _selection(roles[role], f"default {role}") for role in ROLES}


def _template_configuration(root: Path) -> dict[str, dict[str, str | None]]:
    path = root / ".agents/templates/goal-roles.default.json"
    _safe_path(root, path, "goal role template")
    return _parse_configuration(_load_json(path, "goal role template"), "goal role template")


def _is_confirmed(root: Path, goal: dict[str, str]) -> bool:
    path = _confirmation_path(root, goal)
    if not path.exists():
        return False
    if path.is_symlink() or not path.is_file():
        raise RoleError("goal role confirmation is unsafe")
    if path.read_text(encoding="utf-8") != "confirmed\n":
        raise RoleError("goal role confirmation is malformed")
    return True


def initialize_template(root: Path, goal: dict[str, str]) -> None:
    """Copy the immutable tracked template into one goal's local config once."""
    template = _template_configuration(root)
    path = _roles_path(root, goal)
    if path.exists():
        _configuration(root, goal)
        return
    _atomic_write(root, path, {"schema_version": SCHEMA_VERSION, "roles": template})


def _configuration(root: Path, goal: dict[str, str]) -> dict[str, dict[str, str | None]]:
    path = _roles_path(root, goal)
    value = _load_json(path, "goal role configuration")
    if not isinstance(value, dict) or set(value) != {"schema_version", "roles"}:
        raise RoleError("goal role configuration has unknown or missing fields")
    if value["schema_version"] not in {1, SCHEMA_VERSION} or isinstance(value["schema_version"], bool):
        raise RoleError("goal role configuration schema_version is invalid")
    roles = value["roles"]
    if not isinstance(roles, dict) or set(roles) != set(ROLES):
        raise RoleError("goal roles has unknown or missing fields")
    return _parse_configuration(value, "goal role configuration")


def _atomic_write(root: Path, path: Path, value: object) -> None:
    _safe_path(root, path.parent, "goal role configuration directory")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise RoleError("goal role configuration directory is unsafe")
    path.parent.chmod(0o700)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), 0o600)
            data = value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True) + "\n"
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _selections(
    root: Path, goal: dict[str, str], args: argparse.Namespace
) -> dict[str, dict[str, str | None]]:
    selections = _configuration(root, goal)
    for role in ROLES:
        harness = getattr(args, role)
        model = getattr(args, f"{role}_model")
        variant = getattr(args, f"{role}_variant")
        if harness is None:
            if model is not None or variant is not None:
                raise RoleError(f"{role} model or variant requires a selected harness")
            continue
        selections[role] = _selection({"harness": harness, "model": model, "variant": variant}, role)
    return selections


def _init(root: Path, goal: dict[str, str], args: argparse.Namespace) -> None:
    selections = _selections(root, goal, args)
    path = _roles_path(root, goal)
    if _is_confirmed(root, goal):
        if _configuration(root, goal) != selections:
            raise RoleError("goal role configuration conflicts with the recorded selection")
        return
    _atomic_write(root, path, {"schema_version": SCHEMA_VERSION, "roles": selections})
    confirmation = _confirmation_path(root, goal)
    _atomic_write(root, confirmation, "confirmed\n")


def _verify_command(selection: dict[str, str | None], command: list[str]) -> None:
    harness = selection["harness"]
    model = selection["model"]
    if harness not in PROVIDER_COMMANDS or model is None:
        raise RoleError("current harness does not use a provider command")
    if not command or Path(command[0]).name != PROVIDER_COMMANDS[harness]:
        raise RoleError("provider command does not match harness")
    if any(value.startswith("-m") or value.startswith("--model=") for value in command):
        raise RoleError("provider command contains an unconfigured model selector")
    models = [command[index + 1] for index, value in enumerate(command[:-1]) if value == "--model"]
    if models != [model]:
        raise RoleError("provider command must pass the configured model exactly once")


def _parser() -> argparse.ArgumentParser:
    parser = ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    preflight = actions.add_parser("preflight")
    preflight.add_argument("goal")
    resolve = actions.add_parser("resolve")
    resolve.add_argument("goal")
    resolve.add_argument("role", choices=ROLES)
    init = actions.add_parser("init")
    init.add_argument("goal")
    for role in ROLES:
        init.add_argument(f"--{role}", choices=HARNESSES)
        init.add_argument(f"--{role}-model")
        init.add_argument(f"--{role}-variant")
    verify = actions.add_parser("verify")
    verify.add_argument("goal")
    verify.add_argument("role", choices=ROLES)
    verify.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    root: Path | None = None,
    output: Callable[[str], None] = print,
    error: Callable[[str], None] = print,
) -> int:
    """Inspect, initialize, resolve, or verify one goal's role configuration."""
    try:
        args = _parser().parse_args(argv)
        repository = (root or Path(__file__).resolve().parents[2]).resolve()
        if not repository.is_dir() or repository.is_symlink():
            raise RoleError("repository root is missing or unsafe")
        goal = parse_goal(args.goal)
        if args.action == "preflight":
            initialize_template(repository, goal)
            status = "valid" if _is_confirmed(repository, goal) else "missing"
            if status == "valid":
                _configuration(repository, goal)
            output(json.dumps({"goal": goal["goal"], "configuration": status}, sort_keys=True))
        elif args.action == "init":
            initialize_template(repository, goal)
            _init(repository, goal, args)
        elif args.action == "resolve":
            if not _is_confirmed(repository, goal):
                raise RoleError("goal role configuration is missing")
            selection = _configuration(repository, goal)[args.role]
            output(json.dumps({"goal": goal["goal"], "role": args.role, "source": "local", **selection}, sort_keys=True))
        else:
            if not args.command:
                raise RoleError("verify requires provider argv")
            if not _is_confirmed(repository, goal):
                raise RoleError("goal role configuration is missing")
            _verify_command(_configuration(repository, goal)[args.role], args.command)
        return 0
    except (OSError, RoleError, argparse.ArgumentError) as exc:
        error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
