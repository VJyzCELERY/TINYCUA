"""Manage validated ignored local-first issue bundles."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

DOCUMENTS = ("draft.md", "spec.md", "design.md", "implementation-plan.md", "task.md")
SPECS_DOCUMENTS = ("spec", "design", "plan", "task")
PHASES = ("issue", "planned", "implemented", "reviewed", "promoted")
_IDENTIFIER = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
_ISSUE_URL = re.compile(
    r"https://github\.com/([^/]+/[^/]+)/issues/([1-9][0-9]*)\Z", re.I
)


def _bundle(root: Path, identifier: str) -> Path:
    if not _IDENTIFIER.fullmatch(identifier):
        raise ValueError("bundle identifier must be lower-kebab-case")
    path = root.resolve() / ".agents" / "local" / "issues" / identifier
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("bundle path escapes the repository") from exc
    return path


def _state_path(bundle: Path) -> Path:
    return bundle / "state.json"


def _worktree(root: Path, branch: str, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("local bundle worktree is invalid")
    worktree = Path(value)
    if not worktree.is_absolute():
        raise ValueError("local bundle worktree must be absolute")
    try:
        worktree = worktree.resolve(strict=True)
        worktree.relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise ValueError("local bundle worktree escapes the repository") from exc
    if not worktree.is_dir():
        raise ValueError("local bundle worktree is missing")
    try:
        result = subprocess.run(
            ["git", "-C", str(worktree), "branch", "--show-current"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise ValueError("could not inspect local bundle worktree") from exc
    if result.returncode or result.stdout.strip() != branch:
        raise ValueError("local bundle worktree does not match its branch")
    return worktree


def _write(path: Path, value: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _promotion(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"repository", "issue", "specs"}:
        raise ValueError("promotion has unknown or missing fields")
    repository = value["repository"]
    if not isinstance(repository, str) or not re.fullmatch(
        r"[^/\s]+/[^/\s]+", repository
    ):
        raise ValueError("promotion repository is invalid")
    issue = value["issue"]
    specs = value["specs"]
    if not isinstance(issue, dict) or set(issue) != {"number", "url"}:
        raise ValueError("promotion issue is invalid")
    if not isinstance(specs, dict) or set(specs) != {"number", "url", "documents"}:
        raise ValueError("promotion Specs is invalid")
    for name, record in (("issue", issue), ("Specs", specs)):
        match = _ISSUE_URL.fullmatch(
            record["url"] if isinstance(record["url"], str) else ""
        )
        if (
            not isinstance(record["number"], int)
            or isinstance(record["number"], bool)
            or record["number"] < 1
            or not match
            or match.group(1).lower() != repository.lower()
            or int(match.group(2)) != record["number"]
        ):
            raise ValueError(f"promotion {name} reference is invalid")
    documents = specs["documents"]
    if not isinstance(documents, dict) or set(documents) != set(SPECS_DOCUMENTS):
        raise ValueError("promotion Specs documents are incomplete")
    base = re.escape(specs["url"])
    for url in documents.values():
        if not isinstance(url, str) or not re.fullmatch(
            base + r"#issuecomment-[1-9][0-9]*", url, re.I
        ):
            raise ValueError("promotion Specs document is invalid")
    return value


def _read(root: Path, identifier: str) -> tuple[Path, dict]:
    bundle = _bundle(root, identifier)
    if not bundle.is_dir():
        raise ValueError("local bundle is missing")
    for name in DOCUMENTS:
        path = bundle / name
        try:
            path.resolve().relative_to(bundle.resolve())
        except ValueError as exc:
            raise ValueError("local bundle document escapes the bundle") from exc
        if not path.is_file():
            raise ValueError(f"local bundle document is missing: {name}")
        if "[NEEDS CLARIFICATION]" in path.read_text(encoding="utf-8"):
            raise ValueError("local bundle contains an unresolved clarification")
    state_path = _state_path(bundle)
    try:
        state_path.resolve(strict=True).relative_to(bundle.resolve())
    except (OSError, ValueError) as exc:
        raise ValueError("local bundle state escapes the bundle") from exc
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("local bundle state is missing or malformed") from exc
    if not isinstance(state, dict) or set(state) != {
        "identifier",
        "branch",
        "worktree",
        "phase",
        "promotion",
    }:
        raise ValueError("local bundle state has unknown or missing fields")
    if state["identifier"] != identifier:
        raise ValueError("local bundle identity conflicts with its path")
    if not isinstance(state["branch"], str) or not _BRANCH.fullmatch(state["branch"]):
        raise ValueError("local bundle branch is invalid")
    worktree = _worktree(root, state["branch"], state["worktree"])
    if not isinstance(state["phase"], str) or state["phase"] not in PHASES:
        raise ValueError("local bundle phase is invalid")
    if state["promotion"] is not None:
        _promotion(state["promotion"])
        if state["phase"] != "promoted":
            raise ValueError("promoted local bundle phase is invalid")
    elif state["phase"] == "promoted":
        raise ValueError("promoted local bundle is missing its mapping")
    state["worktree"] = str(worktree)
    return bundle, state


def create_bundle(
    root: Path, identifier: str, branch: str, worktree: Path, documents: dict[str, str]
) -> Path:
    """Create one complete local bundle without replacing an existing one."""
    bundle = _bundle(root, identifier)
    if bundle.exists():
        _read(root, identifier)
        return bundle
    if not _BRANCH.fullmatch(branch):
        raise ValueError("local bundle branch is invalid")
    worktree = _worktree(root, branch, str(worktree))
    if set(documents) != set(DOCUMENTS) or not all(
        isinstance(content, str) and content for content in documents.values()
    ):
        raise ValueError("local bundle documents are incomplete")
    bundle.mkdir(parents=True)
    for name, content in documents.items():
        (bundle / name).write_text(content, encoding="utf-8")
    _write(
        _state_path(bundle),
        {
            "identifier": identifier,
            "branch": branch,
            "worktree": str(worktree),
            "phase": "issue",
            "promotion": None,
        },
    )
    _read(root, identifier)
    return bundle


def validate_bundle(root: Path, identifier: str) -> dict:
    """Return the validated lifecycle facts for one local bundle."""
    return _read(root, identifier)[1]


def record_phase(root: Path, identifier: str, phase: str) -> dict:
    """Persist the next local lifecycle phase, preserving safe resumes."""
    bundle, state = _read(root, identifier)
    if phase not in PHASES:
        raise ValueError("local bundle phase is invalid")
    current = state["phase"]
    if phase == current:
        return state
    if PHASES.index(phase) != PHASES.index(current) + 1:
        raise ValueError("local bundle phase transition is invalid")
    if phase == "promoted":
        raise ValueError("local bundle promotion requires a verified mapping")
    state["phase"] = phase
    _write(_state_path(bundle), state)
    return _read(root, identifier)[1]


def record_promotion(root: Path, identifier: str, promotion: dict) -> dict:
    """Persist one verified remote mapping, rejecting a conflicting retry."""
    bundle, state = _read(root, identifier)
    promotion = _promotion(promotion)
    if state["promotion"] is not None:
        if state["promotion"] != promotion:
            raise ValueError("promotion conflicts with the recorded mapping")
        return state
    if state["phase"] != "reviewed":
        raise ValueError("local bundle must be reviewed before promotion")
    state["promotion"] = promotion
    state["phase"] = "promoted"
    _write(_state_path(bundle), state)
    return _read(root, identifier)[1]


class ArgumentParser(argparse.ArgumentParser):
    """Report CLI input errors without terminating tests or callers."""

    def error(self, message: str) -> None:
        raise argparse.ArgumentError(None, message)


def _parser() -> argparse.ArgumentParser:
    parser = ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    create = commands.add_parser("create")
    create.add_argument("identifier")
    create.add_argument("branch")
    create.add_argument("--worktree", required=True, type=Path)
    for document in DOCUMENTS:
        create.add_argument(
            f"--{document.removesuffix('.md')}", required=True, type=Path
        )
    validate = commands.add_parser("validate")
    validate.add_argument("identifier")
    transition = commands.add_parser("transition")
    transition.add_argument("identifier")
    transition.add_argument("phase", choices=PHASES)
    promote = commands.add_parser("promote")
    promote.add_argument("identifier")
    promote.add_argument("--mapping", required=True, type=Path)
    return parser


def _document_inputs(args: argparse.Namespace) -> dict[str, str]:
    documents = {}
    for document in DOCUMENTS:
        path = getattr(args, document.removesuffix(".md").replace("-", "_"))
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"local bundle input is missing or unsafe: {document}")
        try:
            documents[document] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"local bundle input is unreadable: {document}") from exc
    return documents


def _mapping(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("promotion mapping is missing or unsafe")
    try:
        mapping = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("promotion mapping is malformed") from exc
    return _promotion(mapping)


def _run(args: argparse.Namespace, root: Path) -> dict:
    if args.action == "create":
        create_bundle(
            root,
            args.identifier,
            args.branch,
            args.worktree,
            _document_inputs(args),
        )
        return validate_bundle(root, args.identifier)
    if args.action == "validate":
        return validate_bundle(root, args.identifier)
    if args.action == "transition":
        return record_phase(root, args.identifier, args.phase)
    return record_promotion(root, args.identifier, _mapping(args.mapping))


def main(
    argv: list[str] | None = None,
    *,
    root: Path | None = None,
    output: Callable[[str], None] = print,
    error: Callable[[str], None] = print,
) -> int:
    """Run the local-bundle lifecycle command and return its exit status."""
    try:
        args = _parser().parse_args(argv)
        result = _run(args, (root or Path.cwd()).resolve())
        output(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (argparse.ArgumentError, argparse.ArgumentTypeError) as exc:
        error(str(exc))
        return 2
    except (OSError, ValueError) as exc:
        error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
