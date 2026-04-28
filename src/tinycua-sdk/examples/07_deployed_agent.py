"""Example: Deployed Agent (Backend + Runner)

This example demonstrates:
1. Register a new user and login
2. Creating tools
3. Deploying agent to backend
4. Running deployed agent via backend API

Prerequisites:
- PostgreSQL running (make docker-up)
- Backend running (src/tinycua-backend)
- Runner running (src/tinycua-runner)
- OpenAI-compatible server with model loaded

Usage:
    # Copy .env.example to .env and fill in values
    cp .env.example .env
    # Edit .env with your values
    # Then run:
    python examples/07_deployed_agent.py
"""

import asyncio
import os

# Import to load .env file

from tinycua_sdk.tools import tool
from tinycua_sdk.agent import Agent
from tinycua_sdk.clients import BackendClient


# Get backend URL from environment
BACKEND_URL = os.getenv("TINYCUA_BACKEND_URL", "http://localhost:8000")


@tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b


@tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Product of a and b
    """
    return a * b


@tool()
def get_greeting(name: str) -> str:
    """Get a personalized greeting.

    Args:
        name: Name to greet

    Returns:
        Greeting message
    """
    return f"Hello, {name}! Welcome to TINYCUA."


async def main():
    print("=" * 60)
    print("TINYCUA SDK - Deployed Agent Example")
    print("=" * 60)
    print(f"Backend: {BACKEND_URL}")

    # Step 1: Create backend client and register/login
    print("\n[1] Registering new user...")
    client = BackendClient(base_url=BACKEND_URL)

    # Generate unique email for this run
    import time

    email = f"demo_{int(time.time())}@example.com"
    # WARNING: Do not use the default password in production.
    # Set TINYCUA_PASSWORD environment variable to use a secure password.
    password = os.environ.get("TINYCUA_PASSWORD", "changeme")

    try:
        await client.register(email=email, password=password, tenant_name="Demo Tenant")
        print(f"    Registered new user: {email}")
    except Exception as e:
        # If already exists, try to login
        print(f"    Registration failed, trying login: {e}")
        await client.login(email=email, password=password)
        print(f"    Logged in: {email}")

    print(f"    Logged in as tenant: {client.tenant_id}")

    # Step 2: Create agent with tools
    print("\n[2] Creating agent...")
    agent = Agent(
        name="math-assistant",
        instructions="You are a helpful math assistant. Use the tools to perform calculations.",
        provider=os.getenv("TINYCUA_PROVIDER", "openai-compatible"),
        model=os.getenv("TINYCUA_MODEL", "qwen/qwen3.5-9b"),
        base_url="http://127.0.0.1:1234/v1",
        tools=[add_numbers, multiply, get_greeting],
        backend_url=BACKEND_URL,
        backend_api_key=client.api_key,  # Use the token from login
    )
    print(f"    Agent: {agent.name}")
    print(f"    Tools: {[t.name for t in agent.tools]}")

    # Step 3: Deploy to backend
    print("\n[3] Deploying to backend...")
    deployment = await agent.deploy()
    print("    Status: created")
    print(f"    Agent ID: {deployment.get('id', agent.agent_id)}")
    print(f"    Agent Name: {deployment.get('name')}")
    print(f"    Is deployed: {agent.is_deployed}")

    # Step 4: Run agent via backend (remote execution)
    print("\n[4] Running agent via backend...")
    response = await agent.run("What is 25 + 17? Use the add_numbers tool.")
    print(f"    Response: {response}")

    # Step 5: More examples
    print("\n[5] Running more examples...")

    response = await agent.run("What is 12 times 8? Use the multiply tool.")
    print(f"    Multiply: {response}")

    response = await agent.run("Say hello to Alice.")
    print(f"    Greeting: {response}")

    # Step 6: Check agent info
    print("\n[6] Agent info...")
    print(f"    Name: {agent.name}")
    print(f"    Deployed: {agent.is_deployed}")
    print(f"    Mode: {agent.mode}")
    print(f"    Backend URL: {client.base_url}")

    # Step 7: List deployed agents
    print("\n[7] Listing your agents...")
    agents = await client.list_agents()
    print(f"    Total agents: {len(agents)}")
    for a in agents:
        print(f"    - {a['name']} (ID: {a['id']})")

    print("\n" + "=" * 60)
    print("Deployed agent example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
