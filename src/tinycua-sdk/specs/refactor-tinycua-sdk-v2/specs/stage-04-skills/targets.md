# Stage 4: Skills & Composition — Targets

## Purpose
Verify skills inject instructions into the system prompt and agents can use tools + skills together. Uses a real or mock LLM server.

---

### Target 4.1: Single Skill Instruction Injection

**File:** `targets/01_single_skill.py`

```python
"""Target 4.1: Verify agent with one skill includes its instructions."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "unsloth/qwen3.6-35b-a3b"


async def main():
    coding_skill = Skill(
        name="python_expert",
        description="Write idiomatic Python code.",
        instructions=(
            "When writing Python code, follow PEP 8, use type hints, "
            "prefer dataclasses over raw dicts."
        ),
    )

    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
        skills=[coding_skill],
    )

    response = await a.run("Write a hello world function.", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/01_single_skill_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 4.2: Multiple Skills Injected in Order

**File:** `targets/02_multiple_skills.py`

```python
"""Target 4.2: Verify multiple skills inject instructions in registration order."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "unsloth/qwen3.6-35b-a3b"


async def main():
    skill_a = Skill(name="s1", description="First", instructions="Instruction A.")
    skill_b = Skill(name="s2", description="Second", instructions="Instruction B.")

    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
        skills=[skill_a, skill_b],
    )

    response = await a.run("Hello.", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/02_multiple_skills_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 4.3: Dynamic add_skills After Creation

**File:** `targets/03_dynamic_add_skills.py`

```python
"""Target 4.3: Verify skills added after creation work on next run."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "unsloth/qwen3.6-35b-a3b"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    docs_skill = Skill(
        name="documentarian",
        description="Write clear documentation.",
        instructions="Use Google-style docstrings and add a usage example.",
    )
    a.add_skills(docs_skill)

    response = await a.run("Now document that function.", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/03_dynamic_add_skills_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 4.4: Combined Tools and Skills

**File:** `targets/04_combined_tools_and_skills.py`

```python
"""Target 4.4: Verify agent with both tools and skills works."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill, tool

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "unsloth/qwen3.6-35b-a3b"


@tool
def web_search(query: str) -> str:
    """Search the web for current information."""
    return f"[Search results for: {query}]"


research_skill = Skill(
    name="web_research",
    description="Research topics on the web.",
    instructions=(
        "Always verify facts with web_search before answering. "
        "Cite the sources you used."
    ),
)


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
        tools=[web_search],
        skills=[research_skill],
        instructions="You are a research assistant.",
    )

    response = await a.run("What is the latest version of FastAPI?", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/04_combined_tools_and_skills_expected-output.txt` → `Response: <any string>` (must not raise)
