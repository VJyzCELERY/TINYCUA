"""Keyboard input tool for Computer-Use Agent.

Types text and presses keys using the keyboard.
Uses lazy imports for graceful degradation when dependencies are unavailable.
"""

from __future__ import annotations

from typing import Any

try:
    import pyautogui
    from tinycua_sdk.tools.decorators import tool

    @tool()
    def keyboard_type(text: str) -> dict[str, Any]:
        """Type text using the keyboard.

        Args:
            text: Text to type.

        Returns:
            {"success": True} or {"error": "..."} on failure.
        """
        try:
            pyautogui.typewrite(text)
            return {"success": True}
        except Exception as e:
            return {"error": f"Keyboard type failed: {e}"}

    @tool()
    def keyboard_press(key: str) -> dict[str, Any]:
        """Press a specific key or key combination.

        Args:
            key: Key name (e.g., "enter", "tab", "ctrl+c").

        Returns:
            {"success": True} or {"error": "..."} on failure.
        """
        try:
            if "+" in key:
                keys = key.split("+")
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(key)
            return {"success": True}
        except Exception as e:
            return {"error": f"Keyboard press failed: {e}"}

except ImportError:
    from tinycua_sdk.tools.decorators import tool

    @tool()
    def keyboard_type(text: str) -> dict[str, Any]:  # noqa: ARG001
        """Type text (stub — pyautogui not installed).

        Args:
            text: Text to type.

        Returns:
            Error dict indicating missing dependencies.
        """
        return {
            "error": (
                "Keyboard control requires 'pyautogui'. "
                "Install with: pip install tinycua[cua]"
            )
        }

    @tool()
    def keyboard_press(key: str) -> dict[str, Any]:  # noqa: ARG001
        """Press key (stub — pyautogui not installed).

        Args:
            key: Key name.

        Returns:
            Error dict indicating missing dependencies.
        """
        return {
            "error": (
                "Keyboard control requires 'pyautogui'. "
                "Install with: pip install tinycua[cua]"
            )
        }
