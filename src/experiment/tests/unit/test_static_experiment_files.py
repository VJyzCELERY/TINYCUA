"""Static checks for compose and agent image setup."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_compose_defines_four_services_and_volumes() -> None:
    """Compose defines the four harness services."""
    compose = (ROOT / "docker-compose.yml").read_text()

    for service in ["opencode", "hermes", "openclaw", "tinycua"]:
        assert f"  {service}:" in compose
        assert "env_file:\n      - .env" in compose
    assert "  searxng:" in compose
    assert "docker.io/searxng/searxng:latest" in compose
    assert "${EXPERIMENT_SEARXNG_HOST_PORT:-18080}:8080" in compose
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
        "opencode.Dockerfile": [
            "npm install -g opencode-ai",
            "--thinking",
            "--dangerously-skip-permissions",
            "opencode run",
        ],
        "openclaw.Dockerfile": [
            "npm install -g openclaw@latest",
            r'\"profile\":\"full\"',
            "--verbose on",
            "openclaw agent",
        ],
        "hermes.Dockerfile": [
            "pip install",
            "hermes-agent==0.16.0",
            "hermes chat",
            "--verbose",
            "--yolo",
            "SEARXNG_URL",
        ],
    }

    for name, snippets in expected.items():
        text = (ROOT / "docker" / name).read_text()
        for snippet in snippets:
            assert snippet in text


def test_harnesses_receive_searxng_config() -> None:
    """Harnesses with web search get SearXNG env/config aliases."""
    compose = (ROOT / "docker-compose.yml").read_text()
    env = (ROOT / ".env.example").read_text()
    openclaw = (ROOT / "docker" / "openclaw.Dockerfile").read_text()
    searxng_settings = (ROOT / "docker" / "searxng" / "settings.yml").read_text()

    assert "EXPERIMENT_SEARXNG_HOST_PORT=18080" in env
    assert "EXPERIMENT_SEARXNG_BASE_URL=http://searxng:8080" in env
    assert "TINYCUA_SEARXNG_URL=http://searxng:8080/search" in env
    assert (
        "SEARXNG_URL: "
        "${EXPERIMENT_SEARXNG_BASE_URL:-http://searxng:8080}"
    ) in compose
    assert (
        "SEARXNG_BASE_URL: "
        "${EXPERIMENT_SEARXNG_BASE_URL:-http://searxng:8080}"
    ) in compose
    assert (
        "TINYCUA_SEARXNG_URL: "
        "${TINYCUA_SEARXNG_URL:-http://searxng:8080/search}"
    ) in compose
    assert "depends_on:" in compose
    assert "./docker/searxng/settings.yml:/etc/searxng/settings.yml:ro" in compose
    assert '\\"provider\\":\\"searxng\\"' in openclaw
    assert '\\"baseUrl\\":\\"' in openclaw
    assert "%/search" in openclaw
    assert "formats:" in searxng_settings
    assert "- json" in searxng_settings


def test_helper_scripts_wrap_setup_and_runner() -> None:
    """Shell helpers keep common commands one step."""
    setup = (ROOT / "scripts" / "setup.sh").read_text()
    run = (ROOT / "scripts" / "run.sh").read_text()

    assert "cp .env.example .env" in setup
    assert "docker compose build" in setup
    assert "docker compose pull searxng" in setup
    assert "docker pull docker.io/library/busybox:1.36" in setup
    assert "uv run python" in run
    assert "run_experiment.py" in run
    assert "--num" in run
    assert "--prompt" in run
