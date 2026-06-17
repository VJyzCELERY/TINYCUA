"""ClaudeCodeAgent — WildClawBench adapter for Claude Code harness."""

from agent_benchmark.agents.docker_agent import DockerAgent


class ClaudeCodeAgent(DockerAgent):
    """Claude Code harness agent. Pre-built upstream image, env-var config."""

    image_name = "wildclawbench-claudecode-ubuntu:v0.2"
    api_key_env = "ANTHROPIC_API_KEY"
