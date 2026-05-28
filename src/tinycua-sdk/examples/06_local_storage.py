"""Example: Using Local Database Storage with Context Tools and Agent

This example demonstrates:
1. Creating a local SQLite database for session storage
2. Adding messages to a session
3. Using context retrieval tools with an AI Agent
4. Agent can search context, get summary, get recent turns
5. Automatic cleanup with try/finally

Prerequisites:
    - OpenAI-compatible server must be running at http://localhost:1234/v1
    - Or update the provider/model/base_url to use another LLM

Usage:
    python examples/06_local_storage.py
"""

import tempfile
from pathlib import Path

from tinycua_sdk.agent import Agent
from tinycua_sdk.storage.store import SessionStore
from tinycua.agent.tools.context_tools import (
    get_context_summary_tool,
    get_recent_turns_tool,
    search_context_grep_tool,
)


def main():
    """Run the local storage example with AI Agent."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "tinycua.db"

    store = None
    try:
        print("=" * 60)
        print("Local Database Storage with AI Agent Example")
        print("=" * 60)

        # Create session store with temporary database
        db_url = f"sqlite:///{db_path}"
        print(f"\n1. Creating database at: {db_path}")
        store = SessionStore(db_url)
        store.create_tables()

        # Create a new session
        print("\n2. Creating a new session...")
        session = store.create_session(name="Chat with Assistant", user_id="user-123")
        print(f"   Session ID: {session.id}")
        print(f"   Session Name: {session.name}")

        # Add messages to the session
        print("\n3. Adding messages to session...")
        messages = [
            ("user", "Hello, my name is Bob"),
            ("assistant", "Hi Bob! Nice to meet you."),
            ("user", "What's the weather like today?"),
            ("assistant", "The weather today is sunny, 72°F."),
            ("user", "Remember my favorite color is blue"),
            ("assistant", "I'll remember that your favorite color is blue!"),
        ]

        for role, content in messages:
            msg = store.add_message(session.id, role, content)
            print(f"   [{msg.turn_index}] {role}: {content[:30]}...")

        # Update full context for grep search
        print("\n4. Updating full context for search...")
        store.update_full_context(session.id)

        # Add a summary
        print("\n5. Adding session summary...")
        summary_text = """# Conversation Summary

- User introduced themselves as Bob
- User asked about weather (sunny, 72°F)
- User shared that their favorite color is blue"""
        store.update_summary(session.id, summary_text)

        # Create context tools
        print("\n6. Creating context retrieval tools...")
        grep_tool = search_context_grep_tool(store, session.id)
        summary_tool = get_context_summary_tool(store, session.id)
        recent_tool = get_recent_turns_tool(store, session.id)

        # Create agent with context tools
        print("\n7. Creating Agent with context tools...")
        agent = Agent(
            name="context-agent",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
            tools=[grep_tool, summary_tool, recent_tool],
        )

        # Test: Ask about user's name (should use recent turns or grep)
        print("\n8. Testing: Agent asks 'What is my name?'")
        print("   (Agent should use context tools to find answer)")
        print("   NOTE: Requires OpenAI-compatible server running at http://localhost:1234/v1")

        import asyncio

        try:
            response = asyncio.run(
                agent.run(
                    "What is my name? Use the context tools to find out.",
                    force_local=True,
                )
            )
            print(f"   Response: {response[:200]}...")
        except Exception as e:
            print(f"   ERROR: {e}")
            print("   Make sure OpenAI-compatible server is running with the model loaded!")
            print("   Skipping agent tests - context tools work without LLM")

        print("\n" + "=" * 60)
        print("Example completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        # Cleanup
        import shutil

        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)
            print(f"\nCleanup: Removed temporary directory {temp_dir}")


if __name__ == "__main__":
    main()
