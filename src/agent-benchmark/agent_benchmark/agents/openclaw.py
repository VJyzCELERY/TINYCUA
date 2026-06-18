"""OpenClawAgent — WildClawBench adapter for OpenClaw harness."""

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
class OpenClawConfig:
    """Configuration for OpenClaw agent runs."""

    model: str
    api_base: str
    api_key_env: str
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 120
    cost_per_token: float = 0.0000025


_REQUIRED_FIELDS = {"model", "api_base", "api_key_env"}


def load_openclaw_config(path: str) -> OpenClawConfig:
    """Load and validate OpenClaw configuration from a YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"OpenClaw config not found: {path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("OpenClaw config must be a YAML mapping")

    missing = _REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(
            f"OpenClaw config missing required fields: {', '.join(sorted(missing))}"
        )

    return OpenClawConfig(
        model=str(data["model"]),
        api_base=str(data["api_base"]),
        api_key_env=str(data["api_key_env"]),
        temperature=float(data.get("temperature", 0.0)),
        max_tokens=int(data.get("max_tokens", 4096)),
        timeout=int(data.get("timeout", 120)),
        cost_per_token=float(data.get("cost_per_token", 0.0000025)),
    )


class OpenClawAgent(DockerAgent):
    """OpenClaw harness agent for Qwen 3.5 9B.

    Uses an OpenAI-compatible API endpoint to run the Qwen 3.5 9B model
    within the WildClawBench Docker environment.

    Args:
        config_path: Path to the OpenClaw agent YAML config file.
    """

    image_name = "wildclawbench-ubuntu:v1.3"
    transcript_path = "/tmp_workspace/results/transcript.jsonl"

    def __init__(self, config_path: str | None = None) -> None:
        if config_path:
            self._config = load_openclaw_config(config_path)
            self.api_key_env = self._config.api_key_env
            self.default_cost_per_token = self._config.cost_per_token
        else:
            # Fallback to env vars
            self.api_key_env = "LM_STUDIO_API_KEY"
            self.default_cost_per_token = 0.0000025
            self._config = OpenClawConfig(
                model=os.environ.get("DEFAULT_MODEL", "qwen3.5-9b"),
                api_base=os.environ.get("LM_STUDIO_API_BASE", "http://localhost:1234/v1"),
                api_key_env="LM_STUDIO_API_KEY",
            )

    def _build_docker_command(self, spec: AgentTaskSpec) -> list[str]:
        """Build docker run command with OpenClaw-specific volume mounts."""
        project_dir = Path(__file__).parent.parent.parent
        entrypoint_script = project_dir / "scripts" / "entrypoint_lmstudio.sh"

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
