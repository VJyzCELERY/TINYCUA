"""TinyCUAAgent — WildClawBench adapter wrapping tinycua run CLI."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from tinycua.wildclawbench.base_agent import AgentExecution, AgentTaskSpec, BaseAgent

logger = logging.getLogger(__name__)


class TinyCUAAgent(BaseAgent):
    """WildClawBench adapter that spawns tinycua run as a subprocess.

    Provides process-level isolation by delegating to the tinycua CLI rather
    than importing tinycua in-process.

    Args:
        base_url: Optional override for the LLM API base URL.
        api_key: Optional override for the LLM API key.
        model: Optional override for the model name.
        tinycua_bin: Path to the tinycua CLI binary.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        tinycua_bin: str = "tinycua",
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._tinycua_bin = tinycua_bin

    @property
    def expects_gateway(self) -> bool:
        """Return False — no long-running process needed."""
        return False

    @property
    def transcript_container_path(self) -> str:
        """Return path to the transcript JSONL file."""
        return "/tmp_workspace/results/transcript.jsonl"

    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """Execute a benchmark task by spawning tinycua run.

        Builds the CLI command, creates output/workspace directories, spawns
        the subprocess, and returns an AgentExecution with timing info.

        Args:
            spec: The task specification.

        Returns:
            Execution result with elapsed_time and optional error.
        """
        output_dir = Path(spec.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        workspace_path = Path(spec.workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)

        cmd = self._build_command(spec)
        env = self._build_env(spec)

        logger.info("Spawning tinycua subprocess: %s", " ".join(cmd))

        start_time = time.monotonic()
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=str(workspace_path),
                text=True,
            )
            stdout, stderr = proc.communicate(timeout=spec.timeout_seconds)
            elapsed = time.monotonic() - start_time

            if proc.returncode == 124:
                error_msg = f"tinycua run timed out after {spec.timeout_seconds}s"
                logger.warning(error_msg)
                return AgentExecution(elapsed_time=elapsed, error=error_msg)
            elif proc.returncode != 0:
                error_msg = f"tinycua exited with code {proc.returncode}"
                if stderr:
                    error_msg += f": {stderr}"
                logger.error(error_msg)
                return AgentExecution(elapsed_time=elapsed, error=error_msg)

            return AgentExecution(elapsed_time=elapsed)

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start_time
            proc.kill()
            proc.wait()
            error_msg = f"tinycua run timed out after {spec.timeout_seconds}s"
            logger.warning(error_msg)
            return AgentExecution(elapsed_time=elapsed, error=error_msg)

        except FileNotFoundError:
            elapsed = time.monotonic() - start_time
            error_msg = f"tinycua binary not found: {self._tinycua_bin}"
            logger.error(error_msg)
            return AgentExecution(elapsed_time=elapsed, error=error_msg)

    def collect_usage(
        self, task_id: str, output_dir: Path, elapsed_time: float
    ) -> dict[str, Any]:
        """Collect usage statistics from the transcript.

        Parses transcript.jsonl from the output directory to count LLM
        requests and sum token usage.

        Args:
            task_id: The task identifier.
            output_dir: Directory containing task output artifacts.
            elapsed_time: Time taken for execution.

        Returns:
            Dict with keys: requests, total_tokens, cost.
        """
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

                    # Count LLM-related events
                    if "llm" in event_type or "response" in event_type:
                        requests += 1

                    # Sum tokens from usage field
                    usage = event.get("usage", {})
                    tokens = usage.get("total_tokens")
                    if isinstance(tokens, (int, float)):
                        total_tokens += int(tokens)

        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to parse transcript %s: %s", transcript_path, exc)
            return {"requests": 0, "total_tokens": None, "cost": 0.0}

        return {
            "requests": requests,
            "total_tokens": total_tokens if total_tokens > 0 else None,
            "cost": 0.0,
        }

    def _build_command(self, spec: AgentTaskSpec) -> list[str]:
        """Build the tinycua run CLI command.

        Args:
            spec: The task specification.

        Returns:
            List of command arguments.
        """
        cmd = [
            self._tinycua_bin,
            "run",
            spec.prompt,
            "--timeout",
            str(spec.timeout_seconds),
            "--output-dir",
            str(spec.output_dir),
            "--workspace",
            str(spec.workspace_path),
            "--model",
            spec.model,
        ]

        if self._base_url:
            cmd.extend(["--base-url", self._base_url])

        if self._api_key:
            cmd.extend(["--api-key", self._api_key])

        return cmd

    def _build_env(self, spec: AgentTaskSpec) -> dict[str, str]:
        """Build environment variables for the subprocess.

        Inherits the current environment and adds/overrides tinycua-specific
        variables when configured.

        Args:
            spec: The task specification.

        Returns:
            Dict of environment variables.
        """
        env = os.environ.copy()

        if self._base_url:
            env["TINYCUA_BASE_URL"] = self._base_url

        if self._api_key:
            env["TINYCUA_API_KEY"] = self._api_key

        if spec.model:
            env["TINYCUA_MODEL"] = spec.model

        return env
