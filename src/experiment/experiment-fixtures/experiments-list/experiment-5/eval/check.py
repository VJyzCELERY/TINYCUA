"""Deterministically score the Experiment 5 study guide."""

import json
import re
import sys
from hashlib import sha256
from pathlib import Path
from typing import Callable

from sacrebleu.metrics import BLEU


PASS_THRESHOLD = 9
CRITICAL_CATEGORIES = (
    "guide_exists",
    "organized_sections",
    "task_integrity",
)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(#([^)]+)\)")


def normalize_heading(heading: str) -> str:
    """Return the deterministic GitHub-style anchor used by this fixture."""
    plain = re.sub(r"[^a-z0-9\s-]", "", heading.lower())
    return "-".join(plain.split())


def markdown_headings(text: str) -> list[tuple[int, str]]:
    """Return headings outside fenced code blocks."""
    headings = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and (match := HEADING_PATTERN.match(line)):
            headings.append((len(match.group(1)), normalize_heading(match.group(2))))
    return headings


def require(condition: bool, message: str) -> str:
    """Return evidence or fail one binary check."""
    if not condition:
        raise ValueError(message)
    return message


def rouge_l_f1(candidate: str, reference: str) -> float:
    """Return token-level ROUGE-L F1 as a percentage."""
    candidate_tokens = re.findall(r"\w+", candidate.lower())
    reference_tokens = re.findall(r"\w+", reference.lower())
    if not candidate_tokens or not reference_tokens:
        return 0.0
    previous = [0] * (len(reference_tokens) + 1)
    for candidate_token in candidate_tokens:
        current = [0]
        for index, reference_token in enumerate(reference_tokens, start=1):
            current.append(
                previous[index - 1] + 1
                if candidate_token == reference_token
                else max(previous[index], current[-1])
            )
        previous = current
    return round(
        200 * previous[-1] / (len(candidate_tokens) + len(reference_tokens)), 4
    )


def evaluate(
    checks: dict[str, Callable[[], str]],
    result: Path,
    metrics: dict[str, float],
) -> int:
    """Run binary checks and write category evidence."""
    outcomes: dict[str, bool] = {}
    evidence: dict[str, list[str]] = {}
    for name, check in checks.items():
        try:
            evidence[name] = [check()]
            outcomes[name] = True
        except Exception as error:
            evidence[name] = [f"failed: {error}"]
            outcomes[name] = False
            print(f"{name}: {error}", file=sys.stderr)
    total = sum(outcomes.values())
    score = {
        "categories": {
            name: {
                "points": int(outcomes[name]),
                "max_points": 1,
                "evidence": evidence[name],
            }
            for name in checks
        },
        "total": total,
        "pass_threshold": PASS_THRESHOLD,
        "critical_categories": list(CRITICAL_CATEGORIES),
        "metrics": metrics,
    }
    result.mkdir(parents=True, exist_ok=True)
    (result / "score.json").write_text(json.dumps(score, indent=2) + "\n")
    return int(
        total < PASS_THRESHOLD
        or any(not outcomes[name] for name in CRITICAL_CATEGORIES)
    )


def main() -> int:
    """Score structure, topic coverage, learning aids, and task integrity."""
    submission = Path(sys.argv[1])
    result = Path(sys.argv[2])
    guide = submission / "study-guide.md"
    text = guide.read_text() if guide.is_file() else ""
    lower = text.lower()
    reference = Path("/eval/reference.md").read_text()
    heading_pairs = markdown_headings(text)
    normalized_headings = [heading for _, heading in heading_pairs]
    toc_match = re.search(
        r"^#{2,6}\s+(?:Table of Contents|Contents)\s*$\n(.*?)(?=^#{2,6}\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    toc_links = LINK_PATTERN.findall(toc_match.group(1)) if toc_match else []
    checks: dict[str, Callable[[], str]] = {
        "guide_exists": lambda: require(guide.is_file(), "study-guide.md exists"),
        "markdown_title": lambda: require(
            any(level == 1 for level, _ in heading_pairs),
            "a Markdown H1 title is present",
        ),
        "organized_sections": lambda: require(
            sum(level == 2 for level, _ in heading_pairs) >= 3,
            "at least three descriptive H2 sections organize the guide",
        ),
        "table_of_contents": lambda: require(
            bool(toc_links) and all(link in normalized_headings for link in toc_links),
            "an optional table of contents links to existing headings",
        ),
        "unique_headings": lambda: require(
            len(normalized_headings) == len(set(normalized_headings)),
            "normalized headings are unique",
        ),
        "backpropagation": lambda: require(
            "backpropagation" in lower, "backpropagation is explained"
        ),
        "gradient_descent": lambda: require(
            "gradient descent" in lower, "gradient descent is explained"
        ),
        "self_attention": lambda: require(
            "self-attention" in lower, "self-attention is explained"
        ),
        "positional_encoding": lambda: require(
            "positional encoding" in lower, "positional encoding is explained"
        ),
        "encoder": lambda: require("encoder" in lower, "encoders are explained"),
        "decoder": lambda: require("decoder" in lower, "decoders are explained"),
        "code_example": lambda: require(
            len(re.findall(r"^```", text, re.MULTILINE)) >= 2,
            "a fenced code example is present",
        ),
        "practical_plan": lambda: require(
            "study plan" in lower
            and bool(re.search(r"week|day|practice|exercise", lower)),
            "a practical schedule or exercise plan is present",
        ),
        "task_integrity": lambda: require(
            sha256((submission / "TASK.md").read_bytes()).hexdigest()
            == Path("/eval/TASK.md.sha256").read_text().strip(),
            "TASK.md hash matches evaluator snapshot",
        ),
    }
    metrics = {
        "bleu": round(
            BLEU(effective_order=True).corpus_score([text], [[reference]]).score, 4
        ),
        "rouge_l_f1": rouge_l_f1(text, reference),
    }
    return evaluate(checks, result, metrics)


if __name__ == "__main__":
    raise SystemExit(main())
