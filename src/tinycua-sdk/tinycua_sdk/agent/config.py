"""Agent configuration classes."""

import inspect
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from tinycua_sdk.tools.decorators import Tool

if TYPE_CHECKING:
    from tinycua_sdk.agent import Agent


def _substitute_env_vars(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively substitute environment variables in string values.

    Supports ${VAR_NAME} syntax. Raises ValueError if environment variable is not set.

    Args:
        data: Dictionary to process

    Returns:
        Dictionary with environment variables substituted

    Raises:
        ValueError: If environment variable is not set
    """
    pattern = re.compile(r"\$\{(\w+)\}")

    def substitute_value(value: Any) -> Any:
        if isinstance(value, str):

            def replace_match(match):
                var_name = match.group(1)
                env_value = os.environ.get(var_name)
                if env_value is None:
                    raise ValueError(f"Environment variable '{var_name}' is not set")
                return env_value

            return pattern.sub(replace_match, value)
        elif isinstance(value, dict):
            return {k: substitute_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [substitute_value(item) for item in value]
        else:
            return value

    return substitute_value(data)


@dataclass
class AgentPolicy:
    """Policy for agent behavior."""

    max_tool_calls: int = 10
    parallel_tool_calls: bool = True
    temperature: float = 1.0


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str = "assistant"
    instructions: str = ""
    system_prompt: str = "You are a helpful assistant."
    model: str = "gpt-5-nano"
    provider: str = "openai"
    base_url: str | None = None
    api_key: str | None = None
    tools: list[str | Tool] = field(default_factory=list)
    policy: AgentPolicy = field(default_factory=AgentPolicy)
    # Deployed mode settings
    mode: str = "local"  # "local" or "deployed"
    backend_url: str | None = None
    backend_api_key: str | None = None
    backend_headers: dict[str, str] | None = None
    agent_id: str | None = None
    # Thinking strip: None=default patterns, False=disable, list=custom regex
    strip_thinking: bool | list[str] | None = None
    # Sub-agents for delegation
    sub_agents: list["Agent"] = field(default_factory=list)
    # Custom loop configuration
    loop: Any = None  # BaseLoop subclass
    # Skill-related fields (Stage 3)
    skills: list[str] = field(default_factory=list)
    skill_dirs: list[Path] = field(default_factory=list)
    auto_load_dependencies: bool = True
    # Metadata for additional configuration (e.g., skills for later resolution)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_config(self) -> dict[str, Any]:
        """Serialize agent config to dict."""
        loop_config = None
        if self.loop is not None:
            from tinycua_sdk.agent.loop_resolver import analyze_loop_source

            loop_class = self.loop.__class__
            class_name = loop_class.__name__

            module = inspect.getmodule(loop_class)
            if module and module.__file__:
                with open(module.__file__, "r") as f:
                    module_source = f.read()
            else:
                module_source = ""

            class_source = inspect.getsource(loop_class)
            dependencies, helpers = analyze_loop_source(class_source)

            if not helpers and module_source:
                dependencies, helpers = analyze_loop_source(module_source)

            loop_config = {
                "class_name": class_name,
                "source": class_source,
                "dependencies": dependencies,
                "helpers": helpers,
            }

        return {
            "name": self.name,
            "instructions": self.instructions,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "tools": [t.to_config() if isinstance(t, Tool) else t for t in self.tools],
            "policy": {
                "max_tool_calls": self.policy.max_tool_calls,
                "parallel_tool_calls": self.policy.parallel_tool_calls,
                "temperature": self.policy.temperature,
            },
            "strip_thinking": self.strip_thinking,
            "loop": loop_config,
            # Skill-related fields (Stage 3)
            "skills": self.skills,
            "skill_dirs": [str(d) for d in self.skill_dirs],
            "auto_load_dependencies": self.auto_load_dependencies,
            # Include metadata for backward compatibility
            "metadata": self.metadata,
        }

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "AgentConfig":
        """Deserialize agent config from dict."""
        policy_data = data.get("policy", {})
        policy = AgentPolicy(
            max_tool_calls=policy_data.get("max_tool_calls", 10),
            parallel_tool_calls=policy_data.get("parallel_tool_calls", True),
            temperature=policy_data.get("temperature", 1.0),
        )
        loop_config = data.get("loop")

        # Convert tools data back to Tool instances or keep as strings
        tools_data = data.get("tools", [])
        tools = []
        for t in tools_data:
            if isinstance(t, Tool):
                # Already a Tool instance
                tools.append(t)
            elif isinstance(t, dict):
                # Reconstruct from config
                tools.append(Tool.from_config(t))
            elif isinstance(t, str):
                # Keep as string for lazy resolution
                tools.append(t)
            else:
                # Unknown type - keep as is
                tools.append(t)

        # Parse skills - check top-level first, then metadata (Stage 1 compat)
        metadata = data.get("metadata", {})
        skills = data.get("skills", [])
        if not skills and "skills" in metadata:
            skills = metadata["skills"]

        # Parse skill_dirs
        skill_dirs = [
            Path(d) if isinstance(d, str) else d for d in data.get("skill_dirs", [])
        ]

        # Parse auto_load_dependencies
        auto_load_dependencies = data.get("auto_load_dependencies", True)

        return cls(
            name=data.get("name", "assistant"),
            instructions=data.get("instructions", ""),
            system_prompt=data.get("system_prompt", "You are a helpful assistant."),
            model=data.get(
                "model", "gpt-5-nano"
            ),  # Fixed: use gpt-5-nano to match dataclass default
            provider=data.get("provider", "openai"),
            base_url=data.get("base_url"),
            api_key=data.get("api_key"),
            tools=tools,
            policy=policy,
            strip_thinking=data.get("strip_thinking"),
            loop=loop_config,  # Store raw config for later materialization
            # Skill-related fields (Stage 3)
            skills=skills,
            skill_dirs=skill_dirs,
            auto_load_dependencies=auto_load_dependencies,
            # Metadata (for backward compatibility)
            metadata=metadata,
        )

    @classmethod
    def from_json(cls, json_data: str | Path | dict[str, Any]) -> "AgentConfig":
        """Deserialize agent config from JSON.

        Args:
            json_data: JSON string, file path (Path/str), or dict

        Returns:
            AgentConfig instance

        Raises:
            ValueError: If JSON is invalid or cannot be parsed
            FileNotFoundError: If file path doesn't exist
        """
        # Determine input type and parse accordingly
        if isinstance(json_data, Path):
            # Path object - always treat as file path
            json_data = json_data.expanduser()
            if not json_data.exists():
                raise FileNotFoundError(f"File not found: {json_data}")
            content = json_data.read_text()
            if not content.strip():
                raise ValueError("Empty JSON input")
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON: {e}") from e

        elif isinstance(json_data, str):
            if not json_data.strip():
                raise ValueError("Empty JSON input")
            # First, try to parse as JSON
            try:
                data = json.loads(json_data)
            except json.JSONDecodeError:
                # If fails and looks like a file path ending in .json, try loading as file
                if json_data.endswith(".json") and (
                    "/" in json_data or "\\" in json_data
                ):
                    file_path = Path(json_data).expanduser()
                    if file_path.exists():
                        content = file_path.read_text()
                        if not content.strip():
                            raise ValueError("Empty JSON input")
                        try:
                            data = json.loads(content)
                        except json.JSONDecodeError as e:
                            raise ValueError(f"Invalid JSON: {e}") from e
                    else:
                        raise FileNotFoundError(f"File not found: {file_path}")
                else:
                    raise ValueError(f"Invalid JSON: '{json_data[:50]}...'") from None

        elif isinstance(json_data, dict):
            # Dict input - use directly
            data = json_data

        else:
            raise ValueError(f"Unsupported input type: {type(json_data)}")

        # Apply environment variable substitution
        data = _substitute_env_vars(data)

        # Use from_config for field extraction
        return cls.from_config(data)

    def to_json(self, indent: int = 2, redact_sensitive: bool = False) -> str:
        """Serialize agent config to JSON string.

        Args:
            indent: JSON indentation level (default: 2)
            redact_sensitive: If True, mask api_key values (default: False)

        Returns:
            JSON string representation
        """
        config = self.to_config()

        if redact_sensitive:
            if config.get("api_key"):
                config["api_key"] = "***REDACTED***"

        return json.dumps(config, indent=indent)

    def to_yaml(self, redact_sensitive: bool = False) -> str:
        """Serialize agent config to YAML string.

        Args:
            redact_sensitive: If True, mask api_key values (default: False)

        Returns:
            YAML string representation
        """
        config = self.to_config()

        if redact_sensitive:
            if config.get("api_key"):
                config["api_key"] = "***REDACTED***"

        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_json_file(cls, path: Path | str) -> "AgentConfig":
        """Load agent config from JSON file.

        Args:
            path: Path to JSON file

        Returns:
            AgentConfig instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If JSON is invalid
        """
        file_path = Path(path).expanduser()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text()
        if not content.strip():
            raise ValueError("Empty JSON input")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        # Apply environment variable substitution
        data = _substitute_env_vars(data)

        return cls.from_config(data)

    @classmethod
    def from_yaml_file(cls, path: Path | str) -> "AgentConfig":
        """Load agent config from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            AgentConfig instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid (includes line number if available)
        """
        file_path = Path(path).expanduser()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text()
        if not content.strip():
            raise ValueError("Empty YAML input")

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            error_msg = str(e)
            # Try to include line number if available
            if hasattr(e, "problem_mark") and e.problem_mark:
                line_num = e.problem_mark.line + 1
                raise ValueError(f"Invalid YAML at line {line_num}: {error_msg}") from e
            raise ValueError(f"Invalid YAML: {error_msg}") from e

        # Apply environment variable substitution
        data = _substitute_env_vars(data)

        return cls.from_config(data)

    def to_json_file(self, path: Path | str, indent: int = 2) -> None:
        """Write agent config to JSON file.

        Args:
            path: Path to write JSON file
            indent: JSON indentation level
        """
        file_path = Path(path).expanduser()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.to_json(indent=indent))

    def to_yaml_file(self, path: Path | str) -> None:
        """Write agent config to YAML file.

        Args:
            path: Path to write YAML file
        """
        file_path = Path(path).expanduser()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.to_yaml())


__all__ = ["AgentConfig", "AgentPolicy"]
