# Unit tests for Context Discovery


from tinycua_sdk.context.discovery import ContextDiscovery


class TestContextDiscovery:
    """Tests for the ContextDiscovery class."""

    def test_discover_priority_order(self, tmp_path):
        """Test that files are discovered in priority order."""
        # Create context files
        (tmp_path / "CLAUDE.md").write_text("CLAUDE content")
        (tmp_path / "AGENTS.md").write_text("AGENTS content")
        (tmp_path / ".hermes.md").write_text("HERMES content")

        discovery = ContextDiscovery(root_dir=tmp_path)
        found = discovery.discover()

        # Should be in priority order: .hermes > AGENTS > CLAUDE
        assert len(found) == 3
        assert found[0][0].name == ".hermes.md"
        assert found[1][0].name == "AGENTS.md"
        assert found[2][0].name == "CLAUDE.md"

    def test_discover_parent_directories(self, tmp_path):
        """Test discovery traverses parent directories."""
        # Create nested structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        (tmp_path / "CLAUDE.md").write_text("root")
        (subdir / "AGENTS.md").write_text("subdir")

        discovery = ContextDiscovery(root_dir=subdir)
        found = discovery.discover()

        assert len(found) == 2

    def test_load_contexts(self, tmp_path):
        """Test loading context file contents."""
        (tmp_path / "AGENTS.md").write_text("Test content")

        discovery = ContextDiscovery(root_dir=tmp_path)
        contents = discovery.load_contexts()

        assert len(contents) == 1
        assert contents[0] == "Test content"

    def test_merge_contexts(self, tmp_path):
        """Test merging multiple contexts."""
        (tmp_path / "AGENTS.md").write_text("First content")
        (tmp_path / "CLAUDE.md").write_text("Second content")

        discovery = ContextDiscovery(root_dir=tmp_path)
        merged = discovery.merge_contexts()

        assert "First content" in merged
        assert "Second content" in merged

    def test_discover_empty_directory(self, tmp_path):
        """Test discovery in directory with no context files."""
        discovery = ContextDiscovery(root_dir=tmp_path)
        found = discovery.discover()

        assert found == []

    def test_discover_respects_max_depth(self, tmp_path):
        """Test that discovery respects max_depth."""
        # Create nested directories
        for i in range(10):
            parent = tmp_path / ("dir" + str(i))
            parent.mkdir(exist_ok=True)
            (parent / "AGENTS.md").write_text(f"Level {i}")

        discovery = ContextDiscovery(root_dir=tmp_path, max_depth=3)
        found = discovery.discover()

        # Should find files but limited by max_depth
        assert len(found) <= 4  # At most 4 files (root + 3 levels)
