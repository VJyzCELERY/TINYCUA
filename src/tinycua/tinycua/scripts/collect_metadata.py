"""Hardware and runtime metadata collection for benchmark runs.

Provides collect_run_metadata() to gather CPU, GPU, RAM, Python version,
and runtime version. Also provides preflight_check() to validate output
directory writability before execution.
"""

from __future__ import annotations

import os
import platform
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from tinycua.scripts.benchmark_config import BenchmarkConfig


@dataclass
class RunMetadata:
    """Metadata for a single benchmark run.

    Attributes:
        run_id: Unique identifier for this run.
        start_time: ISO-8601 timestamp when the run started.
        end_time: ISO-8601 timestamp when the run ended.
        total_duration_seconds: Total wall-clock time in seconds.
        local_model_name: Name of the local LLM model.
        endpoint_url: Base URL of the LLM API endpoint.
        api_key_configured: Whether an API key was provided.
        cpu_info: Human-readable CPU description.
        gpu_info: List of GPU descriptions (empty if none detected).
        ram_total_gb: Total system RAM in gigabytes.
        runtime_version: Version string for the TinyCUA runtime.
        python_version: Python version string.
        judge_model: Optional judge model name for scoring.
        judge_endpoint: Optional judge model endpoint URL.
    """

    run_id: str = ""
    start_time: str = ""
    end_time: str = ""
    total_duration_seconds: float = 0.0
    local_model_name: str = ""
    endpoint_url: str = ""
    api_key_configured: bool = False
    cpu_info: str = "unknown"
    gpu_info: list[str] = field(default_factory=list)
    ram_total_gb: float = 0.0
    runtime_version: str = "unknown"
    python_version: str = ""
    judge_model: str | None = None
    judge_endpoint: str | None = None


def _collect_cpu_info() -> str:
    """Collect CPU information as a human-readable string.

    Returns:
        CPU description string (e.g. 'AMD Ryzen 9 5900X 12-Core').
    """
    try:
        return platform.processor() or "unknown"
    except Exception:
        return "unknown"


def _collect_gpu_info() -> list[str]:
    """Collect GPU information using nvidia-smi if available.

    Returns:
        List of GPU description strings.
    """
    gpus: list[str] = []
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line:
                    gpus.append(line)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return gpus


def _collect_ram_gb() -> float:
    """Collect total system RAM in gigabytes.

    Returns:
        Total RAM in GB.
    """
    try:
        # Try /proc/meminfo on Linux
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    # Value is in kB
                    kb = int(line.split()[1])
                    return round(kb / (1024 * 1024), 1)
    except (FileNotFoundError, ValueError, IndexError):
        pass

    try:
        # Fallback: use os.sysconf
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round((pages * page_size) / (1024**3), 1)
    except (AttributeError, ValueError):
        pass

    return 0.0


def _collect_runtime_version() -> str:
    """Collect TinyCUA runtime version.

    Returns:
        Version string.
    """
    try:
        from tinycua import __version__

        return __version__
    except ImportError:
        pass

    # Fallback: read from pyproject.toml or package metadata
    try:
        from importlib.metadata import version

        return version("tinycua")
    except Exception:
        return "unknown"


def collect_run_metadata(
    config: BenchmarkConfig,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    duration: float = 0.0,
) -> RunMetadata:
    """Collect hardware and runtime metadata for a benchmark run.

    Args:
        config: Benchmark configuration with model/endpoint info.
        start_time: When the run started (defaults to now).
        end_time: When the run ended (defaults to now).
        duration: Total elapsed time in seconds.

    Returns:
        Populated RunMetadata instance.
    """
    now = datetime.now(timezone.utc)

    if start_time is None:
        start_time = now
    if end_time is None:
        end_time = now

    return RunMetadata(
        run_id=str(uuid.uuid4()),
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        total_duration_seconds=duration,
        local_model_name=config.model_name,
        endpoint_url=config.base_url,
        api_key_configured=bool(config.api_key),
        cpu_info=_collect_cpu_info(),
        gpu_info=_collect_gpu_info(),
        ram_total_gb=_collect_ram_gb(),
        runtime_version=_collect_runtime_version(),
        python_version=platform.python_version(),
        judge_model=None,
        judge_endpoint=None,
    )


def preflight_check(output_dir: Path) -> None:
    """Verify the output directory is writable before running tasks.

    Args:
        output_dir: Path to the output directory.

    Raises:
        PermissionError: If the directory is not writable.
        FileNotFoundError: If the directory does not exist.
    """
    output_dir = Path(output_dir)

    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

    if not os.access(output_dir, os.W_OK):
        raise PermissionError(f"Output directory is not writable: {output_dir}")
