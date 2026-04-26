"""Tests for sync resolver module."""

from tinycua_backend.sync.resolver import detect_conflict, resolve_conflict


class TestDetectConflict:
    """Tests for detect_conflict function."""

    def test_detect_conflict_different_updated_at(self):
        """Test conflict detected when updated_at differs."""
        local = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session A"}
        remote = {"updated_at": "2026-04-26T11:00:00Z", "name": "Session A"}
        assert detect_conflict(local, remote) is True

    def test_no_conflict_same_updated_at_and_name(self):
        """Test no conflict when both items are identical."""
        local = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session A"}
        remote = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session A"}
        assert detect_conflict(local, remote) is False

    def test_detect_conflict_different_name(self):
        """Test conflict detected when name differs."""
        local = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session A"}
        remote = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session B"}
        assert detect_conflict(local, remote) is True

    def test_detect_conflict_different_content(self):
        """Test conflict detected when content differs."""
        local = {"updated_at": "2026-04-26T10:00:00Z", "content": "Hello world", "role": "user"}
        remote = {"updated_at": "2026-04-26T10:00:00Z", "content": "Hello there", "role": "user"}
        assert detect_conflict(local, remote) is True

    def test_detect_conflict_different_role(self):
        """Test conflict detected when role differs."""
        local = {"updated_at": "2026-04-26T10:00:00Z", "content": "Hello", "role": "user"}
        remote = {"updated_at": "2026-04-26T10:00:00Z", "content": "Hello", "role": "assistant"}
        assert detect_conflict(local, remote) is True

    def test_no_conflict_same_all_fields(self):
        """Test no conflict when all fields match."""
        local = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session A"}
        remote = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session A"}
        assert detect_conflict(local, remote) is False

    def test_no_conflict_missing_updated_at_local(self):
        """Test no conflict when local updated_at is missing."""
        local = {"name": "Session A"}
        remote = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session B"}
        assert detect_conflict(local, remote) is False

    def test_no_conflict_missing_updated_at_remote(self):
        """Test no conflict when remote updated_at is missing."""
        local = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session A"}
        remote = {"name": "Session B"}
        assert detect_conflict(local, remote) is False


class TestResolveConflict:
    """Tests for resolve_conflict function."""

    def test_resolve_conflict_remote_wins_later(self):
        """Test remote wins when updated later."""
        local = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session A"}
        remote = {"updated_at": "2026-04-26T11:00:00Z", "name": "Session B"}
        winner, resolution = resolve_conflict(local, remote)
        assert resolution == "remote_wins"
        assert winner["name"] == "Session B"

    def test_resolve_conflict_local_wins_later(self):
        """Test local wins when updated later."""
        local = {"updated_at": "2026-04-26T12:00:00Z", "name": "Session A"}
        remote = {"updated_at": "2026-04-26T11:00:00Z", "name": "Session B"}
        winner, resolution = resolve_conflict(local, remote)
        assert resolution == "local_wins"
        assert winner["name"] == "Session A"

    def test_resolve_conflict_same_timestamp_local_wins(self):
        """Test local wins when timestamps are equal."""
        local = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session A"}
        remote = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session B"}
        winner, resolution = resolve_conflict(local, remote)
        assert resolution == "local_wins"
        assert winner["name"] == "Session A"

    def test_resolve_conflict_missing_updated_at_local(self):
        """Test conflict resolution when local has missing updated_at - remote wins."""
        local = {"name": "Session A"}
        remote = {"updated_at": "2026-04-26T10:00:00Z", "name": "Session B"}
        winner, resolution = resolve_conflict(local, remote)
        assert resolution == "remote_wins"
