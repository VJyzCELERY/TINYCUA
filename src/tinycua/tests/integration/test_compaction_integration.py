"""Integration tests for CompactionStrategy (Milestone 1.3)."""

from unittest.mock import MagicMock, patch

from tinycua.compaction.simple import SimpleCompaction
from tinycua.config.session_config import SessionConfig

# Note: CompactionStrategy, SimpleCompaction, and Session.compact_context()
# unit tests cover all behavioral cases in tests/unit/.
# This file only contains end-to-end integration tests.


class TestFactoryIntegration:
    """Verify factory creates SimpleCompaction with parent config."""

    # Known limitation: factory integration is deferred to Phase 2.
    # Config-passing to SimpleCompaction is validated by
    # test_simple_compaction_uses_parent_config (unit test).

    @patch("tinycua.factory.create_tinycua_agent")
    def test_factory_initializes_simple_compaction(self, mock_create):
        """create_tinycua_agent() initializes SimpleCompaction with parent config."""
        from tinycua.factory import create_tinycua_agent

        strategy = SimpleCompaction()
        config = SessionConfig(compaction_strategy=strategy)
        mock_create.return_value = MagicMock(
            loop=MagicMock(session_config=config)
        )
        agent = create_tinycua_agent(session_config=config)
        mock_create.assert_called_once_with(session_config=config)
        assert agent.loop.session_config.compaction_strategy is strategy
