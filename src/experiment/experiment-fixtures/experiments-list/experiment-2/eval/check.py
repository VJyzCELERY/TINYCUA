"""Deterministically score the Experiment 2 research report."""

import json
import re
import sys
from hashlib import sha256
from pathlib import Path
from typing import Callable

from sacrebleu.metrics import BLEU


PASS_THRESHOLD = 12
CRITICAL_CATEGORIES = (
    "report_exists",
    "model_relevancy",
    "task_integrity",
)
MODEL_FAMILIES = ("gpt", "claude", "gemini", "kimi", "glm", "llama", "qwen")
REQUIRED_HEADINGS = (
    "scope",
    "models",
    "evidence",
    "benchmark interpretation",
    "conclusion",
)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
URL_PATTERN = re.compile(r"https?://[^\s)\]>]+")


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


def check_model_relevancy(text: str, models: tuple[str, ...]) -> str:
    """Require one bundled reference model name, tolerating formatting.

    Accepts space/hyphen interchange, an optional leading ``Claude``/``Anthropic``
    provider prefix, and trailing sentence punctuation so agents who write
    ``GPT 5.6 Sol``, ``Opus 4.8``, or ``Claude Fable 5.`` all pass.
    """
    for model in models:
        tokens = re.split(r"[\s.\-]+", model.strip())
        # ponytail: make the leading provider token optional for Claude-family
        # models so "Fable 5" and "Opus 4.8" match without the "Claude" prefix.
        if tokens[0].lower() in {"claude", "anthropic"}:
            prefix = r"(?:(?:claude|anthropic)[\s.\-]+)?"
            body_tokens = tokens[1:]
        else:
            prefix = r""
            body_tokens = tokens
        body = r"[\s.\-]+".join(re.escape(t) for t in body_tokens)
        pattern = rf"(?<!\w){prefix}{body}[.,;:]?(?!\w)"
        if re.search(pattern, text, re.IGNORECASE):
            return f"report names reference model {model}"
    raise ValueError("report does not name a bundled reference model")


def evaluate(
    checks: dict[str, Callable[[], str]],
    result: Path,
    metrics: dict[str, float],
) -> int:
    """Run binary checks and write transparent category evidence."""
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
    """Score report structure, model relevance, coverage, and integrity."""
    submission = Path(sys.argv[1])
    result = Path(sys.argv[2])
    report = submission / "report.md"
    text = report.read_text() if report.is_file() else ""
    lower = text.lower()
    reference_corpus = json.loads(Path("/eval/evidence.json").read_text())
    reference_models = tuple(reference_corpus["models"])
    reference = Path("/eval/reference.md").read_text()
    headings = [
        (len(match.group(1)), match.group(2).strip().lower())
        for line in text.splitlines()
        if (match := HEADING_PATTERN.match(line))
    ]
    families = [family for family in MODEL_FAMILIES if family in lower]
    h2_headings = [heading for level, heading in headings if level == 2]
    checks: dict[str, Callable[[], str]] = {
        "report_exists": lambda: require(report.is_file(), "report.md exists"),
        "exact_title": lambda: require(
            headings[:1] == [(1, "frontier llm report")], "exact H1 title is present"
        ),
        "required_chapters": lambda: require(
            h2_headings[:5] == list(REQUIRED_HEADINGS),
            "required H2 chapters occur once and in order",
        ),
        "unique_headings": lambda: require(
            len([heading for _, heading in headings])
            == len(set(heading for _, heading in headings)),
            "all headings are unique",
        ),
        "additional_unique_chapter": lambda: require(
            any(heading not in REQUIRED_HEADINGS for heading in h2_headings),
            "a non-duplicate additional H2 chapter earns a bonus point",
        ),
        "model_table": lambda: require(
            "| model | provider | evidence |" in lower,
            "required model table is present",
        ),
        "source_citations": lambda: require(
            len(set(URL_PATTERN.findall(text))) >= 3,
            "at least three distinct source URLs are cited",
        ),
        "model_families": lambda: require(
            len(families) >= 3, f"model families found: {', '.join(families)}"
        ),
        "comparison": lambda: require(
            bool(re.search(r"compar|versus|\bvs\.?\b|trade-?off", lower)),
            "explicit comparison or trade-off discussion is present",
        ),
        "capability": lambda: require("capability" in lower, "capability is covered"),
        "cost": lambda: require("cost" in lower, "cost is covered"),
        "latency": lambda: require("latency" in lower, "latency is covered"),
        "context_length": lambda: require(
            "context" in lower, "context length is covered"
        ),
        "safety": lambda: require("safety" in lower, "safety is covered"),
        "benchmark_methodology": lambda: require(
            all(term in lower for term in ("benchmark", "task", "prompt", "tool")),
            "benchmark dependence on task, prompting, and tools is explained",
        ),
        "reproducibility": lambda: require(
            "reproduc" in lower, "reproducibility is discussed"
        ),
        "contamination_limits": lambda: require(
            "contamin" in lower and ("limit" in lower or "evaluation" in lower),
            "contamination and evaluation limits are discussed",
        ),
        "model_relevancy": lambda: check_model_relevancy(text, reference_models),
        **{
            f"reference_{re.sub(r'[^a-z0-9]+', '_', model.lower()).strip('_')}": lambda model=model: (
                require(
                    model.lower() in lower, f"reference model covered: {model}"
                )
            )
            for model in reference_models
        },
        "reference_coverage": lambda: require(
            BLEU(max_ngram_order=1, effective_order=True)
            .corpus_score([text], [[reference]])
            .score
            >= 8.0,
            "reference BLEU-1 coverage is at least 8.0",
        ),
        "task_integrity": lambda: require(
            sha256((submission / "TASK.md").read_bytes()).hexdigest()
            == Path("/eval/TASK.md.sha256").read_text().strip(),
            "TASK.md hash matches evaluator copy",
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
