"""DigestedInformation dataclass for InformationDigesterNode output."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DigestedInformation:
    """Structured output from InformationDigesterNode.

    Captures the useful context gathered and summarized by the digester
    for downstream consumption (primarily ResponseNode).

    Attributes:
        context_summary: High-level summary of gathered context.
        key_points: Most important facts or findings.
        advisory_instructions: Guidance for downstream nodes on how to use the context.
        constraints: Limitations or caveats about the gathered context.
        known_gaps: Information that was sought but not found.
    """

    context_summary: str = ""
    key_points: list[str] = field(default_factory=list)
    advisory_instructions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    known_gaps: list[str] = field(default_factory=list)
