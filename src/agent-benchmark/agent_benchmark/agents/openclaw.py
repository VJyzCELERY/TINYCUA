"""OpenClawAgent — WildClawBench adapter for OpenClaw harness."""

from agent_benchmark.agents.docker_agent import DockerAgent


class OpenClawAgent(DockerAgent):
    """OpenClaw harness agent. Pre-built upstream image, env-var config."""

    image_name = "wildclawbench-ubuntu:v1.3"
    api_key_env = "OPENROUTER_API_KEY"
