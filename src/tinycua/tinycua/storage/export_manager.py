"""Export manager for TinyCUA data migration."""

from __future__ import annotations

import io
import json
import logging
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tinycua.tui.agent_manager import AgentManager
from tinycua.tui.skills_manager import SkillsManager
from tinycua.storage.local_memory_store import LocalMemoryStore
from tinycua.storage.local_session_store import LocalSessionStore

logger = logging.getLogger(__name__)


@dataclass
class ExportOptions:
    """Export options."""

    include_sessions: bool = True
    include_agents: bool = True
    include_memory: bool = True
    include_skills: bool = True
    session_ids: list[str] | None = None
    agent_ids: list[str] | None = None


@dataclass
class ExportResult:
    """Export result."""

    success: bool
    output_path: Path | None = None
    items_exported: int = 0
    error: str | None = None


class ExportManager:
    """Manages data export to JSON."""

    EXPORT_VERSION = "1.0"

    def __init__(
        self,
        session_store: LocalSessionStore,
        agent_manager: AgentManager,
        memory_store: LocalMemoryStore,
        skills_manager: SkillsManager,
    ) -> None:
        """Initialize the export manager.

        Args:
            session_store: Local session store.
            agent_manager: Agent manager.
            memory_store: Local memory store.
            skills_manager: Skills manager.
        """
        self._session_store = session_store
        self._agent_manager = agent_manager
        self._memory_store = memory_store
        self._skills_manager = skills_manager

    def _collect_export_data(
        self, options: ExportOptions
    ) -> tuple[dict[str, Any], int]:
        """Collect export data based on options.

        Args:
            options: Export options.

        Returns:
            Tuple of (data dictionary, items exported count).
        """
        data: dict[str, Any] = {
            "version": self.EXPORT_VERSION,
            "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {},
        }
        items_exported = 0

        if options.include_sessions:
            sessions_data = self._export_sessions(options.session_ids)
            data["data"]["sessions"] = sessions_data
            items_exported += len(sessions_data)

        if options.include_agents:
            agents_data = self._export_agents(options.agent_ids)
            data["data"]["agents"] = agents_data
            items_exported += len(agents_data)

        if options.include_memory:
            memory_data = self._export_memory()
            data["data"]["memory"] = memory_data
            items_exported += len(memory_data)

        if options.include_skills:
            skills_data = self._export_skills()
            data["data"]["skills"] = skills_data
            items_exported += len(skills_data)

        return data, items_exported

    def export(
        self,
        output_path: Path,
        options: ExportOptions | None = None,
    ) -> ExportResult:
        """Export data to a JSON file.

        Args:
            output_path: Path to write the export file.
            options: Optional export options. Defaults to all enabled.

        Returns:
            ExportResult with success status and metadata.
        """
        options = options or ExportOptions()
        try:
            data, items_exported = self._collect_export_data(options)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            return ExportResult(
                success=True,
                output_path=output_path,
                items_exported=items_exported,
            )
        except Exception as e:
            logger.exception("Export failed")
            return ExportResult(success=False, error=str(e))

    def export_zip(
        self,
        output_path: Path,
        options: ExportOptions | None = None,
    ) -> ExportResult:
        """Export data as a ZIP archive containing JSON.

        Args:
            output_path: Path to write the ZIP file.
            options: Optional export options.

        Returns:
            ExportResult with success status and metadata.
        """
        options = options or ExportOptions()

        try:
            data, items_exported = self._collect_export_data(options)

            json_buffer = io.StringIO()
            json.dump(data, json_buffer, indent=2, default=str)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("export.json", json_buffer.getvalue())

            return ExportResult(
                success=True,
                output_path=output_path,
                items_exported=items_exported,
            )
        except Exception as e:
            logger.exception("ZIP export failed")
            return ExportResult(success=False, error=str(e))

    def _export_sessions(
        self, session_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Export sessions with messages.

        Args:
            session_ids: Optional list of specific session IDs to export.
                If None, exports all sessions.
        """
        sessions = self._session_store.list_sessions()
        sessions_data: list[dict[str, Any]] = []
        for session in sessions:
            if session_ids is not None and str(session.id) not in session_ids:
                continue
            messages = self._session_store.get_messages(session.id)
            sessions_data.append(
                {
                    "id": str(session.id),
                    "name": session.name,
                    "user_id": session.user_id,
                    "created_at": session.created_at.isoformat()
                    if session.created_at
                    else None,
                    "updated_at": session.updated_at.isoformat()
                    if session.updated_at
                    else None,
                    "metadata": session.metadata or {},
                    "messages": [
                        {
                            "id": str(msg.id),
                            "role": msg.role,
                            "content": msg.content,
                            "reasoning": msg.reasoning,
                            "turn_index": msg.turn_index,
                            "created_at": msg.created_at.isoformat()
                            if msg.created_at
                            else None,
                        }
                        for msg in messages
                    ],
                }
            )
        return sessions_data

    def _export_agents(
        self, agent_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Export agents.

        Args:
            agent_ids: Optional list of specific agent IDs to export.
                If None, exports all agents.
        """
        agents = self._agent_manager.list_agents()
        agents_data: list[dict[str, Any]] = []
        for agent in agents:
            if agent_ids is not None and str(agent.id) not in agent_ids:
                continue
            try:
                config_json = agent.config.to_json(redact_sensitive=True)
                if not isinstance(config_json, str):
                    raise TypeError(
                        f"Expected string from to_json, got {type(config_json).__name__}"
                    )
                config_dict = json.loads(config_json)
            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                logger.warning(
                    "Failed to serialize config for agent '%s': %s",
                    agent.name,
                    e,
                )
                config_dict = {"name": agent.name}
            agents_data.append(
                {
                    "id": str(agent.id),
                    "name": agent.name,
                    "config": config_dict,
                }
            )
        return agents_data

    def _export_memory(self) -> dict[str, Any]:
        """Export memory key-value pairs."""
        keys = self._memory_store.list_keys()
        memory_data: dict[str, Any] = {}
        for key in keys:
            value = self._memory_store.get(key)
            if value is not None:
                memory_data[key] = value
        return memory_data

    def _export_skills(self) -> list[dict[str, Any]]:
        """Export skills metadata."""
        skills = self._skills_manager.list_skills()
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
            }
            for skill in skills
        ]
