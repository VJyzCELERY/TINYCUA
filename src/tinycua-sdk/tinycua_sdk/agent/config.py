"""Agent configuration classes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.agent.loop import BaseLoop
from tinycua_sdk.security.approval import ApprovalWorkflow
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.tools.decorators import Tool


class AgentPolicy(BaseModel):
    """Policy for agent behavior."""

    model_config = ConfigDict(frozen=True)

    max_tool_calls: int = 10
    parallel_tool_calls: bool = True


class AgentConfig(BaseModel):
    """Configuration for an agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "assistant"
    instructions: str = ""
    llm_model: LanguageModel
    tools: list[Tool] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)  # type: ignore[type-arg]
    policy: AgentPolicy = Field(default_factory=AgentPolicy)
    metadata: dict[str, Any] = Field(default_factory=dict)
    loop: BaseLoop | None = None
    tool_permissions: dict[str, Literal["allow", "ask", "deny"]] = Field(
        default_factory=dict
    )
    approval_workflow: ApprovalWorkflow | None = None

    def to_config(self) -> dict[str, Any]:
        """Serialize agent config to dict.

        Note: The returned dict may contain non-JSON-serializable values
        (e.g., SecretStr from LanguageModel.api_key). Full JSON serialization
        support is planned for a later stage.
        """
        config: dict[str, Any] = {
            "name": self.name,
            "instructions": self.instructions,
            "llm_model": self.llm_model.to_dict(),
            "tools": [t.to_config() if isinstance(t, Tool) else t for t in self.tools],
            "skills": [
                s.to_dict() if hasattr(s, "to_dict") else s for s in self.skills
            ],
            "policy": self.policy.model_dump(),
            "metadata": self.metadata,
            "tool_permissions": self.tool_permissions,
        }
        return config

    def to_dict(self) -> dict[str, Any]:
        """Serialize agent config to plain dict (alias for to_config)."""
        return self.to_config()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        """Deserialize agent config from plain dict (alias for from_config)."""
        return cls.from_config(data)

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "AgentConfig":
        """Deserialize agent config from dict."""
        policy_data = data.get("policy", {})
        policy = AgentPolicy(
            max_tool_calls=policy_data.get("max_tool_calls", 10),
            parallel_tool_calls=policy_data.get("parallel_tool_calls", True),
        )

        llm_data = data.get("llm_model", {})
        llm_model = (
            LanguageModel.from_dict(llm_data)
            if isinstance(llm_data, dict)
            else LanguageModel()
        )

        tools_data = data.get("tools", [])
        tools = []
        for t in tools_data:
            if isinstance(t, Tool):
                tools.append(t)
            elif isinstance(t, dict):
                tools.append(_tool_from_config_dict(t))
            else:
                tools.append(t)

        skills_data = data.get("skills", [])
        skills = []
        for s in skills_data:
            if hasattr(s, "to_dict"):
                skills.append(s)
            elif isinstance(s, dict):
                from tinycua_sdk.skills.models import Skill

                skills.append(Skill.from_dict(s))
            else:
                skills.append(s)

        return cls(
            name=data.get("name", "assistant"),
            instructions=data.get("instructions", ""),
            llm_model=llm_model,
            tools=tools,
            skills=skills,
            policy=policy,
            metadata=data.get("metadata", {}),
            loop=data.get("loop"),
            tool_permissions=data.get("tool_permissions", {}),
            approval_workflow=data.get("approval_workflow"),
        )


def _tool_from_config_dict(data: dict[str, Any]) -> Tool:
    """Convert a tool configuration dict to a Tool."""
    return Tool.from_dict(data)


__all__ = ["AgentConfig", "AgentPolicy"]
