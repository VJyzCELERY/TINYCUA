"""DigestedInformation model for structured context digestion."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DigestedInformation:
    """Structured output from InformationDigesterNode.

    Produced by InformationDigesterNode and consumed by WorkerNode
    (or ResponseNode). Preserves original query for downstream use.

    Attributes:
        context_summary: High-level summary of gathered context.
            Contains original user query in fallback case.
        key_points: List of key points extracted from context.
        advisory_instructions: Advisory notes for downstream processing.
        constraints: Known constraints or limitations.
        known_gaps: Gaps identified in gathered context.
        original_query: The original user query, always preserved.
    """

    context_summary: str = ""
    key_points: list[str] = field(default_factory=list)
    advisory_instructions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    known_gaps: list[str] = field(default_factory=list)
    original_query: str = ""

    @classmethod
    def fallback(cls, original_query: str) -> DigestedInformation:
        """Create a fallback instance when no useful context is found.

        The fallback contains the original query in context_summary
        and a note that no additional context was available.

        Args:
            original_query: The original user query to preserve.

        Returns:
            A DigestedInformation instance with fallback context_summary.
        """
        return cls(
            context_summary=(
                f"The user asked: {original_query}. "
                "No useful extra information was found. "
                "Downstream should proceed with the user request "
                "and plan carefully before action."
            ),
            original_query=original_query,
        )

    @property
    def has_useful_context(self) -> bool:
        """Whether this digest contains useful context beyond the fallback."""
        return bool(self.key_points or self.advisory_instructions or self.constraints)
