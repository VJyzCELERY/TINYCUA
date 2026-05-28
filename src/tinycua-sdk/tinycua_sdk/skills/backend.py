"""Skill storage backend with DB-first + local fallback."""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from tinycua_sdk.skills.models import Skill

logger = logging.getLogger(__name__)


class SkillBackend(ABC):
    """Abstract base for skill storage backends."""

    @abstractmethod
    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        pass

    @abstractmethod
    def set(self, skill: Skill) -> dict[str, Any]:
        """Create or update a skill."""
        pass

    @abstractmethod
    def delete(self, name: str) -> dict[str, Any]:
        """Delete a skill."""
        pass

    @abstractmethod
    def list(self, category: str | None = None) -> list[Skill]:
        """List all skills, optionally filtered by category."""
        pass

    @abstractmethod
    def clear(self) -> dict[str, Any]:
        """Clear all skills."""
        pass


class LocalSkillBackend(SkillBackend):
    """Local skill storage using JSON files."""

    def __init__(self, storage_path: str | None = None):
        """Initialize local skill storage.

        Args:
            storage_path: Custom storage path. Defaults to ~/.tinycua/skills.json
        """
        self.storage_path = Path(storage_path or self._default_storage_path())
        self._ensure_storage_dir()

    def _default_storage_path(self) -> str:
        """Get default storage path."""
        home = Path.home()
        tinycua_dir = home / ".tinycua" / "skills.json"
        return str(tinycua_dir)

    def _ensure_storage_dir(self) -> None:
        """Ensure storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_skills(self) -> dict[str, dict]:
        """Read skills from file."""
        if not self.storage_path.exists():
            return {}
        with open(self.storage_path, "r") as f:
            return json.load(f)

    def _write_skills(self, skills: dict[str, dict]) -> None:
        """Write skills to file."""
        with open(self.storage_path, "w") as f:
            json.dump(skills, f, indent=2)

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        skills = self._read_skills()
        data = skills.get(name)
        if data is None:
            return None
        return self._data_to_skill(name, data)

    def set(self, skill: Skill) -> dict[str, Any]:
        """Create or update a skill."""
        skills = self._read_skills()
        skills[skill.name] = self._skill_to_data(skill)
        self._write_skills(skills)
        return {"success": True, "name": skill.name}

    def delete(self, name: str) -> dict[str, Any]:
        """Delete a skill."""
        skills = self._read_skills()
        if name in skills:
            del skills[name]
            self._write_skills(skills)
            return {"success": True, "name": name}
        return {"success": False, "name": name, "error": "Skill not found"}

    def list(self, category: str | None = None) -> list[Skill]:
        """List all skills."""
        skills = self._read_skills()
        result = []
        for name, data in skills.items():
            skill = self._data_to_skill(name, data)
            if category is None or skill.category == category:
                result.append(skill)
        return sorted(result, key=lambda s: s.name)

    def clear(self) -> dict[str, Any]:
        """Clear all skills."""
        self._write_skills({})
        return {"success": True}

    def _skill_to_data(self, skill: Skill) -> dict[str, Any]:
        """Convert Skill to dict for storage."""
        return {
            "description": skill.description,
            "category": skill.category,
            "instructions": skill.instructions,
            "tools": skill.tools,
            "dependencies": skill.dependencies,
            "metadata": skill.metadata,
            "is_active": getattr(skill, "is_active", True),
            "version": getattr(skill, "version", "1.0.0"),
        }

    def _data_to_skill(self, name: str, data: dict) -> Skill:
        """Convert dict to Skill."""
        return Skill(
            name=name,
            description=data.get("description", ""),
            category=data.get("category", "general"),
            instructions=data.get("instructions", ""),
            tools=data.get("tools", []),
            dependencies=data.get("dependencies", []),
            metadata=data.get("metadata", {}),
        )


class RemoteSkillBackend(SkillBackend):
    """Remote skill storage via backend API."""

    def __init__(self, backend_url: str, api_key: str | None = None):
        """Initialize remote skill backend.

        Args:
            backend_url: URL of the backend API
            api_key: Optional API key for authentication
        """
        self.backend_url = backend_url.rstrip("/")
        self.api_key = api_key
        self._available = True

    def _check_available(self) -> bool:
        """Check if backend is available."""
        import httpx

        try:
            response = httpx.get(f"{self.backend_url}/health", timeout=2)
            return response.status_code == 200
        except (httpx.HTTPError, OSError, ValueError):
            return False

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        import httpx

        try:
            response = httpx.get(
                f"{self.backend_url}/api/v1/skills/{name}",
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                return self._data_to_skill(name, data)
            return None
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Remote skill storage unavailable: %s", e)
            self._available = False
            raise

    def set(self, skill: Skill) -> dict[str, Any]:
        """Create or update a skill."""
        import httpx

        try:
            response = httpx.post(
                f"{self.backend_url}/api/v1/skills",
                json={
                    "name": skill.name,
                    "description": skill.description,
                    "category": skill.category,
                    "instructions": skill.instructions,
                    "tools": skill.tools,
                    "dependencies": skill.dependencies,
                    "metadata": skill.metadata,
                },
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code in (200, 201):
                return response.json()
            return {"success": False, "error": f"Status {response.status_code}"}
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Remote skill storage unavailable: %s", e)
            self._available = False
            raise

    def delete(self, name: str) -> dict[str, Any]:
        """Delete a skill."""
        import httpx

        try:
            response = httpx.delete(
                f"{self.backend_url}/api/v1/skills/{name}",
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code in (200, 204):
                return {"success": True, "name": name}
            return {"success": False, "error": f"Status {response.status_code}"}
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Remote skill storage unavailable: %s", e)
            self._available = False
            raise

    def list(self, category: str | None = None) -> list[Skill]:
        """List all skills."""
        import httpx

        try:
            params = {}
            if category:
                params["category"] = category
            response = httpx.get(
                f"{self.backend_url}/api/v1/skills",
                headers=self._get_headers(),
                params=params,
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                return [
                    self._data_to_skill(item["name"], item)
                    for item in data
                ]
            return []
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Remote skill storage unavailable: %s", e)
            self._available = False
            raise

    def clear(self) -> dict[str, Any]:
        """Clear all skills (admin only)."""
        import httpx

        try:
            response = httpx.delete(
                f"{self.backend_url}/api/v1/skills",
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code in (200, 204):
                return {"success": True}
            return {"success": False, "error": f"Status {response.status_code}"}
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Remote skill storage unavailable: %s", e)
            self._available = False
            raise

    def _data_to_skill(self, name: str, data: dict) -> Skill:
        """Convert API response to Skill."""
        return Skill(
            name=name,
            description=data.get("description", ""),
            category=data.get("category", "general"),
            instructions=data.get("instructions", ""),
            tools=data.get("tools", []),
            dependencies=data.get("dependencies", []),
            metadata=data.get("metadata", {}),
        )


class HybridSkillBackend(SkillBackend):
    """Skill backend that tries remote first, falls back to local."""

    def __init__(
        self,
        backend_url: str | None = None,
        api_key: str | None = None,
        local_storage_path: str | None = None,
    ):
        """Initialize hybrid skill backend.

        Args:
            backend_url: URL of the backend API (optional)
            api_key: Optional API key for authentication
            local_storage_path: Fallback local storage path
        """
        self._remote: RemoteSkillBackend | None = None
        self._local = LocalSkillBackend(local_storage_path)
        self._backend_url = backend_url
        self._api_key = api_key

        if backend_url:
            try:
                self._remote = RemoteSkillBackend(backend_url, api_key)
            except (httpx.HTTPError, OSError, ValueError):
                self._remote = None

    def _get_backend(self) -> SkillBackend:
        """Get the active backend (remote or local)."""
        if self._remote is not None:
            try:
                self._remote.list()  # Health check
                return self._remote
            except (httpx.HTTPError, OSError, ValueError):
                pass
        return self._local

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        backend = self._get_backend()
        return backend.get(name)

    def set(self, skill: Skill) -> dict[str, Any]:
        """Create or update a skill."""
        backend = self._get_backend()
        return backend.set(skill)

    def delete(self, name: str) -> dict[str, Any]:
        """Delete a skill."""
        backend = self._get_backend()
        return backend.delete(name)

    def list(self, category: str | None = None) -> list[Skill]:
        """List all skills."""
        backend = self._get_backend()
        return backend.list(category)

    def clear(self) -> dict[str, Any]:
        """Clear all skills."""
        backend = self._get_backend()
        return backend.clear()


def get_skill_backend(
    backend_url: str | None = None,
    api_key: str | None = None,
    local_only: bool = False,
) -> SkillBackend:
    """Get appropriate skill backend.

    Args:
        backend_url: URL of the backend API
        api_key: Optional API key
        local_only: If True, only use local storage

    Returns:
        SkillBackend instance
    """
    if local_only or not backend_url:
        return LocalSkillBackend()

    return HybridSkillBackend(backend_url, api_key)


__all__ = [
    "SkillBackend",
    "LocalSkillBackend",
    "RemoteSkillBackend",
    "HybridSkillBackend",
    "get_skill_backend",
]