"""Response request models."""

from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A message in a conversation."""

    role: str
    content: str


class ToolDefinition(BaseModel):
    """Definition of a tool for the API."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_config(self) -> dict[str, Any]:
        """Return tool descriptor for API."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ResponseRequest(BaseModel):
    """Request to the Responses API."""

    model: str
    input: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[Any] = Field(default_factory=list)  # Accept ToolDefinition or dict
    temperature: float = 1.0
    max_tokens: int | None = None
    stream: bool = False
    session_id: str | None = None


__all__ = ["Message", "ToolDefinition", "ResponseRequest"]
