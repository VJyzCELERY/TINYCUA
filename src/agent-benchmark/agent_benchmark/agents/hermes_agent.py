"""HermesAgent — WildClawBench adapter for Hermes agent via Docker.

Extends DockerAgent with YAML config, auto-build from source, and
custom volume mounts matching upstream WildClawBench conventions.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from agent_benchmark.agents.docker_agent import DockerAgent
from agent_benchmark.base_agent import AgentTaskSpec

logger = logging.getLogger(__name__)


@dataclass
class HermesConfig:
    """Configuration for Hermes agent runs.

    Attributes:
        model: Model name/path (e.g., "gpt-4", "qwen3.5-9b").
        api_base: API endpoint URL.
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


def load_hermes_config(path: str) -> HermesConfig:
    """Load and validate Hermes configuration from a YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Hermes config not found: {path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Hermes config must be a YAML mapping")

    missing = _REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(
            f"Hermes config missing required fields: {', '.join(sorted(missing))}"
        )

    return HermesConfig(
        model=str(data["model"]),
        api_base=str(data["api_base"]),
        api_key_env=str(data["api_key_env"]),
        temperature=float(data.get("temperature", 0.0)),
        max_tokens=int(data.get("max_tokens", 4096)),
        timeout=int(data.get("timeout", 120)),
        cost_per_token=float(data.get("cost_per_token", 0.0000025)),
    )


class HermesAgent(DockerAgent):
    """Hermes agent harness. Extends DockerAgent with YAML config + auto-build.

    Args:
        config_path: Path to the Hermes agent YAML config file.
    """

    image_name = "wildclawbench-hermes-agent:v0.5"
    transcript_path = "/workspace/transcript.jsonl"

    def __init__(self, config_path: str) -> None:
        self._config = load_hermes_config(config_path)
        self.api_key_env = self._config.api_key_env
        self.default_cost_per_token = self._config.cost_per_token

    def _build_docker_command(self, spec: AgentTaskSpec) -> list[str]:
        """Build docker run command with Hermes-specific volume mounts."""
        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{spec.output_dir}:/workspace/output",
            "-v",
            f"{spec.workspace_path}:/workspace/workspace",
            "-e",
            f"{self.api_key_env}={os.environ.get(self.api_key_env, '')}",
            "-e",
            f"HERMES_MODEL={spec.model}",
            "-e",
            f"HERMES_API_BASE={self._config.api_base}",
            "-e",
            f"HERMES_TEMPERATURE={self._config.temperature}",
            "-e",
            f"HERMES_MAX_TOKENS={self._config.max_tokens}",
            "--network",
            "host",
            "--add-host=host.docker.internal:host-gateway",
            self.image_name,
            "--model",
            spec.model,
            "--prompt",
            spec.prompt,
            "--timeout",
            str(spec.timeout_seconds),
        ]

    def _ensure_image(self) -> None:
        """Ensure the Hermes Docker image exists. Builds from source if missing."""
        result = subprocess.run(
            ["docker", "images", "-q", self.image_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if not result.stdout.strip():
            logger.info("Hermes Docker image not found — building from source...")
            for dockerfile_path in [
                "docker/Dockerfile.hermes",
                "Dockerfile.hermes",
                "../docker/Dockerfile.hermes",
            ]:
                if Path(dockerfile_path).exists():
                    subprocess.run(
                        [
                            "docker",
                            "build",
                            "-f",
                            dockerfile_path,
                            "-t",
                            self.image_name,
                            ".",
                        ],
                        check=True,
                    )
                    return
            raise subprocess.CalledProcessError(
                1,
                ["docker", "build"],
                stderr="Dockerfile.hermes not found in any expected location",
            )
