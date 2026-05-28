"""Unit tests for skill improver."""

import pytest
from tinycua_sdk.skills.improver import SkillImprover, SkillUsage, SkillImprovement


class TestSkillImprover:
    """Tests for SkillImprover class."""

    @pytest.fixture
    def improver(self):
        return SkillImprover()

    def test_improver_init(self, improver):
        """SkillImprover initializes empty."""
        assert improver._usage_history == []
        assert improver._improvements == []

    @pytest.mark.asyncio
    async def test_track_usage_success(self, improver):
        """Can track successful skill usage."""
        await improver.track_usage("test_skill", success=True, duration_ms=100)
        assert len(improver._usage_history) == 1
        assert improver._usage_history[0].skill_name == "test_skill"
        assert improver._usage_history[0].success is True

    @pytest.mark.asyncio
    async def test_track_usage_failure(self, improver):
        """Can track failed skill usage."""
        await improver.track_usage(
            "test_skill", success=False, error="Something went wrong", duration_ms=50
        )
        assert len(improver._usage_history) == 1
        assert improver._usage_history[0].success is False
        assert improver._usage_history[0].error == "Something went wrong"

    @pytest.mark.asyncio
    async def test_analyze_patterns_empty(self, improver):
        """Empty usage history returns empty patterns."""
        patterns = await improver.analyze_patterns()
        assert patterns == {}

    @pytest.mark.asyncio
    async def test_analyze_patterns_single_skill(self, improver):
        """Can analyze patterns for single skill."""
        await improver.track_usage("test_skill", success=True, duration_ms=100)
        await improver.track_usage("test_skill", success=True, duration_ms=200)

        patterns = await improver.analyze_patterns()

        assert "test_skill" in patterns
        assert patterns["test_skill"]["total_uses"] == 2
        assert patterns["test_skill"]["successful_uses"] == 2
        assert patterns["test_skill"]["success_rate"] == 1.0
        assert patterns["test_skill"]["avg_duration_ms"] == 150

    @pytest.mark.asyncio
    async def test_analyze_patterns_multiple_skills(self, improver):
        """Can analyze patterns for multiple skills."""
        await improver.track_usage("skill_a", success=True)
        await improver.track_usage("skill_b", success=True)
        await improver.track_usage("skill_a", success=False)

        patterns = await improver.analyze_patterns()

        assert len(patterns) == 2
        assert patterns["skill_a"]["total_uses"] == 2
        assert patterns["skill_b"]["total_uses"] == 1

    @pytest.mark.asyncio
    async def test_generate_improvements_low_success_rate(self, improver):
        """Generates improvement when success rate is low."""
        await improver.track_usage("test_skill", success=False)
        await improver.track_usage("test_skill", success=False)
        await improver.track_usage("test_skill", success=True)

        patterns = await improver.analyze_patterns()
        improvements = await improver.generate_improvements(patterns)

        improvement_types = [i.improvement_type for i in improvements]
        assert "prompt_refinement" in improvement_types

    @pytest.mark.asyncio
    async def test_generate_improvements_slow_execution(self, improver):
        """Generates improvement when execution is slow."""
        await improver.track_usage("test_skill", success=True, duration_ms=6000)
        await improver.track_usage("test_skill", success=True, duration_ms=7000)

        patterns = await improver.analyze_patterns()
        improvements = await improver.generate_improvements(patterns)

        improvement_types = [i.improvement_type for i in improvements]
        assert "efficiency" in improvement_types

    @pytest.mark.asyncio
    async def test_generate_improvements_common_errors(self, improver):
        """Generates improvement for common errors."""
        await improver.track_usage("test_skill", success=False, error="Timeout")
        await improver.track_usage("test_skill", success=False, error="Timeout")
        await improver.track_usage("test_skill", success=True)

        patterns = await improver.analyze_patterns()
        improvements = await improver.generate_improvements(patterns)

        improvement_types = [i.improvement_type for i in improvements]
        assert "error_handling" in improvement_types

    @pytest.mark.asyncio
    async def test_get_improvements_all(self, improver):
        """Can get all improvements."""
        await improver.track_usage("skill_a", success=False)
        await improver.track_usage("skill_a", success=False)
        await improver.track_usage("skill_a", success=True)
        await improver.track_usage("skill_b", success=False)
        await improver.track_usage("skill_b", success=False)
        await improver.track_usage("skill_b", success=True)

        patterns = await improver.analyze_patterns()
        await improver.generate_improvements(patterns)

        improvements = improver.get_improvements()
        assert len(improvements) >= 2

    @pytest.mark.asyncio
    async def test_get_improvements_filtered(self, improver):
        """Can get improvements filtered by skill name."""
        await improver.track_usage("skill_a", success=False)
        await improver.track_usage("skill_a", success=False)
        await improver.track_usage("skill_a", success=True)
        await improver.track_usage("skill_b", success=False)

        patterns = await improver.analyze_patterns()
        await improver.generate_improvements(patterns)

        improvements = improver.get_improvements("skill_a")
        assert len(improvements) >= 1
        assert improvements[0].skill_name == "skill_a"

    def test_clear_history(self, improver):
        """Can clear usage history."""
        improver._usage_history.append(
            SkillUsage(skill_name="test", success=True)
        )
        improver.clear_history()
        assert improver._usage_history == []

    def test_clear_improvements(self, improver):
        """Can clear improvements."""
        improver._improvements.append(
            SkillImprovement(
                skill_name="test",
                improvement_type="test",
                description="test",
            )
        )
        improver.clear_improvements()
        assert improver._improvements == []


class TestSkillUsage:
    """Tests for SkillUsage dataclass."""

    def test_skill_usage_defaults(self):
        """SkillUsage has sensible defaults."""
        usage = SkillUsage(skill_name="test")
        assert usage.success is True
        assert usage.error is None
        assert usage.duration_ms == 0


class TestSkillImprovement:
    """Tests for SkillImprovement dataclass."""

    def test_skill_improvement_defaults(self):
        """SkillImprovement has sensible defaults."""
        imp = SkillImprovement(skill_name="test", improvement_type="test", description="test")
        assert imp.generated_at is not None
