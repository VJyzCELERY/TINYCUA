"""Experiment-only TINYCUA entrypoint using the existing run implementation."""

from __future__ import annotations

import os
from pathlib import Path

from tinycua.cli.run import run_command


raise SystemExit(
    run_command(
        prompt=os.environ["EXPERIMENT_PROMPT"],
        dir=Path(os.environ.get("EXPERIMENT_WORKSPACE", "/workspace")),
        provider_url=os.environ["EXPERIMENT_LLM_BASE_URL"],
        api_key=os.environ["EXPERIMENT_LLM_API_KEY"],
        model=os.environ["EXPERIMENT_LLM_MODEL"],
        provider_type=os.environ.get(
            "EXPERIMENT_TINYCUA_PROVIDER_TYPE", "openai-chat-completions"
        ),
        worker_effort=os.environ.get("EXPERIMENT_TINYCUA_WORKER_EFFORT", "medium"),
        timeout=int(os.environ.get("EXPERIMENT_TIMEOUT_SECONDS", "900")),
        verbose=os.environ.get("EXPERIMENT_VERBOSE") == "1",
        env_file=None,
    )
)
