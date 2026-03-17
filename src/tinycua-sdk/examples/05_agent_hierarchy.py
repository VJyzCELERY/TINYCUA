"""Example: Agent Hierarchy with Real Delegation

This example demonstrates:
1. Creating agents with specialized sub-agents
2. Manual delegation pattern (main agent calls sub-agents)
3. Passing context and instructions to sub-agents
4. Aggregating results from multiple sub-agents
5. Complex multi-step workflows

Usage:
    python examples/05_agent_hierarchy.py
"""

import asyncio
from tinycua_sdk.agent import Agent


async def demo_manual_delegation():
    """Demonstrate basic agent hierarchy structure."""
    print("\n" + "=" * 50)
    print("Agent Hierarchy Structure")
    print("=" * 50)

    print("\n1. Creating specialized sub-agents...")
    researcher = Agent(
        name="researcher",
        instructions="You are a research assistant. Find accurate information.",
    )
    coder = Agent(
        name="coder",
        instructions="You are a coding assistant. Write clean, working code.",
    )
    writer = Agent(
        name="writer",
        instructions="You are a technical writer. Write clear documentation.",
    )
    print("   Created: researcher, coder, writer")

    print("\n2. Creating main agent (coordinator)...")
    coordinator = Agent(
        name="coordinator",
        instructions="""You are a project coordinator.
        When given a task, analyze it and delegate to specialized sub-agents.
        Aggregate their results into a cohesive response.""",
        sub_agents=[researcher, coder, writer],
    )
    print(
        f"   Main: {coordinator.name}, Sub-agents: {[a.name for a in coordinator.sub_agents]}"
    )


