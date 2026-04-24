"""Import manager for TinyCUA data migration."""

from __future__ import annotations

import json
import logging
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, cast

from tinycua.tui.agent_manager import AgentManager
from tinycua.tui.skills_manager import SkillsManager
from tinycua.storage.local_memory_store import LocalMemoryStore
from tinycua.storage.local_session_store import LocalSessionStore

logger = logging.getLogger(__name__)


class ImportMode(Enum):
    """Import mode."""

    MERGE = "merge"
    REPLACE = "replace"


@dataclass
class ImportValidation:
    """Import validation result."""

    valid: bool
    version: str | None = None
    data_types: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    parsed_data: dict[str, Any] | None = None


@dataclass
class ImportResult:
    """Import result."""

    success: bool
    items_imported: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class ImportManager:
    """Manages data import from JSON."""

    SUPPORTED_VERSIONS = {"1.0"}
    MAX_IMPORT_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

    def __init__(
        self,
        session_store: LocalSessionStore,
        agent_manager: AgentManager,
        memory_store: LocalMemoryStore,
        skills_manager: SkillsManager,
    ) -> None:
        """Initialize the import manager.

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

    def validate(self, input_path: Path) -> ImportValidation:
        """Validate an import file.

        Args:
            input_path: Path to the import file.

        Returns:
            ImportValidation with validation results.
        """
        try:
            size = input_path.stat().st_size
            if size > self.MAX_IMPORT_FILE_SIZE_BYTES:
                max_mb = self.MAX_IMPORT_FILE_SIZE_BYTES / 1024 / 1024
                return ImportValidation(
                    valid=False,
                    errors=[
                        f"File too large ({size / 1024 / 1024:.1f} MB). "
                        f"Maximum: {max_mb:.0f} MB"
                    ],
                )
        except FileNotFoundError:
            return ImportValidation(
                valid=False, errors=[f"File not found: {input_path}"]
            )
        except OSError as e:
            return ImportValidation(valid=False, errors=[str(e)])

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return ImportValidation(valid=False, errors=[f"Invalid JSON: {e}"])
        except OSError as e:
            return ImportValidation(valid=False, errors=[str(e)])

        warnings: list[str] = []
        errors: list[str] = []

        version = data.get("version")
        if not version:
            errors.append("Missing version field")
        elif version not in self.SUPPORTED_VERSIONS:
            errors.append(f"Unsupported version: {version}")

        if "data" not in data:
            errors.append("Missing data section")
        elif not isinstance(data["data"], dict):
            errors.append("Data section must be an object")
        else:
            errors.extend(self._validate_data_schema(data["data"]))

        if isinstance(data.get("data"), dict):
            data_types = list(data["data"].keys())
            sessions = data["data"].get("sessions", [])
            if isinstance(sessions, list) and len(sessions) > 100:
                warnings.append("Large number of sessions may take time to import")
        else:
            data_types = []

        return ImportValidation(
            valid=len(errors) == 0,
            version=version,
            data_types=data_types,
            warnings=warnings,
            errors=errors,
            parsed_data=data,
        )

    def _validate_data_schema(self, data_section: dict[str, Any]) -> list[str]:
        """Validate the internal structure of data types.

        Args:
            data_section: The 'data' section of the import file.

        Returns:
            List of error messages.
        """
        errors: list[str] = []

        if "sessions" in data_section and not isinstance(
            data_section["sessions"], list
        ):
            errors.append("sessions must be a list")
        elif "sessions" in data_section:
            for idx, item in enumerate(data_section["sessions"]):
                if not isinstance(item, dict):
                    errors.append(f"sessions[{idx}] must be an object")
                    break

        if "agents" in data_section and not isinstance(data_section["agents"], list):
            errors.append("agents must be a list")
        elif "agents" in data_section:
            for idx, item in enumerate(data_section["agents"]):
                if not isinstance(item, dict):
                    errors.append(f"agents[{idx}] must be an object")
                    break
                if "name" not in item:
                    errors.append(f"agents[{idx}] is missing 'name'")
                    break

        if "memory" in data_section and not isinstance(data_section["memory"], dict):
            errors.append("memory must be an object")

        if "skills" in data_section and not isinstance(data_section["skills"], list):
            errors.append("skills must be a list")
        elif "skills" in data_section:
            for idx, item in enumerate(data_section["skills"]):
                if not isinstance(item, dict):
                    errors.append(f"skills[{idx}] must be an object")
                    break

        return errors

    def _execute_import(
        self,
        data_section: dict[str, Any],
        key: str,
        handler: Callable[[Any], tuple[int, list[str]]],
        _notify: Callable[[str], None],
    ) -> tuple[int, list[str]]:
        """Execute import for a single data type.

        Args:
            data_section: The data section from the import file.
            key: The data type key.
            handler: The import handler method.
            _notify: Progress callback wrapper.

        Returns:
            Tuple of (items imported, warnings).
        """
        if key not in data_section:
            return 0, []

        if key == "memory":
            _notify("Importing memory entries...")
        else:
            _notify(f"Importing {len(data_section[key])} {key}...")

        count, warns = handler(data_section[key])

        if key == "memory":
            _notify(f"Imported {count} memory entries")
        else:
            _notify(f"Imported {count} {key}")

        return count, warns

    def import_data(
        self,
        input_path: Path,
        mode: ImportMode = ImportMode.MERGE,
        progress_callback: Callable[[str], None] | None = None,
    ) -> ImportResult:
        """Import data from a JSON file.

        Args:
            input_path: Path to the import file.
            mode: Import mode (MERGE or REPLACE).
            progress_callback: Optional callback for progress updates.

        Returns:
            ImportResult with success status and metadata.
        """

        def _notify(msg: str) -> None:
            if progress_callback is not None:
                progress_callback(msg)

        validation = self.validate(input_path)
        if not validation.valid:
            return ImportResult(
                success=False,
                error="; ".join(validation.errors),
            )

        data = validation.parsed_data
        if data is None:
            try:
                with open(input_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except OSError as e:
                return ImportResult(success=False, error=str(e))

        backup_path: Path | None = None
        data_section = data.get("data", {})
        import_data_types = list(data_section.keys())
        try:
            if mode == ImportMode.REPLACE:
                _notify("Creating backup of existing data...")
                backup_path = self._backup_existing_data()
                _notify("Clearing existing data...")
                self._clear_existing_data(import_data_types)

            items_imported = 0
            warnings: list[str] = []

            for key, handler in [
                ("sessions", self._import_sessions),
                ("agents", self._import_agents),
                ("memory", self._import_memory),
                ("skills", self._import_skills),
            ]:
                count, warns = self._execute_import(
                    data_section,
                    key,
                    cast(Callable[[Any], tuple[int, list[str]]], handler),
                    _notify,
                )
                items_imported += count
                warnings.extend(warns)

            if backup_path is not None and backup_path.exists():
                try:
                    backup_path.unlink(missing_ok=True)
                except OSError as e:
                    logger.warning("Failed to remove backup file %s: %s", backup_path, e)

            return ImportResult(
                success=True,
                items_imported=items_imported,
                warnings=warnings,
            )
        except Exception as e:
            logger.exception("Import failed")
            if backup_path is not None and mode == ImportMode.REPLACE:
                restore_ok = self._restore_from_backup(backup_path)
                backup_path.unlink(missing_ok=True)
                if restore_ok:
                    return ImportResult(
                        success=False,
                        error=f"Import failed and existing data was restored: {e}",
                    )
                return ImportResult(
                    success=False,
                    error=(
                        f"Import failed and data restoration also failed. "
                        f"Data may be lost: {e}"
                    ),
                )
            return ImportResult(success=False, error=str(e))

    def import_zip(
        self,
        input_path: Path,
        mode: ImportMode = ImportMode.MERGE,
        progress_callback: Callable[[str], None] | None = None,
    ) -> ImportResult:
        """Import data from a ZIP archive containing a JSON export.

        Args:
            input_path: Path to the ZIP file.
            mode: Import mode (MERGE or REPLACE).
            progress_callback: Optional callback for progress updates.

        Returns:
            ImportResult with success status and metadata.
        """
        try:
            with zipfile.ZipFile(input_path, "r") as zf:
                namelist = zf.namelist()
                json_files = [n for n in namelist if n.endswith(".json")]
                if not json_files:
                    return ImportResult(
                        success=False,
                        error="No JSON file found in ZIP archive",
                    )
                # Look specifically for export.json; reject nested ZIPs
                preferred_names = ["export.json", "manifest.json"]
                json_name = None
                for name in preferred_names:
                    if name in json_files:
                        json_name = name
                        break
                if json_name is None:
                    json_name = json_files[0]

                # ZIP bomb / extraction safety checks
                for info in zf.infolist():
                    if info.filename.endswith(".zip"):
                        return ImportResult(
                            success=False,
                            error="Nested ZIP files are not allowed",
                        )
                    if info.file_size > 0:
                        ratio = info.file_size / max(info.compress_size, 1)
                        if ratio > 100:
                            return ImportResult(
                                success=False,
                                error="Suspicious compression ratio detected",
                            )
                    if info.file_size > self.MAX_IMPORT_FILE_SIZE_BYTES:
                        return ImportResult(
                            success=False,
                            error=f"ZIP member too large: {info.filename}",
                        )

                with tempfile.TemporaryDirectory() as tmpdir:
                    extract_path = Path(tmpdir) / json_name
                    zf.extract(json_name, tmpdir)
                    return self.import_data(
                        extract_path,
                        mode=mode,
                        progress_callback=progress_callback,
                    )
        except zipfile.BadZipFile:
            return ImportResult(success=False, error="Invalid or corrupted ZIP file")
        except OSError as e:
            return ImportResult(success=False, error=str(e))

    def _backup_existing_data(self) -> Path:
        """Backup existing data to a temporary JSON file before REPLACE.

        Returns:
            Path to the backup file.
        """
        from tinycua.storage.export_manager import ExportManager

        backup_dir = Path(tempfile.gettempdir()) / "tinycua_import_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_dir.chmod(0o700)
        backup_path = backup_dir / f"backup-{uuid.uuid4()}.json"

        exporter = ExportManager(
            self._session_store,
            self._agent_manager,
            self._memory_store,
            self._skills_manager,
        )
        result = exporter.export(backup_path)
        if not result.success:
            raise RuntimeError(f"Failed to backup existing data: {result.error}")
        return backup_path

    def _restore_from_backup(self, backup_path: Path) -> bool:
        """Restore data from a backup file after failed REPLACE import.

        Args:
            backup_path: Path to the backup JSON file.

        Returns:
            True if restoration succeeded, False otherwise.
        """
        try:
            self._clear_existing_data()
            result = self.import_data(backup_path, mode=ImportMode.REPLACE)
            if not result.success:
                logger.error("Backup restoration import failed: %s", result.error)
                return False
            logger.info("Restored existing data from backup")
            return True
        except Exception:
            logger.exception("Failed to restore from backup")
            return False

    def _clear_existing_data(self, data_types: list[str] | None = None) -> None:
        """Clear existing data before replace import.

        Args:
            data_types: List of data types present in the import file.
                If None or empty, clears all data types.
        """
        data_types = data_types or []
        clear_all = not data_types
        if clear_all or "sessions" in data_types:
            for session in self._session_store.list_sessions():
                self._session_store.delete_session(session.id)
        if clear_all or "agents" in data_types:
            for agent in self._agent_manager.list_agents():
                self._agent_manager.delete_agent(agent.id)
        if clear_all or "memory" in data_types:
            self._memory_store.clear()

    def _import_sessions(
        self, sessions_data: list[dict[str, Any]]
    ) -> tuple[int, list[str]]:
        """Import sessions and their messages.

        Returns:
            Tuple of (items imported, warnings).
        """
        items_imported = 0
        warnings: list[str] = []

        for session_data in sessions_data:
            try:
                name = session_data.get("name", "Imported Session")
                user_id = session_data.get("user_id")
                session_id_str = session_data.get("id")
                session_id = None
                if session_id_str:
                    try:
                        session_id = uuid.UUID(session_id_str)
                    except ValueError:
                        pass

                created_session = self._session_store.create_session(
                    name=name,
                    user_id=user_id,
                    session_id=session_id,
                )
                if created_session is None:
                    warnings.append(f"Failed to create session: {name}")
                    continue

                for msg in session_data.get("messages", []):
                    self._session_store.add_message(
                        session_id=created_session.id,
                        role=msg.get("role", "user"),
                        content=msg.get("content", ""),
                        reasoning=msg.get("reasoning"),
                    )

                items_imported += 1
            except Exception as e:
                warnings.append(f"Failed to import session: {e}")

        return items_imported, warnings

    def _import_agents(
        self, agents_data: list[dict[str, Any]]
    ) -> tuple[int, list[str]]:
        """Import agents.

        Returns:
            Tuple of (items imported, warnings).
        """
        items_imported = 0
        warnings: list[str] = []

        existing = self._agent_manager.list_agents()
        existing_names = {a.name for a in existing}

        for agent_data in agents_data:
            try:
                name = agent_data.get("name", "Imported Agent")
                config = agent_data.get("config", {})

                # Strip api_key to prevent credential leakage via tampered exports
                config.pop("api_key", None)

                if name in existing_names:
                    warnings.append(f"Agent '{name}' already exists, skipping")
                    continue

                self._agent_manager.create_agent(
                    name=name,
                    model=config.get("model", "gpt-5-nano"),
                    provider=config.get("provider", "openai"),
                    base_url=config.get("base_url"),
                    api_key=None,
                    system_prompt=config.get(
                        "system_prompt", "You are a helpful assistant."
                    ),
                    instructions=config.get("instructions", ""),
                    temperature=config.get("temperature", 1.0),
                    max_turns=config.get("max_turns"),
                )
                existing_names.add(name)
                items_imported += 1
            except Exception as e:
                warnings.append(
                    f"Failed to import agent '{agent_data.get('name')}': {e}"
                )

        return items_imported, warnings

    def _import_memory(self, memory_data: dict[str, Any]) -> tuple[int, list[str]]:
        """Import memory key-value pairs.

        Returns:
            Tuple of (items imported, warnings).
        """
        items_imported = 0
        warnings: list[str] = []

        for key, value in memory_data.items():
            try:
                self._memory_store.set(key, value)
                items_imported += 1
            except Exception as e:
                warnings.append(f"Failed to import memory key '{key}': {e}")

        return items_imported, warnings

    def _import_skills(
        self, skills_data: list[dict[str, Any]]
    ) -> tuple[int, list[str]]:
        """Import skills metadata.

        Returns:
            Tuple of (items imported, warnings).
        """
        items_imported = 0
        warnings: list[str] = []

        for skill_data in skills_data:
            name = skill_data.get("name", "Unknown")
            warnings.append(
                f"Skill '{name}' not imported; skill files must be installed manually",
            )

        return items_imported, warnings
