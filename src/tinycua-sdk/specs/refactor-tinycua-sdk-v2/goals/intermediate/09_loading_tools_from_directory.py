"""09 - Loading Tools from Directory

Shows how the SDK discovers and loads tools from a directory structure.

Expected directory layout:
    tools/
    ├── calculator/
    │   ├── calculator.py       → @tool decorators (exported functions)
    │   └── helpers.py          → private code (NOT exported)
    ├── file_manager/
    │   ├── file_manager.py     → @tool decorators
    │   ├── validators.py       → private code
    │   └── permissions.py      → private code
    └── http_client/
        ├── http_client.py      → @tool decorators
        └── client.py           → private code

The SDK inspects each directory, finds all @tool-decorated functions,
and registers them as agent tools. Supporting files are ignored unless
explicitly imported by the tool module.
"""

import asyncio
from pathlib import Path

from tinycua_sdk import Agent, LanguageModel, Tool


async def main() -> None:
    # -----------------------------------------------------------------------
    # 1. Load ALL tools from a directory tree
    # -----------------------------------------------------------------------
    tools_dir = Path(__file__).parent / "examples" / "tools"
    all_tools: list[Tool] = Tool.load_directory(tools_dir)

    print(f"Loaded {len(all_tools)} tools from {tools_dir}:")
    for t in all_tools:
        print(f"  - {t.name}: {t.description}")

    # -----------------------------------------------------------------------
    # 2. Load tools from a single package
    # -----------------------------------------------------------------------
    calc_tools: list[Tool] = Tool.load_directory(tools_dir / "calculator")
    print(f"\nCalculator package has {len(calc_tools)} tools:")
    for t in calc_tools:
        print(f"  - {t.name}")

    # -----------------------------------------------------------------------
    # 3. Attach loaded tools to an agent
    # -----------------------------------------------------------------------
    agent = Agent(
        name="tool_powered_agent",
        instructions="You have access to file system and HTTP tools.",
        llm_model=LanguageModel(),
        tools=all_tools,
    )

    print(f"\nAgent '{agent.name}' has {len(agent.tools)} tools.")

    # -----------------------------------------------------------------------
    # 4. Use the agent
    # -----------------------------------------------------------------------
    response = await agent.run("What is 144 / 12?")
    print("Response:", response)


if __name__ == "__main__":
    asyncio.run(main())
