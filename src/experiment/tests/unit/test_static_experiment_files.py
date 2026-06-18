"""Static checks for compose and agent image setup."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_compose_defines_four_services_and_volumes() -> None:
    """Compose keeps the four harnesses isolated."""
    compose = (ROOT / "docker-compose.yml").read_text()

    for service in ["opencode", "hermes", "openclaw", "tinycua"]:
        assert f"  {service}:" in compose
        assert "env_file:\n      - .env" in compose
    for volume in ["Opencode_Vol", "Hermes_Vol", "Openclaw_Vol", "TINYCUA_Vol"]:
        assert volume in compose
    assert "host.docker.internal:host-gateway" in compose


def test_tinycua_dockerfile_installs_local_packages() -> None:
    """TINYCUA image uses this branch's code."""
    dockerfile = (ROOT / "docker" / "tinycua.Dockerfile").read_text()

    assert "COPY src/tinycua-sdk ./tinycua-sdk" in dockerfile
    assert "COPY src/tinycua ./tinycua" in dockerfile
    assert "uv pip install --no-cache-dir --system ./tinycua-sdk" in dockerfile
    assert "uv pip install --no-cache-dir --system ./tinycua" in dockerfile
    assert "tinycua run" in dockerfile
    assert "--dir" in dockerfile


def test_agent_dockerfiles_expose_harness_commands() -> None:
    """Agent commands stay visible and fail loud."""
    expected = {
        "opencode.Dockerfile": ["npm install -g opencode-ai", "lmstudio", "opencode run"],
        "openclaw.Dockerfile": ["npm install -g openclaw@latest", "openai-completions", "openclaw agent"],
        "hermes.Dockerfile": ["pip install", "hermes-agent==0.16.0", "hermes"],
    }

    for name, snippets in expected.items():
        text = (ROOT / "docker" / name).read_text()
        for snippet in snippets:
            assert snippet in text


def test_helper_scripts_wrap_setup_and_runner() -> None:
    """Shell helpers keep common commands one step."""
    setup = (ROOT / "scripts" / "setup.sh").read_text()
    run = (ROOT / "scripts" / "run.sh").read_text()

    assert "cp .env.example .env" in setup
    assert "docker compose build" in setup
    assert "uv run python run_experiment.py" in run
    assert "--num" in run
    assert "--prompt" in run
