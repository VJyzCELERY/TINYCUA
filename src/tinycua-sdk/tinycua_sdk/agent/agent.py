"""Agent with lifecycle convenience wrappers."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Literal, Union

import yaml

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.agent.loop import BaseLoop
from tinycua_sdk.models.attachment import ContentPart, FileAttachment

if TYPE_CHECKING:
    from tinycua_sdk.security.approval import ApprovalWorkflow
    from tinycua_sdk.tools.decorators import Tool
    from tinycua_sdk.skills.models import Skill


_CONFIG_ATTRS = frozenset(
    {
        "name",
        "instructions",
        "llm_model",
        "tools",
        "skills",
        "policy",
        "metadata",
        "loop",
        "approval_workflow",
        "cache_dir",
        "cache_max_entries",
        "session_cache_max_entries",
        "cache_namespace",
        "upload_timeout",
    }
)


class Agent(AgentExecutor):
    """Stateless, fully runnable agent class."""

    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        llm_model: LanguageModel | None = None,
        tools: list[Tool] | None = None,
        skills: list[Skill] | None = None,
        policy: AgentPolicy | None = None,
        metadata: dict | None = None,
        loop: BaseLoop | None = None,
        tool_permissions: dict[str, Literal["allow", "ask", "deny"]] | None = None,
        approval_workflow: Union[ApprovalWorkflow, list[ApprovalWorkflow], None] = None,
        cache_dir: str | None = None,
        cache_max_entries: int = 1000,
        session_cache_max_entries: int = 500,
        cache_namespace: str | None = None,
        upload_timeout: float = 30.0,
    ):
        config = AgentConfig(
            name=name,
            instructions=instructions,
            llm_model=llm_model or LanguageModel(),
            tools=tools or [],
            skills=skills or [],
            policy=policy or AgentPolicy(),
            metadata=metadata or {},
            loop=loop,
            tool_permissions=tool_permissions or {},
            approval_workflow=approval_workflow,
            cache_dir=(
                cache_dir
                if cache_dir is not None
                else os.environ.get("TINYCUA_CACHE_DIR")
            ),
            cache_max_entries=cache_max_entries,
            session_cache_max_entries=session_cache_max_entries,
            cache_namespace=cache_namespace,
            upload_timeout=upload_timeout,
        )

        super().__init__(config=config)

    def __getattr__(self, name: str) -> Any:
        """Delegate config attribute access."""
        if name in _CONFIG_ATTRS:
            return getattr(self.config, name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    @property
    def tool_permissions(self) -> dict[str, Literal["allow", "ask", "deny"]]:
        """Get tool permissions."""
        return self.config.tool_permissions

    @tool_permissions.setter
    def tool_permissions(
        self, value: dict[str, Literal["allow", "ask", "deny"]]
    ) -> None:
        """Set tool permissions."""
        self.config.tool_permissions = value

    @property
    def upload_cache_size(self) -> int:
        """Number of in-memory upload cache entries (for testing).

        Returns:
            The number of cached file-id entries in the upload session,
            or 0 if no upload session has been created yet.
        """
        client = self._get_llm_client()
        session = getattr(client, "_upload_session", None)
        return session.cache_size if session else 0

    def add_tools(self, tool_or_list: Tool | list[Tool]) -> None:
        """Append one or more tools to the agent.

        Args:
            tool_or_list: A single Tool or a list of Tools.
        """
        new_tools = tool_or_list if isinstance(tool_or_list, list) else [tool_or_list]
        existing_names = {t.name for t in self.config.tools}
        for t in new_tools:
            if t.name not in existing_names:
                self.config.tools.append(t)
                existing_names.add(t.name)

    def add_skills(self, skill_or_list: Skill | list[Skill]) -> None:
        """Append one or more skills to the agent.

        Args:
            skill_or_list: A single Skill or a list of Skills.
        """
        new_skills = (
            skill_or_list if isinstance(skill_or_list, list) else [skill_or_list]
        )
        existing_names = {s.name for s in self.config.skills}
        for s in new_skills:
            if s.name not in existing_names:
                self.config.skills.append(s)
                existing_names.add(s.name)

    async def run(
        self,
        query: str | list[ContentPart],
        messages: list[dict] | None = None,
        instructions: str | None = None,
        stream: bool = False,
        file_attachments: list[FileAttachment] | None = None,
    ) -> str | AsyncIterator[dict]:
        """Run the agent with a query, optionally including file attachments.

        Args:
            query: The user query — either a plain string or a list of
                ContentPart objects for multimodal input.
            messages: Optional message history to prepend.
            instructions: Optional instructions override.
            stream: If True, returns an async iterator of SDK-normalized
                stream events.
            file_attachments: Optional list of FileAttachment objects to
                include with the user message.

        Returns:
            Final response string when stream=False, or an async iterator
            of event dicts when streaming.

        Raises:
            TypeError: If query is neither str nor list[ContentPart], or if
                file_attachments contains non-FileAttachment items.
        """
        # Validate query type
        if isinstance(query, str):
            pass  # str queries are always valid
        elif isinstance(query, list):
            if not query:
                raise TypeError(
                    "query must not be an empty list; provide at least one "
                    "ContentPart or use a string query with file_attachments."
                )
            for i, item in enumerate(query):
                if not isinstance(item, ContentPart):
                    raise TypeError(
                        f"Each item in query list must be a ContentPart; "
                        f"item at index {i} is {type(item).__name__}."
                    )
        else:
            raise TypeError(
                f"query must be str or list[ContentPart], got {type(query).__name__}."
            )

        # Validate file_attachments
        if file_attachments is not None:
            for i, att in enumerate(file_attachments):
                if att is None or not isinstance(att, FileAttachment):
                    raise TypeError(
                        f"Each item in file_attachments must be a "
                        f"FileAttachment; item at index {i} is "
                        f"{type(att).__name__}."
                    )

        # Build user message dict
        user_msg: dict[str, Any]
        if isinstance(query, str):
            if file_attachments:
                user_msg = {
                    "role": "user",
                    "content": query,
                    "attachments": file_attachments,
                }
            else:
                user_msg = {"role": "user", "content": query}
        else:
            # query is list[ContentPart]
            if file_attachments:
                # Merge file_attachments as ContentPart(type="file") entries
                file_parts = [
                    ContentPart(type="file", file=a) for a in file_attachments
                ]
                merged = list(query) + file_parts
                user_msg = {"role": "user", "content": merged}
            else:
                user_msg = {"role": "user", "content": query}

        if not isinstance(stream, bool):
            raise TypeError(f"stream must be a bool, got {type(stream).__name__}")
        loop = self.config.loop or BaseLoop()
        msgs = (messages or []) + [user_msg]
        try:
            result = await loop.run(self, msgs, self.tools, instructions, stream=stream)
        finally:
            if not stream:
                self._cancelled = False
                self._cancel_event.clear()

        if not stream:
            return result
        assert isinstance(result, AsyncIterator), (
            "stream mode must return AsyncIterator"
        )
        return self._wrap_stream(result)

    async def _wrap_stream(
        self, gen: AsyncIterator[dict[str, Any]]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Pass through stream events and reset cancellation on completion."""
        try:
            async for event in gen:
                yield event
        finally:
            self._cancelled = False
            self._cancel_event.clear()
            if hasattr(gen, "aclose"):
                await gen.aclose()

    def to_config(self) -> dict[str, Any]:
        """Serialize agent to a configuration dict.

        Returns:
            Dictionary representation of the agent.
        """
        return self.config.to_config()

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Agent":
        """Create an agent from a configuration dict.

        Args:
            config: A configuration dictionary.

        Returns:
            A new Agent instance.
        """
        agent_config = AgentConfig.from_config(config)
        return cls(
            name=agent_config.name,
            instructions=agent_config.instructions,
            llm_model=agent_config.llm_model,
            tools=agent_config.tools,
            skills=agent_config.skills,
            policy=agent_config.policy,
            metadata=agent_config.metadata,
            loop=agent_config.loop,
            tool_permissions=agent_config.tool_permissions,
            approval_workflow=agent_config.approval_workflow,
            cache_dir=agent_config.cache_dir,
            cache_max_entries=agent_config.cache_max_entries,
            session_cache_max_entries=agent_config.session_cache_max_entries,
            cache_namespace=agent_config.cache_namespace,
            upload_timeout=agent_config.upload_timeout,
        )

    def to_json(self, indent: int = 2, redact_sensitive: bool = True) -> str:
        """Serialize agent to a JSON string.

        Args:
            indent: Number of spaces for indentation.
            redact_sensitive: If True, mask api_key as "***".

        Returns:
            JSON string representation of the agent.
        """
        config = self.to_config()
        self._apply_redaction(config, redact_sensitive)
        return json.dumps(config, indent=indent)

    def to_yaml(self, redact_sensitive: bool = True) -> str:
        """Serialize agent to a YAML string.

        Args:
            redact_sensitive: If True, mask api_key as "***".

        Returns:
            YAML string representation of the agent.
        """
        config = self.to_config()
        self._apply_redaction(config, redact_sensitive)
        return yaml.dump(config, default_flow_style=False)

    def _apply_redaction(self, config: dict[str, Any], redact: bool) -> None:
        """Apply or expose api_key in the config dict in-place.

        Args:
            config: The configuration dict to modify.
            redact: If True, set api_key to "***"; if False, expose the actual value.
        """
        llm_dict = config.get("llm_model", {})
        if redact:
            llm_dict["api_key"] = "***"
        else:
            llm_dict["api_key"] = self.config.llm_model.api_key.get_secret_value()

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "Agent":
        """Create an agent from a configuration dict.

        Args:
            config: A configuration dictionary.

        Returns:
            A new Agent instance.
        """
        return cls.from_config(config)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "Agent":
        """Create an agent from a JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            A new Agent instance.
        """
        if isinstance(path, str):
            path = Path(path)
        data = json.loads(path.read_text())
        return cls.from_dict(data)

    @classmethod
    def from_yaml_file(cls, path: str | Path) -> "Agent":
        """Create an agent from a YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            A new Agent instance.
        """
        if isinstance(path, str):
            path = Path(path)
        data = yaml.safe_load(path.read_text())
        return cls.from_dict(data)


__all__ = ["Agent"]
