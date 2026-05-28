"""Low-level HTTP wrapper for the http_client tool."""


import requests


def http_get(url: str, timeout: int = 30) -> str:
    """Perform a GET request and return text content."""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text[:2000]  # Truncate to keep context window sane


def http_post(url: str, json: dict | None = None, timeout: int = 30) -> str:
    """Perform a POST request with JSON body and return text content."""
    resp = requests.post(url, json=json, timeout=timeout)
    resp.raise_for_status()
    return resp.text[:2000]
