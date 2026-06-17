"""CodexAgent — WildClawBench adapter for Codex CLI harness."""

from agent_benchmark.agents.docker_agent import DockerAgent


class CodexAgent(DockerAgent):
    """Codex CLI harness agent. Pre-built upstream image, env-var config."""

    image_name = "wildclawbench-codex-ubuntu:v0.0"
    api_key_env = "OPENAI_API_KEY"
