"""Menu system for TinyCUA TUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from tinycua.tui.app import ChatScreen, HelpScreen, SessionsListScreen, SettingsScreen
from tinycua.tui.commands import CommandParser

if TYPE_CHECKING:
    from textual.app import ComposeResult


@dataclass
class MenuOption:
    """Represents a menu option.

    Attributes:
        label: Display text for the menu option.
        action: Action identifier triggered on selection.
        key: Optional keyboard shortcut.
    """

    label: str
    action: str
    key: str | None = None


class MenuSystem:
    """Vertical menu system with keyboard navigation.

    Provides a selectable list of options with up/down arrow
    key navigation and enter to select.
    """

    def __init__(self, options: list[MenuOption], initial_index: int = 0) -> None:
        """Initialize menu system.

        Args:
            options: List of menu options.
            initial_index: Initial selected index (default: 0).
        """
        self._options = options
        self._selected_index = initial_index

    def _move_selection(self, delta: int) -> None:
        """Move selection by delta with wrap-around.

        Args:
            delta: Direction (+1 for down, -1 for up).
        """
        if not self._options:
            return
        self._selected_index = (self._selected_index + delta) % len(self._options)

    def move_up(self) -> None:
        """Move selection up."""
        self._move_selection(-1)

    def move_down(self) -> None:
        """Move selection down."""
        self._move_selection(1)

    def set_selected_index(self, index: int) -> None:
        """Set selected index directly, clamped to valid range.

        Args:
            index: Target index.
        """
        if not self._options:
            self._selected_index = 0
            return
        self._selected_index = max(0, min(index, len(self._options) - 1))

    def get_selected_action(self) -> str | None:
        """Get action of currently selected option.

        Returns:
            Action string or None if no options.
        """
        if not self._options:
            return None
        return self._options[self._selected_index].action

    def get_options(self) -> list[MenuOption]:
        """Get all menu options.

        Returns:
            List of menu options.
        """
        return self._options.copy()

    def get_selected_index(self) -> int:
        """Get current selected index.

        Returns:
            Selected index.
        """
        return self._selected_index


def create_main_menu() -> MenuSystem:
    """Create main menu with default options.

    Returns:
        MenuSystem with main menu options.
    """
    options = [
        MenuOption(label="New Chat", action="new_chat", key="n"),
        MenuOption(label="Sessions", action="sessions", key="s"),
        MenuOption(label="Settings", action="settings", key=","),
        MenuOption(label="Help", action="help", key="?"),
        MenuOption(label="Quit", action="quit", key="q"),
    ]
    return MenuSystem(options=options)


class MenuScreen(Screen):
    """Main menu screen with navigation options."""

    DEFAULT_CSS = """
    MenuScreen {
        align: center middle;
    }

    #menu-container {
        width: 40;
        height: auto;
        border: solid $primary;
        padding: 2;
    }

    #menu-title {
        text-align: center;
        margin-bottom: 2;
    }

    #menu-options {
        layout: vertical;
        height: auto;
    }

    .menu-button {
        width: 100%;
        margin: 1 0;
    }
    """

    def __init__(self) -> None:
        """Initialize the menu screen."""
        super().__init__()
        self._menu_system = create_main_menu()

    def compose(self) -> ComposeResult:
        """Compose the menu screen layout."""
        yield Container(
            Static("[bold]TinyCUA Menu[/bold]", id="menu-title"),
            Vertical(id="menu-options"),
            id="menu-container",
        )

    def on_mount(self) -> None:
        """Handle screen mount."""
        self._populate_menu()

    def _populate_menu(self) -> None:
        """Populate menu buttons."""
        container = self.query_one("#menu-options", Vertical)
        container.remove_children()

        for option in self._menu_system.get_options():
            container.mount(
                Button(option.label, id=f"btn-{option.action}", classes="menu-button"),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        if button_id:
            action = button_id.replace("btn-", "")
            self._handle_action(action)

    def _handle_action(self, action: str) -> None:
        """Handle menu action."""
        if action == "new_chat":
            self.app.push_screen(ChatScreen(None))
        elif action == "sessions":
            self.app.push_screen(SessionsListScreen(None))
        elif action == "settings":
            self.app.push_screen(SettingsScreen())
        elif action == "help":
            self.app.push_screen(HelpScreen(CommandParser()))
        elif action == "quit":
            self.app.exit()
