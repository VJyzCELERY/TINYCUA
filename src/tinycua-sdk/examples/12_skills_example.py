"""Skills Example - Demonstrates the Skills system in TINYCUA SDK.

This example shows how to:
1. Load skills from the filesystem
2. List available skills
3. View skill details
4. Use skills with an Agent

Prerequisites:
- OpenAI-compatible server running at http://localhost:1234/v1
- Model: qwen/qwen3.5-9b loaded
"""

import asyncio
import tempfile
from pathlib import Path

from tinycua_sdk import Agent
from tinycua_sdk.skills.loader import SkillLoader
from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.skills.tools import create_skills_list_tool, create_skill_view_tool
from tinycua_sdk.tools import tool


# =============================================================================
# Helper: Create a test skill directory
# =============================================================================

def create_test_skill(base_dir: Path, name: str, description: str, tools: list[str]) -> Path:
    """Create a test skill directory with SKILL.md."""
    skill_dir = base_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    skill_md = f"""---
name: {name}
description: {description}
category: test
tools: {tools}
dependencies: []
---

## Instructions
This is a test skill called {name}. {description}
"""
    
    (skill_dir / "SKILL.md").write_text(skill_md)
    return skill_dir


# =============================================================================
# Example 1: Basic Skill Discovery
# =============================================================================

async def example_skill_discovery():
    """Load and discover skills from a directory."""
    print("=" * 60)
    print("Example 1: Skill Discovery")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        
        # Create test skills
        create_test_skill(base_dir, "math-helper", "Helps with math calculations", ["calculator"])
        create_test_skill(base_dir, "web-search", "Searches the web", ["requests"])
        create_test_skill(base_dir, "data-analysis", "Analyzes data", ["pandas"])
        
        # Load skills
        loader = SkillLoader()
        skills = loader.discover_skills(base_dir)
        
        print(f"\nDiscovered {len(skills)} skills:")
        for skill in skills:
            print(f"  - {skill.name}: {skill.description}")
            print(f"    Category: {skill.category}")
            print(f"    Tools: {skill.tools}")


# =============================================================================
# Example 2: Skill Registry
# =============================================================================

async def example_skill_registry():
    """Use SkillRegistry to manage skills."""
    print("\n" + "=" * 60)
    print("Example 2: Skill Registry")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        
        # Create test skills
        create_test_skill(base_dir, "math-helper", "Helps with math", ["calculator"])
        create_test_skill(base_dir, "web-search", "Searches the web", ["requests"])
        
        # Load into registry
        registry = SkillRegistry()
        registry.load_skills_from_directory(base_dir)
        
        print(f"\nRegistered {registry.count} skills")
        
        # List all skills
        all_skills = registry.list_skills()
        print(f"List all: {[s.name for s in all_skills]}")
        
        # Filter by category
        test_skills = registry.list_skills(category="test")
        print(f"Test category: {[s.name for s in test_skills]}")
        
        # Get specific skill
        skill = registry.get_skill("math-helper")
        if skill:
            print(f"\nGot skill 'math-helper': {skill.description}")
        
        # Get categories
        categories = registry.get_categories()
        print(f"Categories: {categories}")


# =============================================================================
# Example 3: Skill Tools
# =============================================================================

async def example_skill_tools():
    """Use skills_list and skill_view tools."""
    print("\n" + "=" * 60)
    print("Example 3: Skill Tools")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        
        # Create test skills
        create_test_skill(base_dir, "math-helper", "Helps with math", ["calculator"])
        create_test_skill(base_dir, "web-search", "Searches the web", ["requests"])
        
        # Load into registry
        registry = SkillRegistry()
        registry.load_skills_from_directory(base_dir)
        
        # Create tools
        list_tool = create_skills_list_tool(registry)
        view_tool = create_skill_view_tool(registry)
        
        print("\nUsing skills_list tool:")
        result = list_tool.invoke()
        print(f"  Result: {result}")
        
        print("\nUsing skill_view tool for 'math-helper':")
        result = view_tool.invoke(skill_name="math-helper")
        print(f"  Result: {result}")


# =============================================================================
# Example 4: Skills with Agent
# =============================================================================

async def example_skills_with_agent():
    """Use skills parameter when creating an agent."""
    print("\n" + "=" * 60)
    print("Example 4: Skills with Agent")
    print("=" * 60)
    
    # Create an agent with skills parameter
    # Note: Skills are loaded at agent creation time
    agent = Agent(
        name="skillful-agent",
        instructions="You are a helpful assistant with special skills.",
        provider="openai-compatible",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234/v1",
        api_key="dummy",
        # skills=['math-helper', 'web-search'],  # Would load from ~/.tinycua/skills/
    )
    
    print(f"\nCreated agent: {agent.name}")
    print(f"Tools available: {[t.name for t in agent.tools]}")
    
    # Try a simple run (needs local server running)
    print("\nTesting agent run:")
    try:
        response = await agent.run("Say hello in one sentence.")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error (expected if local OpenAI-compatible server not running): {e}")


# =============================================================================
# Example 5: Skill Activation Logic
# =============================================================================

async def example_skill_activation():
    """Test skill activation conditions."""
    print("\n" + "=" * 60)
    print("Example 5: Skill Activation Logic")
    print("=" * 60)
    
    from tinycua_sdk.agent.skill_resolver import SkillActivator
    
    activator = SkillActivator()
    
    # Test platform activation
    skill_metadata = {
        "platforms": ["linux", "darwin"],
    }
    
    print("\nPlatform check (linux):")
    # This will vary based on actual platform
    print(f"  Should activate: {activator._check_platform(['linux', 'darwin'])}")
    
    # Test toolset requirements
    available_toolsets = {"web", "api"}
    available_tools = {"requests", "BeautifulSoup"}
    
    skill = type('Skill', (), {
        'metadata': {
            'requires_toolsets': ['web', 'api'],
            'requires_tools': ['requests'],
        }
    })()
    
    should_activate = activator.should_activate_skill(
        skill, available_toolsets, available_tools
    )
    print(f"\nWith requires_toolsets=['web','api'], requires_tools=['requests']:")
    print(f"  Available: {available_toolsets}, {available_tools}")
    print(f"  Should activate: {should_activate}")


# =============================================================================
# Main
# =============================================================================

async def main():
    """Run all examples."""
    print("TINYCUA SDK - Skills Examples")
    print("=" * 60)
    
    await example_skill_discovery()
    await example_skill_registry()
    await example_skill_tools()
    await example_skills_with_agent()
    await example_skill_activation()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())