"""Web research utilities — loaded alongside the skill but not auto-registered as tools."""


def rank_sources(results: list[dict]) -> list[dict]:
    """Rank search results by relevance and authority."""
    # In a real implementation this would use heuristics or an LLM call
    return sorted(results, key=lambda r: r.get("score", 0), reverse=True)


def extract_snippets(html: str, max_length: int = 500) -> str:
    """Extract readable text snippets from raw HTML."""
    # Stripped-down version for the example
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]
