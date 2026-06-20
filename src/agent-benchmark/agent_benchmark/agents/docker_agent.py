"""DockerAgent — shared base class for all Docker-based WildClawBench agents.

Encapsulates: image check, docker run with volumes/env/network, timeout
handling, exit code mapping, transcript parsing, and cost estimation.

OpenClaw, OpenCode, and Hermes all subclass this.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_benchmark.base_agent import AgentExecution, AgentTaskSpec, BaseAgent

if TYPE_CHECKING:
    from agent_benchmark.providers.base import Provider

logger = logging.getLogger(__name__)


class DockerAgent(BaseAgent):
    """Base class for Docker-based WildClawBench agents.

    Subclasses set class-level attributes and optionally override methods.

    Class attributes:
        image_name: Docker image tag (e.g., "wildclawbench-ubuntu:v1.3").
        api_key_env: Env var name for the required API key.
        default_cost_per_token: Default cost per token for estimation.
        transcript_path: Path to transcript JSONL inside the container.
    """

    image_name: str = ""
    api_key_env: str = ""
    default_cost_per_token: float = 0.0000025
    transcript_path: str = "/tmp_workspace/results/transcript.jsonl"

    def __init__(self, provider: Provider | None = None, **kwargs: Any) -> None:
        """Initialize DockerAgent with optional provider config.

        Args:
            provider: LLM provider instance. If None, uses legacy config.
            **kwargs: Additional arguments for BaseAgent.
        """
        self._provider = provider
        if provider:
            self.api_key_env = provider.config.api_key_env
            self.default_cost_per_token = provider.config.cost_per_token
        super().__init__(**kwargs)

    @property
    def expects_gateway(self) -> bool:
        """Docker agents do not need a long-running gateway."""
        return False

    @property
    def transcript_container_path(self) -> str:
        """Path to transcript JSONL inside the container."""
        return self.transcript_path

    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """Execute a benchmark task by running the agent in Docker."""
        api_key = os.environ.get(self.api_key_env, "")
        # Allow empty API keys for local LLMs (LM Studio, Ollama, custom local, etc.)
        if not api_key and self.api_key_env not in ("LM_STUDIO_API_KEY", "LOCAL_CUSTOM_API_KEY", "CUSTOM_API_KEY"):
            error_msg = f"Required API key env var {self.api_key_env} is not set"
            logger.error(error_msg)
            return AgentExecution(elapsed_time=0.0, error=error_msg)

        output_dir = Path(spec.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        workspace_path = Path(spec.workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)

        self._ensure_image()

        cmd = self._build_docker_command(spec)
        env = os.environ.copy()
        safe_cmd = [
            a if not a.startswith(f"{self.api_key_env}=") else f"{self.api_key_env}=***"
            for a in cmd
        ]
        logger.info("Spawning %s container: %s", self.image_name, " ".join(safe_cmd))

        start_time = time.monotonic()
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True
            )
            # timeout=None means unlimited
            stdout, stderr = proc.communicate(timeout=spec.timeout_seconds if spec.timeout_seconds else None)
            elapsed = time.monotonic() - start_time

            if proc.returncode != 0:
                error_msg = f"Container exited with code {proc.returncode}"
                if stderr:
                    error_msg += f": {stderr}"
                logger.error(error_msg)
                return AgentExecution(elapsed_time=elapsed, error=error_msg)

            return AgentExecution(elapsed_time=elapsed)

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start_time
            proc.kill()
            proc.wait()
            error_msg = f"Container timed out after {spec.timeout_seconds}s"
            logger.warning(error_msg)
            return AgentExecution(elapsed_time=elapsed, error=error_msg)

        except FileNotFoundError:
            elapsed = time.monotonic() - start_time
            error_msg = "Docker binary not found — is Docker installed?"
            logger.error(error_msg)
            return AgentExecution(elapsed_time=elapsed, error=error_msg)

    def collect_usage(
        self, task_id: str, output_dir: Path, elapsed_time: float
    ) -> dict[str, Any]:
        """Collect usage statistics from the transcript JSONL."""
        transcript_path = output_dir / "transcript.jsonl"

        if not transcript_path.exists():
            logger.debug("No transcript found at %s", transcript_path)
            return {"requests": 0, "total_tokens": None, "cost": 0.0}

        requests = 0
        total_tokens = 0

        try:
            with open(transcript_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    event = json.loads(line)
                    event_type = event.get("type", "")

                    if "llm" in event_type or "response" in event_type:
                        requests += 1

                    usage = event.get("usage", {})
                    tokens = usage.get("total_tokens")
                    if isinstance(tokens, (int, float)):
                        total_tokens += int(tokens)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to parse transcript %s: %s", transcript_path, exc)
            return {"requests": 0, "total_tokens": None, "cost": 0.0}

        total = total_tokens if total_tokens > 0 else None
        return {
            "requests": requests,
            "total_tokens": total,
            "cost": self._estimate_cost(total),
        }

    def _estimate_cost(self, total_tokens: int | None) -> float:
        if total_tokens is None or total_tokens <= 0:
            return 0.0
        return round(total_tokens * self.default_cost_per_token, 6)

    def _build_docker_command(self, spec: AgentTaskSpec) -> list[str]:
        """Build docker run command. Subclasses can override for custom args."""
        # Get the project directory to mount the entrypoint script
        project_dir = Path(__file__).parent.parent.parent
        entrypoint_script = project_dir / "scripts" / "entrypoint.sh"

        # Get provider environment variables
        if self._provider:
            provider_env = self._provider.get_entrypoint_env()
            # Replace localhost with host.docker.internal for Docker containers
            if "LLM_API_BASE" in provider_env:
                provider_env["LLM_API_BASE"] = provider_env["LLM_API_BASE"].replace(
                    "localhost", "host.docker.internal"
                )
        else:
            # Legacy fallback for backward compatibility
            provider_env = {
                "LLM_API_BASE": os.environ.get(
                    "LM_STUDIO_API_BASE", "http://host.docker.internal:1234/v1"
                ),
                "LLM_API_KEY": os.environ.get(self.api_key_env, "lm-studio"),
                "LLM_MODEL": spec.model,
                "LLM_TEMPERATURE": "0.0",
                "LLM_MAX_TOKENS": "4096",
            }

        # Detect host architecture for Docker platform
        host_arch = platform.machine()
        docker_platform = "linux/arm64" if host_arch == "arm64" else "linux/amd64"

        # Build base command
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
            "-v",
            f"{entrypoint_script}:/tmp_workspace/entrypoint.sh:ro",
        ]

        # Add provider environment variables
        for key, value in provider_env.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Add task-specific environment variables
        cmd.extend(
            [
                "-e",
                f"TASK_PROMPT={spec.prompt}",
                "-e",
                f"DEFAULT_MODEL={spec.model}",
                "--add-host=host.docker.internal:host-gateway",
                self.image_name,
                "bash",
                "/tmp_workspace/entrypoint.sh",
            ]
        )

        return cmd

    def _ensure_image(self) -> None:
        """Ensure the Docker image exists locally. Builds if missing."""
        result = subprocess.run(
            ["docker", "images", "-q", self.image_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if not result.stdout.strip():
            logger.info(
                "Docker image %s not found — attempting to pull...", self.image_name
            )
            subprocess.run(
                ["docker", "pull", self.image_name],
                check=True,
            )
