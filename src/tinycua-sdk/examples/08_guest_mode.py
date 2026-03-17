"""Example: Guest Mode (No Auth Required)

This example demonstrates:
1. Using guest mode for unauthenticated agent execution
2. Temporary sessions that don't persist
3. Shared multi-user access

Guest mode features:
- No login/auth required
- Sessions are in-memory (auto-expire after 30 min)
- Multiple users can use simultaneously
- No persistence - sessions lost on restart

Prerequisites:
- PostgreSQL (make docker-up)
- Backend running
- Runner running
- LM Studio with model
- An agent deployed to the backend (get agent ID from backend)

Usage:
    cp .env.example .env
    # Edit .env with TINYCUA_BACKEND_URL
    # Update DEPLOYED_AGENT_ID below with your agent ID
    python examples/08_guest_mode.py
"""

import asyncio

# Import to load .env file

from tinycua_sdk.agent import Agent


async def main():
    print("=" * 60)
    print("TINYCUA SDK - Guest Mode Example")
    print("=" * 60)

    # Guest mode doesn't require login
    # Just provide the agent ID of a deployed agent

    # Option 1: Create agent and set to guest mode
    print("\n[1] Creating agent in guest mode...")
    agent = Agent(
        name="guest-agent",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://127.0.0.1:1234",
        # No tools needed - they come from the deployed agent
    )

    # Set to guest mode with deployed agent ID
    # Replace with your actual deployed agent ID
    DEPLOYED_AGENT_ID = "YOUR-DEPLOYED-AGENT-ID-HERE"

    agent.set_guest_mode(
        agent_id=DEPLOYED_AGENT_ID,
        backend_url="http://localhost:8000",
    )

    print(f"    Mode: {agent.mode}")
    print(f"    Agent ID: {agent.agent_id}")

    # Option 2: Quick guest run without creating agent object
    print("\n[2] Quick guest run...")
    from tinycua_sdk.clients import BackendClient

    client = BackendClient(base_url="http://localhost:8000")

    print("    Streaming response: ", end="")
    async for event in client.guest_run(
        agent_id=DEPLOYED_AGENT_ID,
        user_input="Say hello!",
    ):
        if isinstance(event, dict):
            if event.get("type") == "content":
                print(event.get("data", {}).get("content", ""), end="", flush=True)
    print()

    # Guest session continues across requests
    print("\n[3] Continuing conversation...")
    print("    Streaming response: ", end="")
    async for event in client.guest_run(
        agent_id=DEPLOYED_AGENT_ID,
        user_input="What was my first message?",
    ):
        if isinstance(event, dict):
            if event.get("type") == "content":
                print(event.get("data", {}).get("content", ""), end="", flush=True)
    print()

    print("\n" + "=" * 60)
    print("Guest mode example completed!")
    print("=" * 60)
    print("\nNote: Guest sessions are temporary and expire after 30 min of inactivity.")


if __name__ == "__main__":
    asyncio.run(main())
