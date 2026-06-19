"""Configuration for the architecture verification gate.

Reads from environment variables and wraps LocalModelConfig with
verification-specific settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import dotenv

from tinycua.config.local_model import LocalModelConfig


# Load .env.test or .env.test.example automatically
_env_loaded = False


def _ensure_env_loaded() -> None:
    """Load environment from .env.test (or .env.test.example as fallback)."""
    global _env_loaded  # noqa: PLW0603
    if _env_loaded:
        return

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    for candidate in (project_root / ".env.test", project_root / ".env.test.example"):
        if candidate.exists():
            dotenv.load_dotenv(candidate, override=False)
            break

    _env_loaded = True


@dataclass
class GateConfig:
    """Configuration for the verification gate.

    Wraps LocalModelConfig (LLM endpoint, model, API key) and adds
    verification-specific settings (timeouts, output paths).

    Attributes:
        local_model_config: LLM endpoint configuration.
        default_timeout_seconds: Per-path timeout in seconds.
        output_dir: Directory for verification output files.
    """

    local_model_config: LocalModelConfig
    default_timeout_seconds: int = 120
    output_dir: str = "test-results"

    @classmethod
    def from_env(cls) -> GateConfig:
        """Construct GateConfig from environment variables.

        Reads provider-specific vars first, then TinyCUA CLI aliases, then
        generic LLM_* fallbacks. Values are normally loaded from .env.test.

        Returns:
            GateConfig configured from environment variables.
        """
        _ensure_env_loaded()

        base_url = os.environ.get(
            "OPENAI_CHAT_COMPLETIONS_BASE_URL",
            os.environ.get(
                "TINYCUA_BASE_URL",
                os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
            ),
        )
        model = os.environ.get(
            "OPENAI_CHAT_COMPLETIONS_MODEL",
            os.environ.get("TINYCUA_MODEL", os.environ.get("LLM_MODEL", "")),
        )
        api_key = os.environ.get(
            "OPENAI_CHAT_COMPLETIONS_API_KEY",
            os.environ.get("TINYCUA_API_KEY", "not-needed"),
        )

        local_model_config = LocalModelConfig(
            base_url=base_url,
            model=model,
            api_key=api_key,
        )

        return cls(local_model_config=local_model_config)

    @property
    def provider(self) -> str:
        """Return the provider identifier for the LLM client."""
        return "openai-chat-completions"

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self.local_model_config.model

    @property
    def base_url(self) -> str:
        """Return the base URL."""
        return self.local_model_config.base_url

    @property
    def api_key(self) -> str:
        """Return the API key."""
        return self.local_model_config.api_key or "not-needed"
