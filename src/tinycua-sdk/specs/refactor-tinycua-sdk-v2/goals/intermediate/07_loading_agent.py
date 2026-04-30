"""07 - Loading Agent

Shows how to reconstruct an Agent from a JSON or YAML configuration file.
"""

import asyncio

from tinycua_sdk import Agent


async def main() -> None:
    # -----------------------------------------------------------------------
    # 1. Load from JSON file
    # -----------------------------------------------------------------------
    agent_json = Agent.from_json_file("exported_agent.json")
    print("Loaded from JSON:", agent_json.name)
    print("Model:", agent_json.llm_model.model_name)
    print("Tools:", [t.name for t in agent_json.tools])
    print("Skills:", [s.name for s in agent_json.skills])

    # -----------------------------------------------------------------------
    # 2. Load from YAML file
    # -----------------------------------------------------------------------
    agent_yaml = Agent.from_yaml_file("exported_agent.yaml")
    print("\nLoaded from YAML:", agent_yaml.name)

    # -----------------------------------------------------------------------
    # 3. Load from an in-memory dict
    # -----------------------------------------------------------------------
    config = {
        "name": "dynamic_agent",
        "instructions": "You are a dynamic agent created from a dict.",
        "llm_model": {
            "provider": "openai-compatible",
            "model_name": "qwen-2.5-7b",
            "base_url": "http://localhost:1234/v1",
            "temperature": 0.5,
        },
        "tools": [],
        "skills": [],
    }
    agent_dict = Agent.from_dict(config)
    print("\nLoaded from dict:", agent_dict.name)

    # -----------------------------------------------------------------------
    # 4. Run the loaded agent
    # -----------------------------------------------------------------------
    response = await agent_json.run("What is 7 * 8?")
    print("\nResponse:", response)


if __name__ == "__main__":
    asyncio.run(main())
