"""Tests for TUI menu system."""

import pytest


class TestMenuOption:
    """Test MenuOption dataclass."""

    def test_menu_option_creation(self):
        """Test creating a menu option."""
        from tinycua.tui.menu import MenuOption

        option = MenuOption(label="New Chat", action="new_chat")
        assert option.label == "New Chat"
        assert option.action == "new_chat"

    def test_menu_option_with_key(self):
        """Test menu option with keyboard shortcut."""
        from tinycua.tui.menu import MenuOption

        option = MenuOption(label="Quit", action="quit", key="q")
        assert option.key == "q"


class TestMenuSystem:
    """Test MenuSystem class."""

    def test_menu_system_initializes(self):
        """Test menu system initializes with options."""
        from tinycua.tui.menu import MenuOption, MenuSystem

        options = [
            MenuOption(label="New Chat", action="new_chat"),
            MenuOption(label="Quit", action="quit"),
        ]
        menu = MenuSystem(options=options)
        assert len(menu._options) == 2
        assert menu._selected_index == 0

    def test_menu_system_selected_option(self):
        """Test getting selected option."""
        from tinycua.tui.menu import MenuOption, MenuSystem

        options = [
            MenuOption(label="New Chat", action="new_chat"),
            MenuOption(label="Quit", action="quit"),
        ]
        menu = MenuSystem(options=options)
        assert menu.get_selected_action() == "new_chat"

    def test_menu_system_move_selection_down(self):
        """Test moving selection down wraps around."""
        from tinycua.tui.menu import MenuOption, MenuSystem

        options = [
            MenuOption(label="A", action="a"),
            MenuOption(label="B", action="b"),
            MenuOption(label="C", action="c"),
        ]
        menu = MenuSystem(options=options)
        menu._move_selection(1)
        assert menu._selected_index == 1
        menu._move_selection(1)
        assert menu._selected_index == 2
        menu._move_selection(1)
        assert menu._selected_index == 0

    def test_menu_system_move_selection_up(self):
        """Test moving selection up wraps around."""
        from tinycua.tui.menu import MenuOption, MenuSystem

        options = [
            MenuOption(label="A", action="a"),
            MenuOption(label="B", action="b"),
            MenuOption(label="C", action="c"),
        ]
        menu = MenuSystem(options=options, initial_index=2)
        menu._move_selection(-1)
        assert menu._selected_index == 1
        menu._move_selection(-1)
        assert menu._selected_index == 0
        menu._move_selection(-1)
        assert menu._selected_index == 2

    def test_menu_system_empty_options(self):
        """Test menu with no options handles movement gracefully."""
        from tinycua.tui.menu import MenuSystem

        menu = MenuSystem(options=[])
        menu._move_selection(1)
        assert menu._selected_index == 0
        menu._move_selection(-1)
        assert menu._selected_index == 0

    def test_menu_system_set_selected_index(self):
        """Test setting selected index directly."""
        from tinycua.tui.menu import MenuOption, MenuSystem

        options = [
            MenuOption(label="A", action="a"),
            MenuOption(label="B", action="b"),
            MenuOption(label="C", action="c"),
        ]
        menu = MenuSystem(options=options)
        menu.set_selected_index(2)
        assert menu._selected_index == 2
        assert menu.get_selected_action() == "c"

    def test_menu_system_set_invalid_index(self):
        """Test setting invalid index clamps to valid range."""
        from tinycua.tui.menu import MenuOption, MenuSystem

        options = [
            MenuOption(label="A", action="a"),
            MenuOption(label="B", action="b"),
        ]
        menu = MenuSystem(options=options)
        menu.set_selected_index(10)
        assert menu._selected_index == 1
        menu.set_selected_index(-1)
        assert menu._selected_index == 0
