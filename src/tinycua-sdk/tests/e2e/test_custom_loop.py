"""End-to-end test for custom agent loop."""

import asyncio

import httpx


BACKEND_URL = "http://localhost:8000"

_access_token = None


def get_auth_headers():
    """Get authorization headers."""
    return {"Authorization": f"Bearer {_access_token}"}


async def register():
    """Register a new user and get token."""
    global _access_token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/v1/auth/register",
            json={
                "email": f"test_loop_{id(object())}@example.com",
                "password": "password123",
                "tenant_name": "Test Loop Tenant",
            },
        )
        if response.status_code == 201:
            data = response.json()
            _access_token = data["access_token"]
            print(f"✓ Registered: tenant={data['tenant_id']}")
            return True
        else:
            print(f"✗ Failed to register: {response.status_code} {response.text}")
            return False


async def create_tool():
    """Create a test tool."""
    tool_data = {
        "name": "add_numbers",
        "description": "Add two numbers together",
        "source": "def add_numbers(a: int, b: int) -> int:\n    return a + b",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        },
        "external_dependencies": [],
        "tool_dependencies": [],
        "version": "test123",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/v1/tools",
            json=tool_data,
            headers=get_auth_headers(),
        )
        if response.status_code == 201:
            data = response.json()
            print(f"✓ Created tool: {data['id']} ({data['name']})")
            return data["id"]
        elif response.status_code == 409:
            print("✓ Tool already exists")
            return "existing"
        else:
            print(f"✗ Failed to create tool: {response.status_code} {response.text}")
            return None


async def create_agent_with_custom_loop():
    """Create an agent with custom loop."""
    custom_loop_code = """class CustomLoggingLoop(DefaultLoop):
    async def run(self, agent, user_input, **kwargs):
        print(f"[CustomLoggingLoop] Input: {user_input}")
        result = await super().run(agent, user_input, **kwargs)
        print(f"[CustomLoggingLoop] Done")
        return result
"""

    agent_data = {
        "name": "custom-loop-agent",
        "config": {
            "name": "custom-loop-agent",
            "instructions": "You are a helpful assistant that uses tools.",
            "provider": "lmstudio",
            "base_url": "http://127.0.0.1:1234",
            "model": "qwen/qwen3.5-9b",
            "tools": ["add_numbers"],
            "loop_code": custom_loop_code,
            "loop_class": "CustomLoggingLoop",
        },
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/v1/agents",
            json=agent_data,
            headers=get_auth_headers(),
        )
        if response.status_code == 201:
            data = response.json()
            print(f"✓ Created agent with custom loop: {data['id']}")
            return data["id"]
        elif response.status_code == 409:
            print("✓ Agent already exists")
            return "existing"
        else:
            print(f"✗ Failed to create agent: {response.status_code} {response.text}")
            return None


async def run_agent(agent_id: str, plan_mode: bool = False):
    """Run the agent and collect streaming response."""
    request_data = {
        "user_input": "What is 5 + 3? Use the add_numbers tool.",
        "plan_mode": plan_mode,
    }

    print(f"\n→ Running agent {agent_id} (plan_mode={plan_mode})...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{BACKEND_URL}/v1/agents/{agent_id}/run",
                json=request_data,
                headers=get_auth_headers(),
            ) as response:
                print(f"  Status: {response.status_code}")
                full_response = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data:
                            full_response += data + "\n"
                print(f"  Response: {full_response[:300]}...")
                return full_response
        except Exception as e:
            print(f"✗ Error running agent: {e}")
            import traceback

            traceback.print_exc()
            return None


async def main():
    """Run the end-to-end test."""
    print("=" * 50)
    print("End-to-End Test: Custom Agent Loop")
    print("=" * 50)

    # Step 1: Register
    print("\n[Step 1] Register user...")
    if not await register():
        return 1

    # Step 2: Create tool
    print("\n[Step 2] Creating tool...")
    tool_result = await create_tool()
    if not tool_result:
        print("Failed to create tool, exiting.")
        return 1

    # Step 3: Create agent with custom loop
    print("\n[Step 3] Creating agent with custom loop...")
    agent_result = await create_agent_with_custom_loop()
    if not agent_result:
        print("Failed to create agent, exiting.")
        return 1

    # Step 4: Run agent (normal mode)
    print("\n[Step 4] Running agent (plan_mode=False)...")
    result1 = await run_agent(
        "existing" if agent_result == "existing" else agent_result, plan_mode=False
    )

    # Step 5: Run agent (plan mode)
    print("\n[Step 5] Running agent (plan_mode=True)...")
    result2 = await run_agent(
        "existing" if agent_result == "existing" else agent_result, plan_mode=True
    )

    print("\n" + "=" * 50)
    if result1 and result2:
        print("✓ End-to-end test PASSED")
        return 0
    else:
        print("✗ End-to-end test FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
