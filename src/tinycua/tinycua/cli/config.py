"""Environment variable and CLI config loading for tinycua run."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from tinycua_sdk.agent.llm_model import LanguageModel

_PROJECT_DIR = Path(__file__).resolve().parents[2]


def _load_default_env() -> None:
    """Load the project ``.env`` before argparse evaluates env-derived defaults.

    ``argparse`` reads ``os.environ`` at parse time to resolve defaults such as
    ``--worker-effort`` and ``--provider-type``. If ``.env`` is only loaded
    inside ``run()`` (after parsing), those defaults are frozen to the
    pre-``.env`` values and the user's settings in ``.env`` are silently
    ignored. Loading ``src/tinycua/.env`` here ensures env-derived argparse
    defaults see the user's configured values. Shell-provided env vars always
    win (``override=False``).
    """
    candidates = [Path.cwd() / ".env", _PROJECT_DIR / ".env"]
    loaded: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in loaded or not resolved.exists():
            continue
        load_dotenv(resolved, override=False)
        loaded.add(resolved)


def load_config(
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    provider_type: str | None = None,
) -> dict[str, str]:
    """Load configuration from environment variables with CLI overrides.

    Resolution order:
      1. CLI flags (base_url, api_key, model, provider_type) take priority when provided.
      2. Environment variables (TINYCUA_BASE_URL, TINYCUA_API_KEY, TINYCUA_MODEL,
         TINYCUA_PROVIDER_TYPE) are used as fallback.
      3. Default model is "llama3" when neither CLI nor env var is set.
      4. Default provider_type is "openai-chat-completions" when neither CLI
         nor env var is set.

    Args:
        base_url: CLI override for base URL, or None to use env var.
        api_key: CLI override for API key, or None to use env var.
        model: CLI override for model name, or None to use env var.
        provider_type: CLI override for provider type, or None to use env var.

    Returns:
        Dict with keys: base_url, api_key, model, provider_type (all str).

    Raises:
        ValueError: If base_url or api_key is missing after merging
            CLI overrides and environment variables.
    """
    resolved_base_url = base_url or os.environ.get("TINYCUA_BASE_URL")
    resolved_api_key = api_key or os.environ.get("TINYCUA_API_KEY")
    resolved_model = model or os.environ.get("TINYCUA_MODEL", "llama3")
    resolved_provider_type = provider_type or os.environ.get(
        "TINYCUA_PROVIDER_TYPE", "openai-chat-completions"
    )

    if not resolved_base_url:
        msg = (
            "base_url is required. Set TINYCUA_BASE_URL environment variable "
            "or provide --provider-url flag."
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
        "provider_type": resolved_provider_type,
    }


def build_language_model(config: dict[str, str]) -> LanguageModel:
    """Build the SDK LanguageModel expected by Agent.__init__.

    Args:
        config: Mapping returned by ``load_config``. Must include
            ``provider_type`` so the SDK routes to the correct API
            (chat completitions vs responses).

    Returns:
        OpenAI-compatible model configuration for TinyCUA runs.
    """
    return LanguageModel(
        provider=config.get("provider_type", "openai-chat-completions"),
        model_name=config["model"],
        base_url=config["base_url"],
        api_key=config["api_key"],
    )
