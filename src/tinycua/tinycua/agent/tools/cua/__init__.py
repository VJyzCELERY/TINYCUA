"""CUA tools package with conditional exports.

Exports screen capture, mouse, and keyboard tools when dependencies
are available. Falls back to empty exports when dependencies are missing.
"""

try:
    from tinycua.agent.tools.cua.keyboard import keyboard_press, keyboard_type
    from tinycua.agent.tools.cua.mouse import mouse_click, mouse_move
    from tinycua.agent.tools.cua.screen_capture import screen_capture

    __all__ = [
        "screen_capture",
        "mouse_move",
        "mouse_click",
        "keyboard_type",
        "keyboard_press",
    ]
except ImportError:
    __all__: list[str] = []
