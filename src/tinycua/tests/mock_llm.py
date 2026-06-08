"""Shared mock LLM clients for unit and integration tests."""

from __future__ import annotations


class MockLLM:
    """Simple mock LLM that returns a fixed response.

    Tracks call count and last messages for assertions.

    Args:
        content: The fixed response content to return.
        response: Alias for ``content`` (backwards compatibility).
    """

    def __init__(
        self, content: str = "response", *, response: str | None = None
    ) -> None:
        self.content = response if response is not None else content
        self.call_count = 0
        self.last_messages: list[dict] | None = None

    def __call__(self, messages: list[dict], **kwargs: object) -> dict:  # noqa: ARG002
        self.call_count += 1
        self.last_messages = messages
        return {"role": "assistant", "content": self.content}


class MultiResponseMockLLM:
    """Mock LLM that returns responses sequentially from a list.

    Usage::

        mock = MultiResponseMockLLM(["analysis", "worker"])
        mock(messages)  # returns "analysis"
        mock(messages)  # returns "worker"

    If more calls are made than responses provided, returns the last response.

    Notes on response ordering:
    - The two-step decision process calls the LLM twice per input:
      first for analysis, then for classification.
    - Classification responses MUST exactly match RouteMap labels
      (exact string match, not fuzzy).
    - For multi-call scenarios, provide responses in order:
      [analysis_response, classification_response].

    Args:
        responses: List of response content strings to return in order.
    """

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.call_count = 0
        self.last_messages: list[dict] | None = None

    def __call__(self, messages: list[dict], **kwargs: object) -> dict:  # noqa: ARG002
        self.call_count += 1
        self.last_messages = messages
        idx = min(self.call_count - 1, len(self.responses) - 1)
        return {"role": "assistant", "content": self.responses[idx]}
