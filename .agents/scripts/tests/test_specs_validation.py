"""Tests for transport-free indexed Specs validation."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import specs_validation


REPOSITORY = "acme/widgets"
ISSUE = 32


def url(comment_id):
    return f"https://github.com/{REPOSITORY}/issues/{ISSUE}#issuecomment-{comment_id}"


def test_parse_index_requires_four_unique_repository_bound_comments():
    body = (
        "# Specs: Widgets\n\nPrimary Issue: #31\n\n## Documents\n\n"
        f"- spec: {url(1)}\n"
        f"- design: {url(2)}\n"
        f"- plan: {url(3)}\n"
        f"- task: {url(4)}\n"
    )

    assert specs_validation.parse_index(body, ISSUE, REPOSITORY) == {
        "spec": url(1),
        "design": url(2),
        "plan": url(3),
        "task": url(4),
    }


def test_validate_issue_requires_open_spec_issue_and_primary_marker():
    issue = {
        "state": "open",
        "labels": [{"name": "spec"}],
        "title": "Spec(#31): Ship widgets",
        "body": "# Specs: Widgets\n\nPrimary Issue: #31\n",
    }

    assert specs_validation.specs_title(31, "Ship widgets") == "Spec(#31): Ship widgets"
    assert specs_validation.validate_issue(issue, 31, "Ship widgets") == issue["body"]
    with pytest.raises(ValueError):
        specs_validation.validate_issue({**issue, "state": "closed"}, 31, "Ship widgets")
    with pytest.raises(ValueError, match="title"):
        specs_validation.validate_issue({**issue, "title": "Specs: Widgets"}, 31, "Ship widgets")


@pytest.mark.parametrize(
    "body",
    [
        "# Specs: Widgets\n\nPrimary Issue: #31\n",
        (
            "# Specs: Widgets\n\nPrimary Issue: #31\n\n## Documents\n\n"
            f"- spec: {url(1)}\n- design: {url(1)}\n"
            f"- plan: {url(3)}\n- task: {url(4)}\n"
        ),
        (
            "# Specs: Widgets\n\nPrimary Issue: #31\n\n## Documents\n\n"
            f"- spec: {url(1)}\n- design: {url(2)}\n"
            f"- plan: {url(3)}\n"
            "- task: https://github.com/other/repo/issues/32#issuecomment-4\n"
        ),
    ],
)
def test_parse_index_rejects_incomplete_duplicate_or_foreign_references(body):
    with pytest.raises(ValueError):
        specs_validation.parse_index(body, ISSUE, REPOSITORY)


def test_resolve_comments_rejects_missing_reference_and_detects_changes():
    references = {name: url(index) for index, name in enumerate(specs_validation.DOCUMENTS, 1)}
    comments = [
        {"html_url": url(index), "body": f"## {name.title()}\n\nold"}
        for index, name in enumerate(specs_validation.DOCUMENTS, 1)
    ]

    assert specs_validation.changed_documents(
        references,
        comments,
        {name: f"## {name.title()}\n\nnew" for name in specs_validation.DOCUMENTS},
    ) == list(specs_validation.DOCUMENTS)

    with pytest.raises(ValueError):
        specs_validation.changed_documents(references, comments[:-1], {})


def test_partial_initialization_reuses_matching_comments_and_rejects_conflicts():
    desired = {name: f"## {name.title()}\n\ncontent" for name in specs_validation.DOCUMENTS}
    comments = [{"html_url": url(1), "body": desired["spec"]}]

    assert specs_validation.missing_documents(comments, desired) == [
        "design",
        "plan",
        "task",
    ]

    comments.append({"html_url": url(2), "body": "## Spec\n\nconflict"})
    with pytest.raises(ValueError, match="conflicting canonical spec comments"):
        specs_validation.missing_documents(comments, desired)