async def demo_delegation_with_llm():
    """Demonstrate full end-to-end delegation flow with LM Studio."""
    print("\n" + "=" * 50)
    print("Full End-to-End Delegation Flow (LM Studio)")
    print("=" * 50)

    print("\n1. Creating sub-agents (LLM will decide when to delegate)...")

    searcher = Agent(
        name="searcher",
        instructions="You are a research assistant. Find and provide information clearly.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )
    coder = Agent(
        name="coder",
        instructions="You are a coding assistant. Write clean, working code.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )

    print("   Created sub-agents: searcher, coder")
    print("   (LLM will decide when to use delegate tools)")

    print("\n2. Creating main coordinator agent...")
    coordinator = Agent(
        name="coordinator",
        instructions="""You are a helpful assistant. You have access to specialist agents:
- searcher: Use for research, finding information, explaining concepts
- coder: Use for writing code, programming tasks

When a task matches a specialist's expertise, use the delegate tool to hand off the task.""",
        sub_agents=[searcher, coder],
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )

    print(f"   Main: {coordinator.name}")
    print(f"   Sub-agents: {[a.name for a in coordinator.sub_agents]}")

    print("\n3. Running tasks (LLM decides whether to delegate)...")
    print("   Try verbose=True to see delegation flow:")

    tasks = [
        "What is async/await in Python?",
        "Write a hello world function in Rust",
        "Hello there, how are you?",
    ]

    for task in tasks:
        print(f"\n   Task: '{task}'")

        try:
            result = await coordinator.run(task)
            print(f"   Result: {result[:200]}...")
        except Exception as e:
            print(f"   Error: {type(e).__name__}: {e}")


async def demo_stream_sse():
    """Demonstrate stream_sse - full event stream."""
    print("\n" + "=" * 50)
    print("Stream SSE Demo (Full Event Stream)")
    print("=" * 50)

    print("\n1. Creating agents...")
    coder = Agent(
        name="coder",
        instructions="You are a coding assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )

    coordinator = Agent(
        name="coordinator",
        instructions="Delegate to coder when needed.",
        sub_agents=[coder],
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )

    print("\n2. Using stream_sse=True to get every event:")
    print("   - LLM request/response")
    print("   - Tool call start/end")
    print("   - Delegation start/end")
    print("   - Content chunks")
    print()

    stream = await coordinator.run(
        "Use delegate_to_coder to write hello", stream_sse=True
    )

    async for event in stream:
        t = event.type.value
        d = event.data

        if t == "llm_request":
            print(f"   [LLM] Request: model={d.get('model')}")
        elif t == "content":
            content = d.get("content", "")
            if content:
                print(f"   [CONTENT] {content[:50]}...")
        elif "delegation" in t:
            print(f"   [{t.upper()}] {d.get('agent')}: {d.get('task', '')[:30]}...")
        elif t.startswith("tool_call"):
            print(f"   [{t.upper()}] {d.get('tool_name', '')}")
        elif t.startswith("tool_result"):
            print(f"   [{t.upper()}] {d.get('tool_name', '')}")


async def demo_verbose_delegation():
    """Demonstrate verbose mode to see delegation flow."""
    print("\n" + "=" * 50)
    print("Verbose Delegation Demo")
    print("=" * 50)

    import logging

    logging.basicConfig(
        level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s"
    )

    print("\n1. Creating agents...")
    coder = Agent(
        name="coder",
        instructions="You are a coding assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )

    coordinator = Agent(
        name="coordinator",
        instructions="Delegate to coder when needed.",
        sub_agents=[coder],
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )

    print("\n2. Running with verbose=True...")
    print("   (Watch logs below for delegation flow)")
    print()

    try:
        result = await coordinator.run(
            "Use delegate_to_coder to write a hello world", verbose=True
        )
        print(f"\n   Final result: {result[:150]}...")
    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")


async def demo_streaming_delegation():
    """Demonstrate streaming with sub-agent delegation."""
    print("\n" + "=" * 50)
    print("Streaming with Delegation Demo")
    print("=" * 50)

    import logging

    logging.basicConfig(
        level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s"
    )

    print("\n1. Creating agents...")
    coder = Agent(
        name="coder",
        instructions="You are a coding assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )

    coordinator = Agent(
        name="coordinator",
        instructions="Delegate to coder when needed.",
        sub_agents=[coder],
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )

    print("\n2. Running with stream() - watch delegation happen live:")
    print()

    try:
        async for event in coordinator.stream(
            "Use delegate_to_coder to write hello world"
        ):
            if event.type.name == "CONTENT":
                print(event.data.get("content", ""), end="", flush=True)
            elif event.type.name == "TOOL_CALL_START":
                print(f"\n>>> [Delegating to {event.data.get('tool_name')}]")
            elif event.type.name == "TOOL_RESULT_CHUNK":
                print(event.data.get("content", ""), end="", flush=True)
            elif event.type.name == "TOOL_RESULT_END":
                print("\n<<< [Delegation complete]")
    except Exception as e:
        print(f"\n   Error: {type(e).__name__}: {e}")


async def demo_explicit_delegation():
    """Demonstrate explicit delegation pattern."""
    print("\n" + "=" * 50)
    print("Explicit Delegation Pattern")
    print("=" * 50)

    print("\n1. Creating sub-agents with specific purposes...")

    searcher = Agent(name="searcher", instructions="Find information on any topic.")
    writer = Agent(name="writer", instructions="Write content based on research.")

    coordinator = Agent(
        name="coordinator",
        instructions="You coordinate tasks between searcher and writer.",
        sub_agents=[searcher, writer],
    )

    print("   coordinator -> [searcher, writer]")

    print("\n2. Manual delegation flow...")

    user_request = "Research Python async programming and write a guide"

    parts = user_request.split(" and ")
    print(f"   Task: '{user_request}'")
    print(f"   Split into: {parts}")

    print("\n3. Delegating to searcher...")
    search_task = parts[0].replace("Research ", "")
    print(f"   Running searcher.run('{search_task}')")
    context = coordinator._pass_context_to_sub_agent(search_task, searcher)
    print(f"   Context passed: {len(context)} chars")

    print("\n4. Delegating to writer...")
    write_task = parts[1].replace("write a ", "")
    print(f"   Running writer.run('{write_task}')")
    context = coordinator._pass_context_to_sub_agent(write_task, writer)
    print(f"   Context passed: {len(context)} chars")

    print("\n5. Aggregating results...")
    research_result = "Async/await helps write concurrent code without callbacks."
    write_result = "Here's a guide to Python async programming..."
    combined = coordinator._aggregate_results(research_result, searcher)
    combined += "\n" + coordinator._aggregate_results(write_result, writer)
    print(f"   Combined: {len(combined)} chars")


async def demo_task_routing():
    """Demonstrate task routing based on configurable keywords."""
    print("\n" + "=" * 50)
    print("Task Routing with Configurable Keywords")
    print("=" * 50)

    print("\n1. Creating specialized agents with custom keywords...")

    searcher = Agent(
        name="searcher",
        keywords=["search", "find", "look up", "google", "research", "browse"],
    )
    file_handler = Agent(
        name="file_handler",
        keywords=["read", "write", "file", "save", "load", "delete"],
    )
    calculator = Agent(
        name="calculator",
        keywords=["calculate", "compute", "math", "sum", "average", "total"],
    )
    email_agent = Agent(
        name="email_agent",
        keywords=["email", "send", "mail", "message"],
    )

    assistant = Agent(
        name="assistant",
        sub_agents=[searcher, file_handler, calculator, email_agent],
    )

    print("\n2. Testing various tasks with keywords...")

    tasks = [
        "search for Python best practices",
        "look up the documentation",
        "calculate monthly revenue",
        "send an email to John",
        "browse the website",
        "read the config file",
        "what is the weather?",  # No match - handled by main
    ]

    for task in tasks:
        matched = assistant._find_sub_agent_for_task(task)
        agent_name = matched.name if matched else "main agent"
        print(f"   '{task}' -> {agent_name}")


async def demo_depth_tracking():
    """Demonstrate depth tracking in nested agents."""
    print("\n" + "=" * 50)
    print("Depth Tracking Demo")
    print("=" * 50)

    print("\n1. Creating nested hierarchy...")

    level3 = Agent(name="worker_l3", current_depth=3)
    level2 = Agent(name="worker_l2", current_depth=2, sub_agents=[level3])
    level1 = Agent(name="worker_l1", current_depth=1, sub_agents=[level2])

    print(f"   level1 (depth={level1.current_depth})")
    print(f"    -> level2 (depth={level2.current_depth})")
    print(f"       -> level3 (depth={level3.current_depth})")

    print("\n2. Getting all agents...")
    all_agents = level1._get_all_sub_agents()
    print(f"   Found {len(all_agents)} agents: {list(all_agents.keys())}")

    print("\n3. Checking max depth enforcement...")
    print(f"   level1.max_depth: {level1.max_depth}")
    print(
        f"   level3.current_depth ({level3.current_depth}) >= max_depth ({level1.max_depth}): {level3.current_depth >= level1.max_depth}"
    )


async def main():
    print("=" * 50)
    print("TINYCUA SDK - Agent Hierarchy Demo")
    print("=" * 50)

    await demo_manual_delegation()
    await demo_delegation_with_llm()
    await demo_verbose_delegation()
    await demo_stream_sse()
    await demo_streaming_delegation()
    await demo_explicit_delegation()
    await demo_task_routing()
    await demo_depth_tracking()

    print("\n" + "=" * 50)
    print("All demos completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
