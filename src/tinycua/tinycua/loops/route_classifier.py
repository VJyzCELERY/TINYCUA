"""Deterministic decision-route classification helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


class RouteClassificationError(ValueError):
    """Raised when a route response cannot be mapped unambiguously."""


@dataclass(frozen=True)
class RouteClassifier:
    """Classify raw LLM text into one exact allowed route label."""

    allowed_labels: list[str]
    fallback_label: str | None = None

    def classify(self, raw_response: str) -> str:
        """Return an allowed route label from raw LLM output.

        Supports exact labels, trailing punctuation, and JSON objects with a
        ``route`` or ``route_label`` field. Substring matching is intentionally
        rejected because it can silently choose the wrong route.
        """
        normalized_labels = {self._normalize(label): label for label in self.allowed_labels}
        candidates = self._candidate_values(raw_response)

        for candidate in candidates:
            normalized = self._normalize(candidate)
            if normalized in normalized_labels:
                return normalized_labels[normalized]

        token_matches = self._token_label_matches(raw_response, normalized_labels)
        if len(token_matches) == 1:
            return token_matches[0]

        if self.fallback_label is not None:
            return self.fallback_label
        msg = f"Unable to classify route {raw_response!r} into {self.allowed_labels}"
        raise RouteClassificationError(msg)

    def validate(self, raw_response: str) -> bool:
        """Return whether raw_response maps to an allowed label."""
        try:
            self.classify(raw_response)
        except RouteClassificationError:
            return False
        return True

    def _candidate_values(self, raw_response: str) -> list[str]:
        text = raw_response.strip()
        candidates = [text]
        if not text:
            return candidates

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            for key in ("route", "route_label", "label"):
                value = parsed.get(key)
                if isinstance(value, str):
                    candidates.insert(0, value)

        route_match = re.fullmatch(r"route\s*:\s*([A-Za-z0-9_-]+)[.!?]?", text, re.I)
        if route_match:
            candidates.insert(0, route_match.group(1))

        return candidates

    def _normalize(self, value: str) -> str:
        return value.strip().lower().strip(".!?;:,`'\"")

    def _token_label_matches(
        self,
        raw_response: str,
        normalized_labels: dict[str, str],
    ) -> list[str]:
        """Return labels present as full tokens, not substrings."""
        tokens = {
            self._normalize(token)
            for token in re.split(r"\s+", raw_response)
            if token.strip()
        }
        return [label for normalized, label in normalized_labels.items() if normalized in tokens]
