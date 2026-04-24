"""Tests for TUI export/import screens."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Checkbox, RadioButton

from tinycua.storage.export_manager import ExportOptions
from tinycua.tui.app import (
    ConfirmScreen,
    ExportPreviewScreen,
    ExportScreen,
    FileBrowserScreen,
    ImportScreen,
)


class _TestApp(App[None]):
    """Minimal app for mounting screens under test."""

    def __init__(self) -> None:
        super().__init__()
        self.notifications: list[tuple[str, str]] = []
        self._session_store = MagicMock()
        self._local_memory_store = MagicMock()

    def compose(self) -> ComposeResult:
        yield from ()

    def notify(self, message: str, severity: str = "information") -> None:
        self.notifications.append((message, severity))

    def get_session_store(self):
        return self._session_store

    def get_memory_store(self):
        return self._local_memory_store


@pytest.fixture
def mock_deps(tmp_path: Path):
    """Return mocked dependencies for screen tests."""
    session_manager = MagicMock()
    session_manager.list_sessions.return_value = []
    agent_manager = MagicMock()
    agent_manager.list_agents.return_value = []
    memory_store = MagicMock()
    memory_store.list_keys.return_value = []
    skills_manager = MagicMock()
    skills_manager.list_skills.return_value = []
    return {
        "session_manager": session_manager,
        "agent_manager": agent_manager,
        "memory_store": memory_store,
        "skills_manager": skills_manager,
    }


class TestConfirmScreen:
    """Test ConfirmScreen callback behavior."""

    @pytest.mark.asyncio
    async def test_confirm_fires_callback(self):
        """ConfirmScreen should fire on_confirm when Yes is pressed."""
        confirmed = False

        def on_confirm() -> None:
            nonlocal confirmed
            confirmed = True

        app = _TestApp()
        async with app.run_test() as pilot:
            app.push_screen(ConfirmScreen("Are you sure?", on_confirm=on_confirm))
            await pilot.pause()
            await pilot.click("#btn-yes")

        assert confirmed is True

    @pytest.mark.asyncio
    async def test_cancel_does_not_fire_callback(self):
        """ConfirmScreen should not fire on_confirm when No is pressed."""
        confirmed = False

        def on_confirm() -> None:
            nonlocal confirmed
            confirmed = True

        app = _TestApp()
        async with app.run_test() as pilot:
            app.push_screen(ConfirmScreen("Are you sure?", on_confirm=on_confirm))
            await pilot.pause()
            await pilot.click("#btn-no")

        assert confirmed is False


class TestFileBrowserScreen:
    """Test FileBrowserScreen selection behavior."""

    @pytest.mark.asyncio
    async def test_file_browser_select_callback(self, tmp_path: Path):
        """FileBrowserScreen should invoke on_select with the chosen path."""
        selected_path = None

        def on_select(path: Path) -> None:
            nonlocal selected_path
            selected_path = path

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        app = _TestApp()
        async with app.run_test() as pilot:
            app.push_screen(
                FileBrowserScreen(
                    initial_path=tmp_path,
                    on_select=on_select,
                    select_file=True,
                )
            )
            await pilot.pause()
            screen = app.screen
            screen._current_path = test_file
            btn = app.screen.query_one("#btn-select", Button)
            btn.press()
            await pilot.pause()

        assert selected_path == test_file


class TestExportPreviewScreen:
    """Test ExportPreviewScreen button visibility and behavior."""

    @pytest.mark.asyncio
    async def test_shows_overwrite_and_rename_when_file_exists(
        self, mock_deps, tmp_path: Path
    ):
        """If output file exists, preview should show overwrite/rename/cancel buttons."""
        existing_file = tmp_path / "export.json"
        existing_file.write_text("{}")

        app = _TestApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ExportPreviewScreen(
                    session_store=mock_deps["session_manager"],
                    agent_manager=mock_deps["agent_manager"],
                    memory_store=mock_deps["memory_store"],
                    skills_manager=mock_deps["skills_manager"],
                    options=ExportOptions(),
                    output_path=existing_file,
                    export_format="json",
                )
            )
            await pilot.pause()
            assert app.screen.query_one("#btn-overwrite") is not None
            assert app.screen.query_one("#btn-rename") is not None
            assert app.screen.query_one("#btn-cancel") is not None

    @pytest.mark.asyncio
    async def test_shows_export_button_when_file_missing(
        self, mock_deps, tmp_path: Path
    ):
        """If output file does not exist, preview should show export/cancel buttons."""
        missing_file = tmp_path / "new_export.json"

        app = _TestApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ExportPreviewScreen(
                    session_store=mock_deps["session_manager"],
                    agent_manager=mock_deps["agent_manager"],
                    memory_store=mock_deps["memory_store"],
                    skills_manager=mock_deps["skills_manager"],
                    options=ExportOptions(),
                    output_path=missing_file,
                    export_format="json",
                )
            )
            await pilot.pause()
            assert app.screen.query_one("#btn-export") is not None
            assert app.screen.query_one("#btn-cancel") is not None

    @pytest.mark.asyncio
    async def test_rename_aborts_when_renamed_file_exists(
        self, mock_deps, tmp_path: Path
    ):
        """If renamed file also exists, export should abort with a warning."""
        existing_file = tmp_path / "export.json"
        existing_file.write_text("{}")

        # Pre-create the timestamped file so rename collides
        with patch("tinycua.tui.app.datetime.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "20250101-120000"
            timestamped = tmp_path / "export-20250101-120000.json"
            timestamped.write_text("{}")

            app = _TestApp()
            async with app.run_test() as pilot:
                app.push_screen(
                    ExportPreviewScreen(
                        session_store=mock_deps["session_manager"],
                        agent_manager=mock_deps["agent_manager"],
                        memory_store=mock_deps["memory_store"],
                        skills_manager=mock_deps["skills_manager"],
                        options=ExportOptions(),
                        output_path=existing_file,
                        export_format="json",
                    )
                )
                await pilot.pause()
                btn = app.screen.query_one("#btn-rename", Button)
                btn.press()
                await pilot.pause()

        messages = [m for m, _ in app.notifications]
        assert any(
            "cancelled" in m.lower() and "renamed file also exists" in m.lower()
            for m in messages
        )


class TestExportScreen:
    """Test ExportScreen checkbox-to-options mapping."""

    @pytest.mark.asyncio
    async def test_checkbox_state_maps_to_options(self, mock_deps, tmp_path: Path):
        """Toggling checkboxes should be reflected in widget state."""
        export_path = tmp_path / "export.json"

        app = _TestApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ExportScreen(
                    session_manager=mock_deps["session_manager"],
                    agent_manager=mock_deps["agent_manager"],
                    memory_store=mock_deps["memory_store"],
                    skills_manager=mock_deps["skills_manager"],
                )
            )
            await pilot.pause()
            # Uncheck sessions and memory via widget toggle
            app.screen.query_one("#chk-sessions", Checkbox).toggle()
            app.screen.query_one("#chk-memory", Checkbox).toggle()

            # Set output path via input
            app.screen.query_one("#export-output").value = str(export_path)

            # Verify widget states reflect intent
            assert app.screen.query_one("#chk-sessions", Checkbox).value is False
            assert app.screen.query_one("#chk-agents", Checkbox).value is True
            assert app.screen.query_one("#chk-memory", Checkbox).value is False
            assert app.screen.query_one("#chk-skills", Checkbox).value is True

    @pytest.mark.asyncio
    async def test_default_format_is_json(self, mock_deps):
        """Export format should default to JSON."""

        app = _TestApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ExportScreen(
                    session_manager=mock_deps["session_manager"],
                    agent_manager=mock_deps["agent_manager"],
                    memory_store=mock_deps["memory_store"],
                    skills_manager=mock_deps["skills_manager"],
                )
            )
            await pilot.pause()
            radio_set = app.screen.query_one("#export-format")
            pressed = radio_set.pressed_button
            assert pressed is not None
            assert pressed.id == "rad-json"


class TestImportScreen:
    """Test ImportScreen mode selection and preview."""

    @pytest.mark.asyncio
    async def test_mode_defaults_to_merge(self, mock_deps):
        """Import mode should default to MERGE."""

        app = _TestApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ImportScreen(
                    session_manager=mock_deps["session_manager"],
                    agent_manager=mock_deps["agent_manager"],
                    memory_store=mock_deps["memory_store"],
                    skills_manager=mock_deps["skills_manager"],
                )
            )
            await pilot.pause()
            radio_set = app.screen.query_one("#import-mode")
            pressed = radio_set.pressed_button
            assert pressed is not None
            assert pressed.id == "rad-merge"

    @pytest.mark.asyncio
    async def test_replace_mode_shows_confirmation(self, mock_deps, tmp_path: Path):
        """Selecting REPLACE mode should show a confirmation screen before importing."""
        import_file = tmp_path / "import.json"
        import_file.write_text('{"version": "1.0", "data": {}}')

        app = _TestApp()
        with patch.object(
            ImportScreen, "_update_preview", lambda self, path_str: None
        ):
            async with app.run_test() as pilot:
                app.push_screen(
                    ImportScreen(
                        session_manager=mock_deps["session_manager"],
                        agent_manager=mock_deps["agent_manager"],
                        memory_store=mock_deps["memory_store"],
                        skills_manager=mock_deps["skills_manager"],
                    )
                )
                await pilot.pause()
                app.screen.query_one("#import-path").value = str(import_file)

                # Switch to replace mode
                app.screen.query_one("#rad-replace", RadioButton).value = True

                # Click import
                app.screen.query_one("#btn-import", Button).press()
                await pilot.pause()

                # A ConfirmScreen should now be on top
                assert isinstance(app.screen, ConfirmScreen)
