"""Example: Remote Runner

This example demonstrates:
1. Using a remote runner to execute agent tasks
2. Configuring HTTP runner
3. Health check for remote runners

Note: This example requires a remote runner server to be running.
If no server is available, the runner will handle errors gracefully.

Usage:
    python examples/04_remote_runner.py
"""

from tinycua_sdk.runner import HTTPRunner, RemoteRunner, RunnerOptions


async def demo_http_runner():
    """Demonstrate HTTP runner."""
    print("\n" + "=" * 50)
    print("HTTP Runner Demo")
    print("=" * 50)

    print("\n1. Creating HTTP runner...")
    runner = HTTPRunner(
        base_url="http://localhost:8000",
        api_key="my-api-key",
        timeout=30,
    )
    print(f"   Base URL: {runner.base_url}")
    print(f"   API Key: {runner.api_key}")
    print(f"   Timeout: {runner.timeout}")

    print("\n2. Checking headers...")
    headers = runner._get_headers()
    print(f"   Headers: {headers}")

    print("\n3. Health check (will fail without server)...")
    is_healthy = await runner.health_check()
    print(f"   Health: {is_healthy}")


async def demo_custom_runner():
    """Demonstrate custom runner implementation."""
    print("\n" + "=" * 50)
    print("Custom Runner Demo")
    print("=" * 50)

    print("\n1. Creating custom runner class...")

    class CustomRunner(RemoteRunner):
        """A custom runner that processes locally."""

        def __init__(self):
            super().__init__(base_url="custom://local")
            self.execution_count = 0

        async def execute(self, messages, tools, options):
            """Execute task (simulated)."""
            self.execution_count += 1
            yield f"Executed task #{self.execution_count}"
            yield "Result: Custom runner works!"

        async def health_check(self):
            """Always healthy."""
            return True

    runner = CustomRunner()
    print(f"   Custom runner created: {runner}")

    print("\n2. Health check...")
    is_healthy = await runner.health_check()
    print(f"   Health: {is_healthy}")

    print("\n3. Execute task...")
    async for event in runner.execute(
        messages=[{"role": "user", "content": "Hello"}],
        tools=[],
        options=RunnerOptions(model="test"),
    ):
        print(f"   Event: {event}")


async def demo_runner_with_agent():
    """Demonstrate using runner with agent."""
    print("\n" + "=" * 50)
    print("Runner with Agent Demo")
    print("=" * 50)

    print("\n1. Creating runner...")
    runner = HTTPRunner(
        base_url="http://localhost:8000",
        api_key="demo-key",
    )

    print("\n2. Creating agent with runner...")
    from tinycua_sdk.agent import Agent

    agent = Agent(
        name="remote-agent",
        provider="openai-compatible",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234/v1",
        api_key="dummy",
        runner=runner,
    )

    print(f"   Agent: {agent.name}")
    print(f"   Runner: {agent.runner}")
    print(f"   Runner type: {type(agent.runner).__name__}")


async def main():
    print("=" * 50)
    print("TINYCUA SDK - Remote Runner Demo")
    print("=" * 50)

    await demo_http_runner()
    await demo_custom_runner()
    await demo_runner_with_agent()

    print("\n" + "=" * 50)
    print("All demos completed!")
    print("=" * 50)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
