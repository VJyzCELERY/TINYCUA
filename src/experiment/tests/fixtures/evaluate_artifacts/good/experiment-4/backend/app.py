"""Minimal submitted application fixture."""

from pathlib import Path


def initialize_database() -> None:
    """Create the submitted SQLite marker used by this fixture."""
    Path("fixture.sqlite").touch()


initialize_database()
