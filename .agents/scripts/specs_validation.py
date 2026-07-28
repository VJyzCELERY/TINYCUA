"""Pure validation for the repository's indexed Specs comments."""

import re

DOCUMENTS = ("spec", "design", "plan", "task")


def specs_title(primary: int, title: str) -> str:
    """Return the deterministic title for one primary issue's Specs issue."""
    if not isinstance(primary, int) or isinstance(primary, bool) or primary < 1:
        raise ValueError("primary issue number must be positive")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("primary issue title must be non-empty")
    return f"Spec(#{primary}): {title}"


def validate_issue(issue: object, primary: int, primary_title: str) -> str:
    """Return the body of one open Specs issue for the expected primary issue."""
    if not isinstance(issue, dict) or issue.get("state", "").lower() != "open":
        raise ValueError("Specs issue must be open")
    if issue.get("title") != specs_title(primary, primary_title):
        raise ValueError("Specs issue title does not match the primary issue")
    labels = issue.get("labels")
    if not isinstance(labels, list) or "spec" not in {
        label.get("name") for label in labels if isinstance(label, dict)
    }:
        raise ValueError("Specs issue must be labelled spec")
    if "pull_request" in issue:
        raise ValueError("Specs issue must not be a pull request")
    body = issue.get("body")
    if not isinstance(body, str) or len(
        re.findall(rf"(?m)^Primary Issue: #{primary}\s*$", body)
    ) != 1:
        raise ValueError("Specs issue does not identify the primary issue")
    return body


def _comment_id(url: object, issue: int, repository: str) -> str:
    match = re.fullmatch(
        r"https://github\.com/([^/]+/[^/]+)/issues/([1-9][0-9]*)"
        r"#issuecomment-([1-9][0-9]*)",
        url if isinstance(url, str) else "",
        re.IGNORECASE,
    )
    if (
        not match
        or match.group(1).lower() != repository.lower()
        or int(match.group(2)) != issue
    ):
        raise ValueError("Specs index contains a malformed or foreign link")
    return match.group(3)


def parse_index(body: str, issue: int, repository: str) -> dict[str, str]:
    """Parse one strict four-document Specs index."""
    match = re.search(r"(?ms)^## Documents\n\n((?:- [^\n]+\n)+)\Z", body)
    if not match or len(re.findall(r"(?m)^## Documents\s*$", body)) != 1:
        raise ValueError("Specs issue has a malformed document index")
    entries = re.findall(r"(?m)^- ([a-z]+): (https://[^\s]+)$", match.group(1))
    references = dict(entries)
    if [name for name, _ in entries] != list(DOCUMENTS):
        raise ValueError("Specs index must contain exactly four document keys")
    ids = [_comment_id(url, issue, repository) for url in references.values()]
    if len(set(ids)) != len(ids):
        raise ValueError("Specs index contains duplicate comment links")
    return references


def changed_documents(
    references: dict[str, str], comments: list[dict], desired: dict[str, str]
) -> list[str]:
    """Return indexed documents whose canonical comment bodies differ."""
    changed = []
    for name in DOCUMENTS:
        matches = [comment for comment in comments if comment.get("html_url") == references[name]]
        if len(matches) != 1 or not isinstance(matches[0].get("body"), str):
            raise ValueError("Specs index references a missing comment")
        if matches[0]["body"] != desired.get(name):
            changed.append(name)
    return changed


def missing_documents(comments: list[dict], desired: dict[str, str]) -> list[str]:
    """Validate an unindexed partial publication and return missing documents."""
    if not isinstance(comments, list):
        raise ValueError("Specs comments must be a list")
    missing = []
    for name in DOCUMENTS:
        body = desired.get(name)
        if not isinstance(body, str) or not body:
            raise ValueError(f"desired {name} document is missing")
        lines = body.splitlines()
        if not lines:
            raise ValueError(f"desired {name} document is malformed")
        heading = lines[0]
        matches = [
            comment
            for comment in comments
            if isinstance(comment, dict)
            and isinstance(comment.get("body"), str)
            and comment["body"].splitlines()
            and comment["body"].splitlines()[0] == heading
        ]
        if not matches:
            missing.append(name)
        elif len(matches) != 1 or matches[0]["body"] != body:
            raise ValueError(f"conflicting canonical {name} comments")
    return missing
