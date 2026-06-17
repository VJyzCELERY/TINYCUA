"""HermesAgentAdapter — WildClawBench adapter for running Hermes agent via Docker."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from agents_benchmark.base_agent import AgentExecution, AgentTaskSpec, BaseAgent

logger = logging.getLogger(__name__)

_HERMES_IMAGE_NAME = "hermes-agent"


class HermesAgentAdapter(BaseAgent):
    """WildClawBench adapter that runs Hermes agent via Docker.

    Provides Docker-isolated execution of the Hermes agent, building the
    Docker image if needed, spawning the container, and collecting usage
    data from the transcript.
    """

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize the adapter.

        Args:
            config_path: Optional path to the Hermes agent YAML config file.
        """
        self._config = None
        if config_path:
            from agents_benchmark.agents.hermes_config import load_hermes_config

            self._config = load_hermes_config(config_path)

    @property
    def name(self) -> str:
        """Return the agent identifier."""
        return "hermes"

    @property
    def expects_gateway(self) -> bool:
        """Return False — no long-running process needed."""
        return False

    @property
    def transcript_container_path(self) -> str:
        """Return path to the transcript JSONL file inside the container."""
        return "/workspace/transcript.jsonl"

    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """Execute a benchmark task by running Hermes agent in Docker.

        Args:
            spec: The task specification.

        Returns:
            Execution result with elapsed_time and optional error.
        """
        api_key = os.environ.get(
            self._config.api_key_env if self._config else "HERMES_API_KEY"
        )
        if not api_key:
            error_msg = "Required API key env var is not set"
            logger.error(error_msg)
            return AgentExecution(elapsed_time=0.0, error=error_msg)

        output_dir = Path(spec.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        workspace_path = Path(spec.workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)

        try:
            self._ensure_image()
        except subprocess.CalledProcessError as exc:
            error_msg = f"Docker image build failed: {exc}"
            logger.error(error_msg)
            return AgentExecution(elapsed_time=0.0, error=error_msg)

        cmd = self._build_docker_command(spec)
        env = os.environ.copy()

        start_time = time.monotonic()
        try:
            proc = subprocess.Popen(  # noqa: S603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
            )
            _stdout, stderr = proc.communicate(timeout=spec.timeout_seconds)
            elapsed = time.monotonic() - start_time

            if proc.returncode != 0:
                error_msg = f"Hermes container exited with code {proc.returncode}"
                if stderr:
                    error_msg += f": {stderr}"
                logger.error(error_msg)
                return AgentExecution(elapsed_time=elapsed, error=error_msg)

            return AgentExecution(elapsed_time=elapsed)

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start_time
            proc.kill()
            proc.wait()
            error_msg = f"Hermes container timed out after {spec.timeout_seconds}s"
            logger.warning(error_msg)
            return AgentExecution(elapsed_time=elapsed, error=error_msg)

        except FileNotFoundError:
            elapsed = time.monotonic() - start_time
            error_msg = "Docker binary not found — is Docker installed?"
            logger.error(error_msg)
            return AgentExecution(elapsed_time=elapsed, error=error_msg)

    def collect_usage(
        self, _task_id: str, output_dir: Path, _elapsed_time: float
    ) -> dict[str, Any]:
        """Collect usage statistics from the Hermes transcript.

        Args:
            task_id: The task identifier.
            output_dir: Directory containing task output artifacts.
            elapsed_time: Time taken for execution.

        Returns:
            Dict with keys: requests, total_tokens, cost.
        """
        transcript_path = Path(output_dir) / "transcript.jsonl"

        if not transcript_path.exists():
            return {"requests": 0, "total_tokens": None, "cost": 0.0}

        requests = 0
        total_tokens = 0

        try:
            with transcript_path.open() as f:
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
        """Estimate API cost from token usage.

        Args:
            total_tokens: Total token count or None.

        Returns:
            Estimated cost in USD.
        """
        if total_tokens is None or total_tokens <= 0:
            return 0.0
        rate = 0.0000025
        return round(total_tokens * rate, 6)

    def _build_docker_command(self, spec: AgentTaskSpec) -> list[str]:
        """Build the docker run command for the Hermes agent.

        Args:
            spec: The task specification.

        Returns:
            List of command arguments.
        """
        api_key_env = self._config.api_key_env if self._config else "HERMES_API_KEY"
        api_base = self._config.api_base if self._config else ""
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{spec.output_dir}:/workspace/output",
            "-v",
            f"{spec.workspace_path}:/workspace/workspace",
            "-e",
            f"{api_key_env}={os.environ.get(api_key_env, '')}",
            "-e",
            f"HERMES_MODEL={spec.model}",
            "-e",
            f"HERMES_API_BASE={api_base}",
            "--network",
            "host",
            _HERMES_IMAGE_NAME,
            "--model",
            spec.model,
            "--prompt",
            spec.prompt,
            "--timeout",
            str(spec.timeout_seconds),
        ]
        return cmd

    def _ensure_image(self) -> None:
        """Ensure the Hermes Docker image exists locally.

        Raises:
            subprocess.CalledProcessError: If the Docker build fails.
        """
        result = subprocess.run(  # noqa: S603
            ["docker", "images", "-q", _HERMES_IMAGE_NAME],
            capture_output=True,
            text=True,
            check=False,
        )
        if not result.stdout.strip():
            logger.info("Hermes Docker image not found — building...")
            for dockerfile_path in [
                "docker/Dockerfile.hermes",
                "Dockerfile.hermes",
                "../docker/Dockerfile.hermes",
            ]:
                if Path(dockerfile_path).exists():
                    logger.info(
                        "Building Hermes Docker image (this may take several minutes)..."
                    )
                    subprocess.run(  # noqa: S603
                        [
                            "docker",
                            "build",
                            "-f",
                            dockerfile_path,
                            "-t",
                            _HERMES_IMAGE_NAME,
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
