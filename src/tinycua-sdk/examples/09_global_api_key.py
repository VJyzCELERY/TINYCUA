"""Example: Using Global API Key

This example demonstrates:
1. Using global API key for system-wide access
2. No login required - just set the API key
3. Access all agents across all tenants

The global API key is defined in backend config (auth.api_key).
It bypasses tenant restrictions and gives system-level access.

Prerequisites:
- Backend configured with global API key
- Runner running
- LM Studio with model

Usage:
    cp .env.example .env
    # Edit .env with:
    #   TINYCUA_BACKEND_URL=http://localhost:8000
    #   TINYCUA_API_KEY=your-global-api-key-from-backend-config
    python examples/09_global_api_key.py
"""

import asyncio
import os

# Import to load .env file
from tinycua_sdk.config import Config
from tinycua_sdk.clients import BackendClient


async def main():
    # Get credentials from environment
    backend_url = os.getenv("TINYCUA_BACKEND_URL", "http://localhost:8000")
    api_key = os.getenv("TINYCUA_API_KEY", "")

    print("=" * 60)
    print("TINYCUA SDK - Global API Key Example")
    print("=" * 60)
    print(f"Backend: {backend_url}")
    print(f"API Key: {'*' * len(api_key) if api_key else '(none)'}")

    if not api_key:
        print("\nERROR: TINYCUA_API_KEY not set!")
        print("Set the global API key in backend config (auth.api_key)")
        return

    # Create client with API key (no login needed)
    client = BackendClient(
        base_url=backend_url,
        api_key=api_key,
    )

    # List all agents across all tenants (system-wide access)
    print("\n[1] Listing all agents (system-wide)...")
    agents = await client.list_agents()
    print(f"    Found {len(agents)} agents:")
    for agent in agents:
        print(f"    - {agent['name']} (ID: {agent['id']})")

    # List all tools across all tenants
    print("\n[2] Listing all tools (system-wide)...")
    tools = await client.list_tools()
    print(f"    Found {len(tools)} tools:")
    for tool in tools:
        print(f"    - {tool['name']} (v{tool.get('version', '?')})")

    # Example: Get a specific agent if exists
    if agents:
        agent_id = agents[0]["id"]
        print(f"\n[3] Getting agent {agent_id}...")
        agent = await client.get_agent(agent_id)
        print(f"    Name: {agent['name']}")
        print(f"    Config: {agent.get('config', {}).get('name', 'N/A')}")

    print("\n" + "=" * 60)
    print("Global API key example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
