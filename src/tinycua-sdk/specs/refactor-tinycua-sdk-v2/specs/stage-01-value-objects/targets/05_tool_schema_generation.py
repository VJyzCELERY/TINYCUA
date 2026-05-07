"""Target 1.5: Verify @tool generates correct OpenAI function schema."""

from tinycua_sdk import tool


@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Fetch weather for a city.

    Args:
        city: Name of the city (e.g., "Tokyo").
        unit: Temperature unit ("celsius" or "fahrenheit").
    """
    return f"sunny in {city}"


schema = get_weather.to_config()

assert schema["type"] == "function"
assert schema["function"]["name"] == "get_weather"
assert schema["function"]["description"] == "Fetch weather for a city."
assert "city" in schema["function"]["parameters"]["properties"]
assert "unit" in schema["function"]["parameters"]["properties"]
assert schema["function"]["parameters"]["required"] == ["city"]
print("PASS")
