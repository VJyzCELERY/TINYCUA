"""Statistical helpers for the data_analyst skill."""

from typing import Any


def describe_series(values: list[float]) -> dict[str, Any]:
    """Return basic statistics for a numeric series."""
    n = len(values)
    if n == 0:
        return {}
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    std = variance ** 0.5
    return {
        "count": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min": min(values),
        "max": max(values),
    }
