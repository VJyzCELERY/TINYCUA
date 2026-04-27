"""User-facing configuration manager for TinyCUA.

Provides a three-way merge strategy: YAML > env > defaults.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import yaml
from tinycua_sdk.core.config import LLMConfig, MemoryConfig, SDKConfig, SessionConfig


class UserConfig:
    """User-facing configuration manager.

    Loads configuration from ~/.tinycua/config.yaml with explicit
    YAML > env > defaults merge logic.
    """

    DEFAULT_CONFIG_DIR = Path.home() / ".tinycua"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"

    @classmethod
    def load(cls, path: Path | None = None) -> SDKConfig:
        """Load config with priority: YAML > env > defaults.

        Merge strategy:
        1. Start with SDKConfig() defaults
        2. Overlay SDKConfig.from_env() values
        3. Overlay only explicitly set YAML values (if path exists)

        Args:
            path: Optional custom config file path. Defaults to
                ~/.tinycua/config.yaml.

        Returns:
            Merged SDKConfig instance.
        """
        # Start with defaults
        defaults = SDKConfig()

        # Overlay env values
        env_config = SDKConfig.from_env()
        merged = cls._deep_merge(defaults, env_config)

        # Overlay YAML values if file exists
        # Load YAML as plain dict to avoid Pydantic filling in defaults
        yaml_path = path or cls.DEFAULT_CONFIG_FILE
        if yaml_path.exists():
            with open(yaml_path, "r") as f:
                yaml_data: dict[str, Any] = yaml.safe_load(f) or {}

            if yaml_data:
                # Convert to dict and merge only explicitly set values
                merged_dict = cls._to_dict(merged)
                yaml_dict = cls._flatten_yaml(yaml_data)
                merged_dict = cls._merge_dicts(merged_dict, yaml_dict)
                # Convert nested dicts to Pydantic models
                if "llm" in merged_dict and isinstance(merged_dict["llm"], dict):
                    merged_dict["llm"] = LLMConfig(**merged_dict["llm"])
                if "memory" in merged_dict and isinstance(merged_dict["memory"], dict):
                    merged_dict["memory"] = MemoryConfig(**merged_dict["memory"])
                if "session" in merged_dict and isinstance(merged_dict["session"], dict):
                    merged_dict["session"] = SessionConfig(**merged_dict["session"])
                merged = SDKConfig(**merged_dict)

        return merged

    @classmethod
    def save(cls, config: SDKConfig, path: Path | None = None) -> None:
        """Save config to YAML file with 0o600 permissions.

        Args:
            config: SDKConfig instance to serialize.
            path: Optional custom file path. Defaults to
                ~/.tinycua/config.yaml.
        """
        save_path = path or cls.DEFAULT_CONFIG_FILE
        cls.ensure_config_dir_for_path(save_path)

        data = cls._to_dict(config)

        with open(save_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False)

        # Set permissions to 0o600 (owner read/write only)
        os.chmod(save_path, stat.S_IRUSR | stat.S_IWUSR)

    @classmethod
    def ensure_config_dir(cls) -> Path:
        """Create ~/.tinycua/ if it doesn't exist.

        Returns:
            Path to the config directory.
        """
        cls.DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        return cls.DEFAULT_CONFIG_DIR

    @classmethod
    def generate_default_config(cls, path: Path | None = None) -> SDKConfig:
        """Generate a default config file and return it.

        Creates ~/.tinycua/config.yaml with default values if it
        doesn't already exist.

        Returns:
            The default SDKConfig instance.
        """
        config_file = path or cls.DEFAULT_CONFIG_FILE

        if config_file.exists():
            return SDKConfig.from_yaml(config_file)

        cls.ensure_config_dir()
        default_config = SDKConfig()
        cls.save(default_config, path=config_file)
        return default_config

    @classmethod
    def ensure_config_dir_for_path(cls, path: Path) -> None:
        """Create parent directory for a config file path.

        Args:
            path: Path to config file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _deep_merge(cls, base: SDKConfig, overlay: SDKConfig) -> SDKConfig:
        """Deep merge two SDKConfig instances, overlay taking priority.

        Args:
            base: Base configuration.
            overlay: Overlay configuration (takes priority).

        Returns:
            New SDKConfig with merged values.
        """
        base_dict = cls._to_dict(base)
        overlay_dict = cls._to_dict(overlay)
        merged_dict = cls._merge_dicts(base_dict, overlay_dict)
        return SDKConfig(**merged_dict)

    @classmethod
    def _merge_dicts(
        cls, base: dict[str, Any], overlay: dict[str, Any]
    ) -> dict[str, Any]:
        """Recursively merge two dicts, overlay taking priority.

        Args:
            base: Base dictionary.
            overlay: Overlay dictionary (takes priority).

        Returns:
            Merged dictionary.
        """
        result = dict(base)
        for key, value in overlay.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = cls._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result

    @classmethod
    def _to_dict(cls, config: SDKConfig) -> dict[str, Any]:
        """Convert SDKConfig to a plain dict for YAML serialization.

        Args:
            config: SDKConfig instance.

        Returns:
            Dictionary representation suitable for YAML.
        """
        return {
            "llm": {
                "provider": config.llm.provider,
                "model": config.llm.model,
                "base_url": config.llm.base_url,
                "api_key": config.llm.api_key.get_secret_value(),
                "temperature": config.llm.temperature,
            },
            "memory": {
                "database_url": config.memory.database_url,
                "embedding_dimension": config.memory.embedding_dimension,
            },
            "session": {
                "max_turns": config.session.max_turns,
                "summary_enabled": config.session.summary_enabled,
            },
            "backend_url": config.backend_url,
            "environment": config.environment,
        }

    @classmethod
    def _flatten_yaml(cls, yaml_data: dict[str, Any]) -> dict[str, Any]:
        """Flatten YAML data to match SDKConfig structure.

        Only includes keys that are explicitly set in the YAML file.

        Args:
            yaml_data: Raw YAML data.

        Returns:
            Flattened dict with only explicitly set values.
        """
        result: dict[str, Any] = {}

        # Handle top-level keys
        if "backend_url" in yaml_data:
            result["backend_url"] = yaml_data["backend_url"]
        if "environment" in yaml_data:
            result["environment"] = yaml_data["environment"]

        # Handle nested llm config
        if "llm" in yaml_data and isinstance(yaml_data["llm"], dict):
            result["llm"] = {}
            for key in yaml_data["llm"]:
                result["llm"][key] = yaml_data["llm"][key]

        # Handle nested memory config
        if "memory" in yaml_data and isinstance(yaml_data["memory"], dict):
            result["memory"] = {}
            for key in yaml_data["memory"]:
                result["memory"][key] = yaml_data["memory"][key]

        # Handle nested session config
        if "session" in yaml_data and isinstance(yaml_data["session"], dict):
            result["session"] = {}
            for key in yaml_data["session"]:
                result["session"][key] = yaml_data["session"][key]

        return result
