"""Calculator tool — main entry point.

This tool consists of multiple files:
  calculator.py   → @tool decorator and public interface
  helpers.py      → private math logic

The SDK loads the directory as a single tool package.
"""

from tinycua_sdk import tool

from .helpers import safe_eval_expr, SUPPORTED_OPS


@tool
def calculator(expression: str, precision: int = 4) -> str:
    """Evaluate a mathematical expression safely.

    Supports: +, -, *, /, //, %, **, abs, round

    Args:
        expression: A math expression like "(12 + 4) * 2".
        precision: Number of decimal places for floating-point results.
    """
    result = safe_eval_expr(expression)
    if isinstance(result, float):
        result = round(result, precision)
    return str(result)


@tool
def list_operations() -> list[str]:
    """Return the list of supported calculator operations."""
    return SUPPORTED_OPS
