"""Pydantic-based immutable SDK configuration system."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from tinycua_sdk.core.providers import DEFAULT_BASE_URL, OPENAI_COMPATIBLE


class LLMConfig(BaseModel):
    """Configuration for the LLM provider."""

    model_config = ConfigDict(frozen=True)

    provider: str = OPENAI_COMPATIBLE
    model: str = "qwen/qwen3.5-9b"
    base_url: str = DEFAULT_BASE_URL
    api_key: SecretStr = SecretStr("")
    temperature: float = 1.0


class MemoryConfig(BaseModel):
    """Configuration for memory/storage."""

    model_config = ConfigDict(frozen=True)

    database_url: str = "sqlite:///./tinycua.db"
    embedding_dimension: int = 1536


class LoopConfig(BaseModel):
    """Configuration for agent loop."""

    model_config = ConfigDict(frozen=True)

    type: str = "default"
    max_iterations: int = 5


class SkillsConfig(BaseModel):
    """Configuration for skills system."""

    model_config = ConfigDict(frozen=True)

    directories: list[str] = Field(
        default_factory=lambda: [
            os.path.expanduser("~/.tinycua/skills"),
            "./skills",
        ]
    )
    auto_load: bool = True
    auto_improve: bool = True


class SDKConfig(BaseModel):
    """Top-level immutable SDK configuration."""

    model_config = ConfigDict(frozen=True)

    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    backend_url: str = "http://localhost:8000"
    environment: str = "dev"

    def get_skill_directories(self) -> list[Path]:
        """Get skill directories as Path objects.

        Returns:
            List of Path objects for skill directories
        """
        return [Path(d) for d in self.skills.directories]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SDKConfig":
        """Load configuration from a YAML file.

        Args:
            path: Path to YAML configuration file.

        Returns:
            SDKConfig instance with values from the YAML file.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            yaml.YAMLError: If the file contains invalid YAML.
            pydantic.ValidationError: If config values fail validation.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r") as f:
            data: dict[str, Any] = yaml.safe_load(f)

        if data is None:
            data = {}

        return cls(**data)

    @classmethod
    def from_env(cls) -> "SDKConfig":
        """Load configuration from environment variables.

        Returns:
            SDKConfig instance with values from environment variables.
        """
        data: dict[str, Any] = {}

        env = os.getenv("TINYCUA_ENV")
        if env is not None:
            data["environment"] = env

        backend_url = os.getenv("TINYCUA_BACKEND_URL")
        if backend_url is not None:
            data["backend_url"] = backend_url

        llm_data: dict[str, Any] = {}

        api_key = os.getenv("TINYCUA_API_KEY")
        if api_key is not None:
            llm_data["api_key"] = SecretStr(api_key)

        provider = os.getenv("TINYCUA_PROVIDER")
        if provider is not None:
            llm_data["provider"] = provider

        model = os.getenv("TINYCUA_MODEL")
        if model is not None:
            llm_data["model"] = model

        base_url = os.getenv("TINYCUA_BASE_URL")
        if base_url is not None:
            llm_data["base_url"] = base_url

        if llm_data:
            data["llm"] = llm_data

        database_url = os.getenv("TINYCUA_DATABASE_URL")
        if database_url is not None:
            data["memory"] = {"database_url": database_url}

        loop_type = os.getenv("TINYCUA_LOOP_TYPE")
        if loop_type is not None:
            data["loop"] = {"type": loop_type}

        return cls(**data)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "SDKConfig":
        """Load config with priority: YAML > env > defaults.

        Args:
            path: Optional path to YAML file. If provided, YAML values
                override environment variables.

        Returns:
            Merged SDKConfig instance.
        """
        if path is not None:
            return cls.from_yaml(path)

        return cls.from_env()
