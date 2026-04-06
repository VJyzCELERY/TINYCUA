"""Screen capture tool for Computer-Use Agent.

Captures the current screen and returns a base64-encoded image.
Uses lazy imports for graceful degradation when dependencies are unavailable.
"""

from __future__ import annotations

from typing import Any

try:
    import base64
    import io

    import mss
    from PIL import Image
    from tinycua_sdk.tools.decorators import tool

    @tool()
    def screen_capture(
        region: tuple[int, int, int, int] | None = None,
        quality: int = 85,
    ) -> dict[str, Any]:
        """Capture the current screen and return as base64-encoded image.

        Args:
            region: Optional (left, top, width, height) to capture
                specific area.
            quality: JPEG quality (1-100, default 85).

        Returns:
            Dict with image data: {"image": "<base64>", "format": "jpeg",
                "width": N, "height": N} or {"error": "..."} on failure.
        """
        try:
            with mss.mss() as sct:
                if region:
                    monitor = {
                        "left": region[0],
                        "top": region[1],
                        "width": region[2],
                        "height": region[3],
                    }
                else:
                    monitor = sct.monitors[1]  # Primary monitor

                screenshot = sct.grab(monitor)
                img = Image.frombytes(
                    "RGB", screenshot.size, screenshot.bgra, "raw", "BGRX"
                )

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality)
                buffer.seek(0)
                image_b64 = base64.b64encode(buffer.read()).decode("utf-8")

                return {
                    "image": image_b64,
                    "format": "jpeg",
                    "width": screenshot.width,
                    "height": screenshot.height,
                }
        except Exception as e:
            return {"error": f"Screen capture failed: {e}"}

except ImportError:
    from tinycua_sdk.tools.decorators import tool

    @tool()
    def screen_capture(
        region: tuple[int, int, int, int] | None = None,  # noqa: ARG001
        quality: int = 85,  # noqa: ARG001
    ) -> dict[str, Any]:
        """Capture the current screen (stub — mss/Pillow not installed).

        Args:
            region: Optional region tuple.
            quality: JPEG quality.

        Returns:
            Error dict indicating missing dependencies.
        """
        return {
            "error": (
                "Screen capture requires 'mss' and 'Pillow'. "
                "Install with: pip install tinycua[cua]"
            )
        }
