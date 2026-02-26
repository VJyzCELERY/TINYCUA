# Coding Standards

## Updated Rules
1. **Global Enforcements**:
   - **Code Style**: Ruff manages all linting and formatting tasks.
   - **Auto-Fix**: Ruff is configured to auto-fix all known issues (`fixable = ["ALL"]`).
   - **Absolute Imports**: Relative imports are disallowed (`ban-relative-imports = "all"`).

2. **Testing Flexibility**:
   - Test directories are exempt from docstring rules (`"**/tests/**" = ["D"]`).

3. **Logging Practices**:
   - Use `logging` for debugging and messaging across all subprojects.
   - Follow centralized logging rules as detailed in `docs/project_rules/logging_guidelines.md`.

---

## Docstring Guide
### Examples
```python
"""
This function converts temperature from Celsius to Fahrenheit.

Args:
    celsius (float): Temperature in Celsius.

Examples:
    # Convert 0 degrees C to Fahrenheit
    fahrenheit = to_fahrenheit(0)
"""

def to_fahrenheit(celsius: float) -> float:
    return celsius * 9 / 5 + 32
```
