"""Agent configuration classes."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.tools.decorators import Tool




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


class AgentPolicy(BaseModel):
    """Policy for agent behavior."""

    model_config = ConfigDict(frozen=True)

    max_tool_calls: int = 10
    parallel_tool_calls: bool = True


class AgentConfig(BaseModel):
    """Configuration for an agent."""

    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)

    name: str = "assistant"
    instructions: str = ""
    llm_model: LanguageModel = Field(default_factory=LanguageModel)
    tools: list[Tool] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)  # type: ignore[type-arg]
    policy: AgentPolicy = Field(default_factory=AgentPolicy)
    metadata: dict[str, Any] = Field(default_factory=dict)
    loop: Any = None  # BaseLoop | None — kept as Any since BaseLoop is not a Pydantic model

    def to_config(self) -> dict[str, Any]:
        """Serialize agent config to dict."""
        config: dict[str, Any] = {
            "name": self.name,
            "instructions": self.instructions,
            "llm_model": self.llm_model.to_dict(),
            "tools": [t.to_config() if isinstance(t, Tool) else t for t in self.tools],
            "skills": [
                s.to_dict() if hasattr(s, "to_dict") else s for s in self.skills
            ],
            "policy": {
                "max_tool_calls": self.policy.max_tool_calls,
                "parallel_tool_calls": self.policy.parallel_tool_calls,
            },
        }
        if self.loop is not None:
            if hasattr(self.loop, "to_dict"):
                config["loop"] = self.loop.to_dict()
            elif hasattr(self.loop, "max_iterations"):
                config["loop"] = {"max_iterations": self.loop.max_iterations}
            else:
                config["loop"] = None
        else:
            config["loop"] = None
        return config

    def to_dict(self) -> dict[str, Any]:
        """Serialize agent config to plain dict (alias for to_config)."""
        return self.to_config()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        """Deserialize agent config from plain dict (alias for from_config)."""
        return cls.from_config(data)

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "AgentConfig":
        """Deserialize agent config from dict."""
        policy_data = data.get("policy", {})
        policy = AgentPolicy(
            max_tool_calls=policy_data.get("max_tool_calls", 10),
            parallel_tool_calls=policy_data.get("parallel_tool_calls", True),
        )

        llm_data = data.get("llm_model", {})
        llm_model = LanguageModel.from_dict(llm_data) if isinstance(llm_data, dict) else LanguageModel()

        tools_data = data.get("tools", [])
        tools = []
        for t in tools_data:
            if isinstance(t, Tool):
                tools.append(t)
            elif isinstance(t, dict):
                tools.append(Tool.from_dict(t))
            else:
                tools.append(t)

        skills_data = data.get("skills", [])
        skills = []
        for s in skills_data:
            if hasattr(s, "to_dict"):
                skills.append(s)
            elif isinstance(s, dict):
                from tinycua_sdk.skills.models import Skill
                skills.append(Skill.from_dict(s))
            else:
                skills.append(s)

        return cls(
            name=data.get("name", "assistant"),
            instructions=data.get("instructions", ""),
            llm_model=llm_model,
            tools=tools,
            skills=skills,
            policy=policy,
            loop=data.get("loop"),
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
        if isinstance(json_data, Path):
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
            try:
                data = json.loads(json_data)
            except json.JSONDecodeError:
                if json_data.endswith(".json") and ("/" in json_data or "\\" in json_data):
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
            data = json_data

        else:
            raise ValueError(f"Unsupported input type: {type(json_data)}")

        data = _substitute_env_vars(data)
        return cls.from_config(data)

    def to_json(self, indent: int = 2, redact_sensitive: bool = False) -> str:
        """Serialize agent config to JSON string."""
        config = self.to_config()
        if redact_sensitive:
            if config.get("llm_model", {}).get("api_key"):
                config["llm_model"]["api_key"] = "***REDACTED***"
        return json.dumps(config, indent=indent, default=str)

    def to_yaml(self, redact_sensitive: bool = False) -> str:
        """Serialize agent config to YAML string."""
        config = self.to_config()
        if redact_sensitive:
            if config.get("llm_model", {}).get("api_key"):
                config["llm_model"]["api_key"] = "***REDACTED***"
        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_json_file(cls, path: Path | str) -> "AgentConfig":
        """Load agent config from JSON file."""
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
        data = _substitute_env_vars(data)
        return cls.from_config(data)

    @classmethod
    def from_yaml_file(cls, path: Path | str) -> "AgentConfig":
        """Load agent config from YAML file."""
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
            if hasattr(e, "problem_mark") and e.problem_mark:
                line_num = e.problem_mark.line + 1
                raise ValueError(f"Invalid YAML at line {line_num}: {error_msg}") from e
            raise ValueError(f"Invalid YAML: {error_msg}") from e
        data = _substitute_env_vars(data)
        return cls.from_config(data)

    def to_json_file(self, path: Path | str, indent: int = 2) -> None:
        """Write agent config to JSON file."""
        file_path = Path(path).expanduser()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.to_json(indent=indent))

    def to_yaml_file(self, path: Path | str) -> None:
        """Write agent config to YAML file."""
        file_path = Path(path).expanduser()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.to_yaml())


__all__ = ["AgentConfig", "AgentPolicy"]
