"""01 - Tool Creation

Shows how to create tools using the @tool decorator and the Tool class.
Tools are plain Python functions annotated with a schema that the LLM can call.
"""

from tinycua_sdk import Tool, tool

# ---------------------------------------------------------------------------
# 1. Using the @tool decorator (recommended)
# ---------------------------------------------------------------------------
@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    # ToolExecutor runs this in a subprocess by default for safety
    return str(eval(expression, {"__builtins__": {}}, {}))


@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Fetch the current weather for a city.

    Args:
        city: Name of the city (e.g., "Tokyo").
        unit: Temperature unit — "celsius" or "fahrenheit".
    """
    # In a real tool this would call a weather API
    return f"The weather in {city} is 22°{unit[0].upper()}."


# ---------------------------------------------------------------------------
# 2. Inspecting the generated schema
# ---------------------------------------------------------------------------
print("calculator schema:", calculator.to_config())
# {
#   "type": "function",
#   "function": {
#     "name": "calculator",
#     "description": "Evaluate a mathematical expression safely.",
#     "parameters": {
#       "type": "object",
#       "properties": {
#         "expression": {"type": "string"}
#       },
#       "required": ["expression"]
#     }
#   }
# }

# ---------------------------------------------------------------------------
# 3. Manual Tool construction (for dynamic / runtime tools)
# ---------------------------------------------------------------------------
dynamic_tool = Tool(
    name="reverse_string",
    description="Reverse a string.",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
        },
        "required": ["text"],
    },
)

# ---------------------------------------------------------------------------
# 4. Tool with dependencies metadata
# ---------------------------------------------------------------------------
@tool(dependencies=["requests"])
def fetch_url(url: str) -> str:
    """Fetch the content of a URL."""
    import requests

    resp = requests.get(url, timeout=30)
    return resp.text[:1000]


if __name__ == "__main__":
    print("Tools created:")
    for t in (calculator, get_weather, dynamic_tool, fetch_url):
        print(f"  - {t.name}: {t.description}")
