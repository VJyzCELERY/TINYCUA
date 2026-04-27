"""Skill auto-improvement system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SkillUsage:
    """Tracks usage of a skill.

    Attributes:
        skill_name: Name of the skill used
        timestamp: When the skill was used
        success: Whether the skill execution was successful
        error: Error message if execution failed
        duration_ms: How long the skill took to execute
    """

    skill_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: str | None = None
    duration_ms: int = 0


@dataclass
class SkillImprovement:
    """Represents a procedural improvement to a skill.

    Attributes:
        skill_name: Name of the skill to improve
        improvement_type: Type of improvement (prompt, parameters, etc.)
        description: Description of the improvement
        generated_at: When the improvement was generated
    """

    skill_name: str
    improvement_type: str
    description: str
    generated_at: datetime = field(default_factory=datetime.now)


class SkillImprover:
    """Tracks skill usage and generates procedural improvements.

    Monitors skill usage patterns including frequency, success rate,
    and failure modes to generate procedural improvements.

    Example:
        improver = SkillImprover()

        await improver.track_usage("file_editor", success=True, duration_ms=150)

        patterns = await improver.analyze_patterns()
        improvements = await improver.generate_improvements(patterns)
    """

    def __init__(self):
        self._usage_history: list[SkillUsage] = []
        self._improvements: list[SkillImprovement] = []

    async def track_usage(
        self,
        skill_name: str,
        success: bool = True,
        error: str | None = None,
        duration_ms: int = 0,
    ) -> None:
        """Track skill usage.

        Records a skill usage event for analysis.

        Args:
            skill_name: Name of the skill used
            success: Whether execution was successful
            error: Error message if failed
            duration_ms: Execution time in milliseconds
        """
        usage = SkillUsage(
            skill_name=skill_name,
            success=success,
            error=error,
            duration_ms=duration_ms,
        )
        self._usage_history.append(usage)

    async def analyze_patterns(self) -> dict[str, dict[str, Any]]:
        """Analyze usage patterns for all skills.

        Returns:
            Dict mapping skill names to their usage statistics
        """
        patterns = {}

        for usage in self._usage_history:
            if usage.skill_name not in patterns:
                patterns[usage.skill_name] = {
                    "total_uses": 0,
                    "successful_uses": 0,
                    "failed_uses": 0,
                    "total_duration_ms": 0,
                    "errors": [],
                }

            stats = patterns[usage.skill_name]
            stats["total_uses"] += 1

            if usage.success:
                stats["successful_uses"] += 1
            else:
                stats["failed_uses"] += 1
                if usage.error:
                    stats["errors"].append(usage.error)

            stats["total_duration_ms"] += usage.duration_ms

        for skill_name, stats in patterns.items():
            if stats["total_uses"] > 0:
                stats["success_rate"] = stats["successful_uses"] / stats["total_uses"]
                stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["total_uses"]
            else:
                stats["success_rate"] = 0.0
                stats["avg_duration_ms"] = 0.0

        return patterns

    async def generate_improvements(
        self, patterns: dict[str, dict[str, Any]]
    ) -> list[SkillImprovement]:
        """Generate procedural improvements based on patterns.

        Args:
            patterns: Usage patterns from analyze_patterns()

        Returns:
            List of generated improvements
        """
        improvements = []

        for skill_name, stats in patterns.items():
            if stats["success_rate"] < 0.8 and stats["total_uses"] >= 3:
                improvement = SkillImprovement(
                    skill_name=skill_name,
                    improvement_type="prompt_refinement",
                    description=f"Success rate is {stats['success_rate']:.0%}. Consider improving instructions.",
                )
                improvements.append(improvement)
                self._improvements.append(improvement)

            if stats["avg_duration_ms"] > 5000 and stats["total_uses"] >= 2:
                improvement = SkillImprovement(
                    skill_name=skill_name,
                    improvement_type="efficiency",
                    description=f"Average duration {stats['avg_duration_ms']:.0f}ms exceeds threshold. Consider optimizing.",
                )
                improvements.append(improvement)
                self._improvements.append(improvement)

            if stats["errors"]:
                error_counts: dict[str, int] = {}
                for error in stats["errors"]:
                    error_counts[error] = error_counts.get(error, 0) + 1
                most_common_error = max(error_counts, key=error_counts.get)
                if error_counts[most_common_error] >= 2:
                    improvement = SkillImprovement(
                        skill_name=skill_name,
                        improvement_type="error_handling",
                        description=f"Common error: '{most_common_error}'. Add error handling.",
                    )
                    improvements.append(improvement)
                    self._improvements.append(improvement)

        return improvements

    async def persist_improvements(self, memory: Any) -> None:
        """Persist improvements to memory.

        Args:
            memory: Memory storage to persist improvements to
        """
        for improvement in self._improvements:
            key = f"skill_improvement:{improvement.skill_name}:{improvement.improvement_type}"
            value = {
                "skill_name": improvement.skill_name,
                "improvement_type": improvement.improvement_type,
                "description": improvement.description,
                "generated_at": improvement.generated_at.isoformat(),
            }

            if hasattr(memory, "set"):
                await memory.set(key, value)
            elif hasattr(memory, "store"):
                memory.store(key, value)

    def get_improvements(self, skill_name: str | None = None) -> list[SkillImprovement]:
        """Get stored improvements.

        Args:
            skill_name: Optional filter by skill name

        Returns:
            List of improvements
        """
        if skill_name is None:
            return self._improvements.copy()
        return [imp for imp in self._improvements if imp.skill_name == skill_name]

    def clear_history(self) -> None:
        """Clear usage history."""
        self._usage_history.clear()

    def clear_improvements(self) -> None:
        """Clear stored improvements."""
        self._improvements.clear()
