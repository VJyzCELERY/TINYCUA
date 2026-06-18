"""OpenCodeAgent — WildClawBench adapter for OpenCode harness with Qwen 3.5 9B.

Extends DockerAgent with OpenCode-specific configuration for running
the Qwen 3.5 9B model via an OpenAI-compatible API endpoint.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from agent_benchmark.agents.docker_agent import DockerAgent
from agent_benchmark.base_agent import AgentTaskSpec

logger = logging.getLogger(__name__)


@dataclass
class OpenCodeConfig:
    """Configuration for OpenCode agent runs.

    Attributes:
        model: Model name/path (e.g., "qwen3.5-9b").
        api_base: API endpoint URL (OpenAI-compatible).
        api_key_env: Env var name for API key (not the key itself).
        temperature: Sampling temperature (default: 0.0).
        max_tokens: Max tokens per response (default: 4096).
        timeout: Request timeout in seconds (default: 120).
        cost_per_token: Cost per token in USD (default: 0.0000025).
    """

    model: str
    api_base: str
    api_key_env: str
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 120
    cost_per_token: float = 0.0000025


_REQUIRED_FIELDS = {"model", "api_base", "api_key_env"}


def load_opencode_config(path: str) -> OpenCodeConfig:
    """Load and validate OpenCode configuration from a YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"OpenCode config not found: {path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("OpenCode config must be a YAML mapping")

    missing = _REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(
            f"OpenCode config missing required fields: {', '.join(sorted(missing))}"
        )

    return OpenCodeConfig(
        model=str(data["model"]),
        api_base=str(data["api_base"]),
        api_key_env=str(data["api_key_env"]),
        temperature=float(data.get("temperature", 0.0)),
        max_tokens=int(data.get("max_tokens", 4096)),
        timeout=int(data.get("timeout", 120)),
        cost_per_token=float(data.get("cost_per_token", 0.0000025)),
    )


class OpenCodeAgent(DockerAgent):
    """OpenCode harness agent for Qwen 3.5 9B.

    Uses an OpenAI-compatible API endpoint to run the Qwen 3.5 9B model
    within the WildClawBench Docker environment.

    Args:
        config_path: Path to the OpenCode agent YAML config file.
    """

    image_name = "wildclawbench-ubuntu:v1.3"
    transcript_path = "/workspace/transcript.jsonl"

    def __init__(self, config_path: str) -> None:
        self._config = load_opencode_config(config_path)
        self.api_key_env = self._config.api_key_env
        self.default_cost_per_token = self._config.cost_per_token

    def _build_docker_command(self, spec: AgentTaskSpec) -> list[str]:
        """Build docker run command with OpenCode-specific volume mounts."""
        # Get the project directory to mount the entrypoint script
        project_dir = Path(__file__).parent.parent.parent
        entrypoint_script = project_dir / "scripts" / "entrypoint_lmstudio.sh"

        # Determine API base - use host.docker.internal for Docker containers
        api_base = self._config.api_base.replace("localhost", "host.docker.internal")

        return [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "-v",
            f"{spec.output_dir}:/tmp_workspace/results",
            "-v",
            f"{spec.workspace_path}:/tmp_workspace/workspace",
            "-v",
            f"{entrypoint_script}:/tmp_workspace/entrypoint.sh:ro",
            "-e",
            f"{self.api_key_env}={os.environ.get(self.api_key_env, 'lm-studio')}",
            "-e",
            f"OPENCODE_MODEL={spec.model}",
            "-e",
            f"OPENCODE_API_BASE={api_base}",
            "-e",
            f"OPENCODE_TEMPERATURE={self._config.temperature}",
            "-e",
            f"OPENCODE_MAX_TOKENS={self._config.max_tokens}",
            "-e",
            f"TASK_PROMPT={spec.prompt}",
            "-e",
            f"DEFAULT_MODEL={spec.model}",
            "-e",
            f"LM_STUDIO_API_BASE={api_base}",
            "-e",
            f"LM_STUDIO_API_KEY={os.environ.get(self.api_key_env, 'lm-studio')}",
            "-e",
            "LM_STUDIO_MAX_TOKENS=4096",
            "-e",
            "LM_STUDIO_TEMPERATURE=0.0",
            "--network",
            "host",
            "--add-host=host.docker.internal:host-gateway",
            self.image_name,
            "bash",
            "/tmp_workspace/entrypoint.sh",
        ]
