"""Pydantic-based immutable SDK configuration system."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class LLMConfig(BaseModel):
    """Default LLM configuration for SDK-wide defaults."""

    model_config = ConfigDict(frozen=True)

    provider: str = "openai-compatible"
    model: str = "gpt-4o-mini"
    base_url: str = "http://localhost:1234/v1"
    api_key: SecretStr = SecretStr("")
    temperature: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMConfig":
        """Deserialize from a plain dictionary."""
        return cls(**data)


class LoopConfig(BaseModel):
    """Default loop configuration."""

    model_config = ConfigDict(frozen=True)

    max_iterations: int = 5

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopConfig":
        """Deserialize from a plain dictionary."""
        return cls(**data)


class SkillsConfig(BaseModel):
    """Default skill loading configuration."""

    model_config = ConfigDict(frozen=True)

    directories: list[str] = Field(default_factory=lambda: ["./skills"])
    auto_load: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillsConfig":
        """Deserialize from a plain dictionary."""
        return cls(**data)


class SDKConfig(BaseModel):
    """Framework-level configuration."""

    model_config = ConfigDict(frozen=True)

    llm: LLMConfig = Field(default_factory=LLMConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    backend_url: str = "http://localhost:8000"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SDKConfig":
        """Deserialize from a plain dictionary."""
        return cls(**data)

    def to_yaml(self, path: str | Path) -> None:
        """Serialize to a YAML file.

        Args:
            path: Path to the output YAML file.
        """
        path = Path(path)
        with open(path, "w") as f:
            yaml.safe_dump(self.to_dict(), f, default_flow_style=False)

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
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r") as f:
            data: dict[str, Any] = yaml.safe_load(f)

        if data is None:
            data = {}

        return cls.from_dict(data)

    def to_json(self, path: str | Path) -> None:
        """Serialize to a JSON file.

        Args:
            path: Path to the output JSON file.
        """
        path = Path(path)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_json(cls, path: str | Path) -> "SDKConfig":
        """Load configuration from a JSON file.

        Args:
            path: Path to JSON configuration file.

        Returns:
            SDKConfig instance with values from the JSON file.

        Raises:
            FileNotFoundError: If the JSON file does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r") as f:
            data: dict[str, Any] = json.load(f)

        return cls.from_dict(data)

    @classmethod
    def from_env(cls) -> "SDKConfig":
        """Load configuration from environment variables.

        Returns:
            SDKConfig instance with values from environment variables.
        """
        data: dict[str, Any] = {}

        backend_url = os.getenv("TINYCUA_BACKEND_URL")
        if backend_url is not None:
            data["backend_url"] = backend_url

        llm_data: dict[str, Any] = {}

        api_key = os.getenv("TINYCUA_API_KEY")
        if api_key is not None:
            llm_data["api_key"] = api_key

        provider = os.getenv("TINYCUA_PROVIDER")
        if provider is not None:
            llm_data["provider"] = provider

        model = os.getenv("TINYCUA_MODEL")
        if model is not None:
            llm_data["model"] = model

        base_url = os.getenv("TINYCUA_BASE_URL")
        if base_url is not None:
            llm_data["base_url"] = base_url

        temperature = os.getenv("TINYCUA_TEMPERATURE")
        if temperature is not None:
            llm_data["temperature"] = float(temperature)

        if llm_data:
            data["llm"] = llm_data

        max_iterations = os.getenv("TINYCUA_MAX_ITERATIONS")
        if max_iterations is not None:
            data["loop"] = {"max_iterations": int(max_iterations)}

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
