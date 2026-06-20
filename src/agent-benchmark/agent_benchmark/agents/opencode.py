"""OpenCodeAgent — WildClawBench adapter for OpenCode harness.

Extends DockerAgent with OpenCode-specific configuration. The agent CLI
(opencode-ai) is installed from npm inside the Docker image. Entrypoint
is baked into the image at /app/entrypoint.sh.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from agent_benchmark.agents.docker_agent import DockerAgent
from agent_benchmark.base_agent import AgentTaskSpec
from agent_benchmark.providers.base import Provider

logger = logging.getLogger(__name__)


class OpenCodeAgent(DockerAgent):
    """OpenCode harness agent.

    Installs opencode-ai from npm inside the container. Runs in one-shot
    mode: receives TASK_PROMPT via env var, executes, saves transcript, exits.

    Args:
        provider: LLM provider instance for model access.
    """

    image_name = "wildclawbench-opencode:latest"
    transcript_path = "/tmp_workspace/results/transcript.jsonl"

    def __init__(self, provider: Provider | None = None, **kwargs: Any) -> None:
        super().__init__(provider=provider, **kwargs)

    def _build_docker_command(self, spec: AgentTaskSpec) -> list[str]:
        """Build docker run command. Entrypoint is baked into the image."""
        # Get provider environment variables
        if self._provider:
            provider_env = self._provider.get_entrypoint_env()
            api_base = self._provider.config.api_base.replace(
                "localhost", "host.docker.internal"
            )
            provider_env["LLM_API_BASE"] = api_base
        else:
            api_base = os.environ.get(
                "LM_STUDIO_API_BASE", "http://host.docker.internal:1234/v1"
            )
            provider_env = {
                "LLM_API_BASE": api_base,
                "LLM_API_KEY": os.environ.get(self.api_key_env, "lm-studio"),
                "LLM_MODEL": spec.model,
                "LLM_TEMPERATURE": "0.0",
                "LLM_MAX_TOKENS": "4096",
            }

        # Detect host architecture for Docker platform
        host_arch = platform.machine()
        docker_platform = "linux/arm64" if host_arch == "arm64" else "linux/amd64"

        cmd = [
            "docker",
            "run",
            "--rm",
            "--platform",
            docker_platform,
            "-v",
            f"{spec.output_dir}:/tmp_workspace/results",
            "-v",
            f"{spec.workspace_path}:/tmp_workspace/workspace",
        ]

        # Add provider environment variables
        for key, value in provider_env.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Add OpenCode-specific environment variables
        cmd.extend([
            "-e", f"OPENCODE_MODEL={spec.model}",
            "-e", f"TASK_PROMPT={spec.prompt}",
            "-e", f"DEFAULT_MODEL={spec.model}",
            "--add-host=host.docker.internal:host-gateway",
            self.image_name,
        ])

        return cmd

    def _ensure_image(self) -> None:
        """Ensure the OpenCode Docker image exists. Builds from source if missing."""
        result = subprocess.run(
            ["docker", "images", "-q", self.image_name],
            capture_output=True, text=True, check=False,
        )
        if not result.stdout.strip():
            logger.info("OpenCode Docker image not found — building from source...")
            for dockerfile_path in [
                "docker/Dockerfile.opencode",
                "Dockerfile.opencode",
                "../docker/Dockerfile.opencode",
            ]:
                if Path(dockerfile_path).exists():
                    subprocess.run(
                        ["docker", "build", "-f", dockerfile_path,
                         "-t", self.image_name, "."],
                        check=True,
                    )
                    return
            raise subprocess.CalledProcessError(
                1, ["docker", "build"],
                stderr="Dockerfile.opencode not found in any expected location",
            )
