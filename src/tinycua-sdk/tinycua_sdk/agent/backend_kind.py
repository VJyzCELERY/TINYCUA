"""Backend configuration value object."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class BackendKind(str, Enum):
    """Where the agent should run."""

    LOCAL = "local"
    REMOTE = "remote"


class BackendConfig(BaseModel):
    """Immutable backend configuration.

    Pure value object — no I/O, no persistence methods.
    """

    model_config = ConfigDict(frozen=True)

    kind: BackendKind = BackendKind.LOCAL
    url: str | None = None
    api_key: SecretStr = SecretStr("")
    headers: dict[str, str] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackendConfig":
        """Deserialize from plain dict."""
        return cls(**data)
