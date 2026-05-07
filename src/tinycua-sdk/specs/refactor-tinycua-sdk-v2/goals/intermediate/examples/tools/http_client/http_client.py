"""HTTP client tool — main entry point.

This tool shows how a tool can depend on third-party packages (requests)
and wrap them with a clean interface for the LLM.
"""

from tinycua_sdk import tool

from .client import http_get, http_post


@tool(dependencies=["requests"])
def fetch_url(url: str, timeout: int = 30) -> str:
    """Fetch the content of a URL via GET.

    Args:
        url: Full URL to fetch.
        timeout: Request timeout in seconds.
    """
    return http_get(url, timeout=timeout)


@tool(dependencies=["requests"])
def post_json(url: str, payload: dict, timeout: int = 30) -> str:
    """Send a JSON POST request.

    Args:
        url: Full URL to post to.
        payload: JSON-serializable dict.
        timeout: Request timeout in seconds.
    """
    return http_post(url, json=payload, timeout=timeout)
