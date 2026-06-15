"""End-to-end tests for session and message persistence."""

import asyncio
import json
import os

import httpx


BACKEND_URL = os.getenv("TINYCUA_BACKEND_URL", "http://localhost:8000")

_access_token = None
_tenant_id = None


def get_auth_headers():
    """Get authorization headers."""
    return {"Authorization": f"Bearer {_access_token}"}


async def register():
    """Register a new user and get token."""
    global _access_token, _tenant_id
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/v1/auth/register",
            json={
                "email": f"test_session_{id(object())}@example.com",
                "password": "password123",
                "tenant_name": "Test Session Tenant",
            },
        )
        if response.status_code == 201:
            data = response.json()
            _access_token = data["access_token"]
            _tenant_id = data["tenant_id"]
            print(f"✓ Registered: tenant={_tenant_id}")
            return True
        else:
            print(f"✗ Failed to register: {response.status_code} {response.text}")
            return False


async def create_agent():
    """Create a test agent with LM Studio."""
    agent_data = {
        "name": "session-test-agent",
        "config": {
            "name": "session-test-agent",
            "instructions": "You are a helpful assistant.",
            "provider": "lmstudio",
            "base_url": "http://127.0.0.1:1234",
            "model": "qwen2.5-coder-14b",
            "tools": [],
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
            print(f"✓ Created agent: {data['id']}")
            return data["id"]
        elif response.status_code == 409:
            print("✓ Agent already exists")
            return "existing"
        else:
            print(f"✗ Failed to create agent: {response.status_code} {response.text}")
            return None


async def test_create_session(agent_id: str):
    """Test POST /v1/sessions creates a session."""
    print("\n[TEST] Create Session...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/v1/sessions",
            json={
                "agent_id": agent_id,
                "name": "Test Session",
            },
            headers=get_auth_headers(),
        )
        if response.status_code == 201:
            data = response.json()
            print(f"✓ Session created: {data['id']}")
            return data["id"]
        else:
            print(f"✗ Failed to create session: {response.status_code} {response.text}")
            return None


async def test_get_messages(session_id: str):
    """Test GET /v1/sessions/{id}/messages returns messages."""
    print("\n[TEST] Get Messages...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BACKEND_URL}/v1/sessions/{session_id}/messages",
            headers=get_auth_headers(),
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Got messages: {len(data)} messages")
            return data
        else:
            print(f"✗ Failed to get messages: {response.status_code} {response.text}")
            return None


async def test_add_message(session_id: str, role: str, content: str):
    """Test POST /v1/sessions/{id}/messages adds a message."""
    print(f"\n[TEST] Add Message (role={role})...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/v1/sessions/{session_id}/messages",
            json={"role": role, "content": content},
            headers=get_auth_headers(),
        )
        if response.status_code == 201:
            data = response.json()
            print(
                f"✓ Message added: {data['id']} (turn_index={data.get('turn_index')})"
            )
            return data
        else:
            print(f"✗ Failed to add message: {response.status_code} {response.text}")
            return None


async def test_run_is_stateless(agent_id: str):
    """Test that /run endpoint doesn't require session_id and is stateless."""
    print("\n[TEST] Run Agent (stateless)...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{BACKEND_URL}/v1/agents/{agent_id}/run",
                json={"user_input": "Say 'hello'"},
                headers=get_auth_headers(),
            ) as response:
                if response.status_code == 200:
                    print("✓ Run endpoint works without session_id")
                    return True
                else:
                    print(f"✗ Run failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"✗ Run error: {e}")
            return False


async def test_full_message_flow(agent_id: str):
    """Test full flow: create session → add messages → get messages."""
    print("\n" + "=" * 50)
    print("FULL MESSAGE FLOW TEST")
    print("=" * 50)

    # 1. Create session
    session_id = await test_create_session(agent_id)
    if not session_id:
        return False

    # 2. Get messages (should be empty)
    messages = await test_get_messages(session_id)
    if messages is None:
        return False
    assert len(messages) == 0, "Should start with 0 messages"
    print("✓ Initial messages is empty")

    # 3. Add user message
    msg1 = await test_add_message(session_id, "user", "Hello, how are you?")
    if not msg1:
        return False
    assert msg1["role"] == "user"
    assert msg1["turn_index"] == 0

    # 4. Add assistant message
    msg2 = await test_add_message(session_id, "assistant", "I'm doing great, thanks!")
    if not msg2:
        return False
    assert msg2["role"] == "assistant"
    assert msg2["turn_index"] == 1

    # 5. Add tool message as JSON
    tool_content = json.dumps(
        {"tool_name": "add_numbers", "arguments": {"a": 5, "b": 3}, "result": 8}
    )
    msg3 = await test_add_message(session_id, "tool", tool_content)
    if not msg3:
        return False
    assert msg3["role"] == "tool"
    assert msg3["turn_index"] == 2

    # 6. Get all messages
    final_messages = await test_get_messages(session_id)
    if not final_messages:
        return False
    assert len(final_messages) == 3, (
        f"Should have 3 messages, got {len(final_messages)}"
    )
    print("✓ All 3 messages retrieved correctly")

    # 7. Verify turn indices are sequential
    turn_indices = [m["turn_index"] for m in final_messages]
    assert turn_indices == [0, 1, 2], (
        f"Turn indices should be [0, 1, 2], got {turn_indices}"
    )
    print("✓ Turn indices are sequential")

    return True


async def main():
    """Run all session/message tests."""
    print("=" * 50)
    print("Session & Message Persistence E2E Tests")
    print("=" * 50)

    # Register
    print("\n[Setup] Register user...")
    if not await register():
        return 1

    # Create agent
    print("\n[Setup] Create agent...")
    agent_id = await create_agent()
    if not agent_id:
        return 1

    # Run tests
    tests_passed = 0
    tests_failed = 0

    # Test 1: Stateless run
    if await test_run_is_stateless(agent_id):
        tests_passed += 1
    else:
        tests_failed += 1

    # Test 2: Full message flow
    if await test_full_message_flow(agent_id):
        tests_passed += 1
    else:
        tests_failed += 1

    # Summary
    print("\n" + "=" * 50)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print("=" * 50)

    return 0 if tests_failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
