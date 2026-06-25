"""Integration tests for the agent harness experiment runner."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICES = ["opencode", "hermes", "openclaw", "tinycua"]


def make_fake_docker(tmp_path: Path) -> None:
    """Create a docker stub that records compose service invocations."""
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, sys\n"
        f"services = {SERVICES!r}\n"
        "service = [arg for arg in sys.argv if arg in services][-1]\n"
        "pathlib.Path(os.environ['DOCKER_CALLS']).open('a').write(service + '\\n')\n"
        "print(f'{service} stdout')\n"
        "print(f'{service} stderr', file=sys.stderr)\n"
        "sys.exit(7 if service == 'hermes' else 0)\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)


def test_runner_invokes_all_agents_in_order_and_writes_metadata(tmp_path: Path):
    """One prompt runs all four services, even when Hermes fails."""
    calls = tmp_path / "calls.txt"
    make_fake_docker(tmp_path)
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(calls),
    }
    (tmp_path / ".env").write_text("EXPERIMENT_LLM_MODEL=test-model\n")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "run_experiment.py"),
            "--num",
            "1",
            "--prompt",
            "compare harnesses",
            "--output-root",
            str(tmp_path / "results"),
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[opencode] starting experiment-1" in result.stdout
    assert "[tinycua] passed exit_code=0" in result.stdout
    assert "summary: opencode=passed, hermes=failed, openclaw=passed, tinycua=passed" in result.stdout
    assert calls.read_text().splitlines() == SERVICES
    for agent in SERVICES:
        root = tmp_path / "results" / agent / "experiment-1" / "logs"
        assert (root / "prompt.txt").read_text() == "compare harnesses"
        assert (root / "container.env").read_text() == "EXPERIMENT_LLM_MODEL=test-model\n"
        assert (root / "stdout.log").read_text() == f"{agent} stdout\n"
        assert (root / "stderr.log").read_text() == f"{agent} stderr\n"
        meta = json.loads((root / "metadata.json").read_text())
        assert meta["agent"] == agent
        assert meta["experiment_num"] == 1
        assert "duration_seconds" in meta
    hermes_meta = json.loads(
        (tmp_path / "results" / "hermes" / "experiment-1" / "logs" / "metadata.json").read_text()
    )
    assert hermes_meta["exit_code"] == 7
    assert hermes_meta["status"] == "failed"


def test_runner_rejects_empty_prompt_before_docker(tmp_path: Path):
    """Whitespace prompts fail before invoking Docker."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "run_experiment.py"), "--num", "1", "--prompt", "   "],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "prompt" in result.stderr.lower()


def test_runner_rejects_existing_output_without_overwrite(tmp_path: Path):
    """Existing experiment paths are protected."""
    existing = tmp_path / "results" / "opencode" / "experiment-1"
    existing.mkdir(parents=True)

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "run_experiment.py"),
            "--num",
            "1",
            "--prompt",
            "compare harnesses",
            "--output-root",
            str(tmp_path / "results"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "overwrite" in result.stderr.lower()


def test_runner_times_out_agents_and_writes_partial_logs(tmp_path: Path):
    """Hung containers are killed and still leave logs."""
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, time\n"
        "print('started', flush=True)\n"
        "time.sleep(5)\n"
        "sys.exit(0)\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    env = os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}"}

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "run_experiment.py"),
            "--num",
            "3",
            "--prompt",
            "compare harnesses",
            "--output-root",
            str(tmp_path / "results"),
            "--timeout-seconds",
            "1",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    first = tmp_path / "results" / "opencode" / "experiment-3" / "logs"
    assert (first / "stdout.log").read_text() == "started\n"
    assert "Timed out after 1 seconds" in (first / "stderr.log").read_text()
    assert json.loads((first / "metadata.json").read_text())["exit_code"] == 124
