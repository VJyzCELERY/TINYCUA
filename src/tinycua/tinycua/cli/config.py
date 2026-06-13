"""Environment variable and CLI config loading for tinycua run."""

from __future__ import annotations

import os


def load_config(
    base_url: str | None,
    api_key: str | None,
    model: str | None,
) -> dict[str, str]:
    """Load configuration from environment variables with CLI overrides.

    Resolution order:
      1. CLI flags (base_url, api_key, model) take priority when provided.
      2. Environment variables (TINYCUA_BASE_URL, TINYCUA_API_KEY, TINYCUA_MODEL)
         are used as fallback.
      3. Default model is "llama3" when neither CLI nor env var is set.

    Args:
        base_url: CLI override for base URL, or None to use env var.
        api_key: CLI override for API key, or None to use env var.
        model: CLI override for model name, or None to use env var.

    Returns:
        Dict with keys: base_url, api_key, model (all str).

    Raises:
        ValueError: If base_url or api_key is missing after merging
            CLI overrides and environment variables.
    """
    resolved_base_url = base_url or os.environ.get("TINYCUA_BASE_URL")
    resolved_api_key = api_key or os.environ.get("TINYCUA_API_KEY")
    resolved_model = model or os.environ.get("TINYCUA_MODEL", "llama3")

    if not resolved_base_url:
        msg = (
            "base_url is required. Set TINYCUA_BASE_URL environment variable "
            "or provide --base-url flag."
        )
        raise ValueError(msg)

    if not resolved_api_key:
        msg = (
            "api_key is required. Set TINYCUA_API_KEY environment variable "
            "or provide --api-key flag."
        )
        raise ValueError(msg)

    return {
        "base_url": resolved_base_url,
        "api_key": resolved_api_key,
        "model": resolved_model,
    }
