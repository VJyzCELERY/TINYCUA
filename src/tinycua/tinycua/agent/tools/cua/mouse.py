"""Mouse control tool for Computer-Use Agent.

Moves the mouse cursor and performs clicks.
Uses lazy imports for graceful degradation when dependencies are unavailable.
"""

from __future__ import annotations

from typing import Any

try:
    import pyautogui
    from tinycua_sdk.tools.decorators import tool

    @tool()
    def mouse_move(x: int, y: int) -> dict[str, Any]:
        """Move the mouse cursor to absolute coordinates.

        Args:
            x: X coordinate (pixels from left).
            y: Y coordinate (pixels from top).

        Returns:
            {"success": True} or {"error": "..."} on failure.
        """
        try:
            pyautogui.moveTo(x, y)
            return {"success": True}
        except Exception as e:
            return {"error": f"Mouse move failed: {e}"}

    @tool()
    def mouse_click(button: str = "left") -> dict[str, Any]:
        """Perform a mouse click.

        Args:
            button: Mouse button ("left", "right", "middle").

        Returns:
            {"success": True} or {"error": "..."} on failure.
        """
        try:
            pyautogui.click(button=button)
            return {"success": True}
        except Exception as e:
            return {"error": f"Mouse click failed: {e}"}

except ImportError:
    from tinycua_sdk.tools.decorators import tool

    @tool()
    def mouse_move(x: int, y: int) -> dict[str, Any]:  # noqa: ARG001
        """Move mouse (stub — pyautogui not installed).

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            Error dict indicating missing dependencies.
        """
        return {
            "error": (
                "Mouse control requires 'pyautogui'. "
                "Install with: pip install tinycua[cua]"
            )
        }

    @tool()
    def mouse_click(button: str = "left") -> dict[str, Any]:  # noqa: ARG001
        """Click mouse (stub — pyautogui not installed).

        Args:
            button: Mouse button.

        Returns:
            Error dict indicating missing dependencies.
        """
        return {
            "error": (
                "Mouse control requires 'pyautogui'. "
                "Install with: pip install tinycua[cua]"
            )
        }
