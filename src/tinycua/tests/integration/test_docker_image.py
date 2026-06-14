"""Integration tests for Docker image build and container lifecycle."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

IMAGE_TAG = "tinycua-benchmark:test"


@pytest.fixture
def test_workspace(tmp_path: Path) -> Path:
    """Provide a temporary workspace directory for Docker volume mounts."""
    return tmp_path


@pytest.mark.integration
class TestDockerfileBuild:
    """Verify the Dockerfile builds successfully."""

    def test_dockerfile_exists(self) -> None:
        """Dockerfile exists at the project root."""
        from pathlib import Path

        dockerfile = Path(__file__).parent.parent.parent.parent / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile must exist at project root"

    @pytest.mark.slow
    def test_docker_image_builds(self) -> None:
        """Docker image builds without errors."""
        result = subprocess.run(
            ["docker", "build", "-t", IMAGE_TAG, "."],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, f"Build failed:\n{result.stderr}"

    @pytest.mark.slow
    def test_image_size_under_2gb(self) -> None:
        """Built image is under 2GB."""
        result = subprocess.run(
            ["docker", "image", "inspect", IMAGE_TAG, "--format", "{{.Size}}"],
            capture_output=True,
            text=True,
        )
        size_bytes = int(result.stdout.strip())
        size_gb = size_bytes / (1024**3)
        assert size_gb < 2.0, f"Image size {size_gb:.2f}GB exceeds 2GB target"


@pytest.mark.integration
class TestContainerStartup:
    """Verify the container starts and reaches a ready state."""

    def test_container_starts(self) -> None:
        """Container starts without errors."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-e",
                "TINYCUA_BASE_URL=http://example.com/v1",
                "-e",
                "TASK_PROMPT=test",
                IMAGE_TAG,
                "echo",
                "ready",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Container failed to start:\n{result.stderr}"
        assert "ready" in result.stdout

    def test_container_fails_without_model_endpoint(self) -> None:
        """Container fails with clear error when TINYCUA_BASE_URL is missing."""
        result = subprocess.run(
            ["docker", "run", "--rm", IMAGE_TAG],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0, (
            f"Container should fail without TINYCUA_BASE_URL:\n{result.stderr}"
        )
        assert "TINYCUA_BASE_URL" in result.stderr, (
            "Error message must mention TINYCUA_BASE_URL"
        )

    def test_entrypoint_validates_base_url(self) -> None:
        """Entrypoint validates TINYCUA_BASE_URL without command override."""
        result = subprocess.run(
            ["docker", "run", "--rm", IMAGE_TAG],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0, "Container should fail without TINYCUA_BASE_URL"
        assert "TINYCUA_BASE_URL" in result.stderr, (
            "Entrypoint must mention TINYCUA_BASE_URL in error"
        )

    def test_container_fails_without_task_prompt(self) -> None:
        """Container fails with clear error when TASK_PROMPT is missing."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-e",
                "TINYCUA_BASE_URL=http://example.com/v1",
                IMAGE_TAG,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0, (
            f"Container should fail without TASK_PROMPT:\n{result.stderr}"
        )
        assert "TASK_PROMPT" in result.stderr, "Error message must mention TASK_PROMPT"


@pytest.mark.integration
class TestWorkspaceMounting:
    """Verify /tmp_workspace mounting and read/write operations."""

    def test_workspace_is_writable(self, test_workspace: Path) -> None:
        """Container can write to /tmp_workspace."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{test_workspace}:/tmp_workspace",
                "-e",
                "TINYCUA_BASE_URL=http://example.com/v1",
                "-e",
                "TASK_PROMPT=test",
                IMAGE_TAG,
                "sh",
                "-c",
                "touch /tmp_workspace/test-file && echo ok",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Workspace write failed:\n{result.stderr}"
        assert "ok" in result.stdout


@pytest.mark.integration
class TestEnvironmentVariables:
    """Verify environment variable injection and accessibility."""

    def test_env_vars_accessible(self) -> None:
        """Injected environment variables are accessible inside the container."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-e",
                "TINYCUA_BASE_URL=http://example.com/v1",
                "-e",
                "BRAVE_API_KEY=test-key-123",
                "-e",
                "TASK_PROMPT=test",
                IMAGE_TAG,
                "sh",
                "-c",
                "echo $BRAVE_API_KEY",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "test-key-123" in result.stdout


@pytest.mark.integration
class TestTinyCUAInstalled:
    """Verify TinyCUA is installed and the CLI is available."""

    def test_tinycua_cli_available(self) -> None:
        """tinycua CLI is available in the container."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-e",
                "TINYCUA_BASE_URL=http://example.com/v1",
                "-e",
                "TASK_PROMPT=test",
                IMAGE_TAG,
                "tinycua",
                "--help",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"tinycua CLI not found:\n{result.stderr}"
        assert "tinycua" in result.stdout.lower()

    def test_tinycua_benchmark_subcommand(self) -> None:
        """tinycua benchmark subcommand is available."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-e",
                "TINYCUA_BASE_URL=http://example.com/v1",
                "-e",
                "TASK_PROMPT=test",
                IMAGE_TAG,
                "tinycua",
                "benchmark",
                "--help",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"benchmark subcommand not found:\n{result.stderr}"
        )
