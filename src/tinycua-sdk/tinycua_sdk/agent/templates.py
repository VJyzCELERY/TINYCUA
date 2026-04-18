"""Agent templates for quick agent creation."""

from typing import TypedDict


class AgentTemplate(TypedDict, total=False):
    """Template definition for an agent."""

    name: str
    description: str
    system_prompt: str
    model: str
    provider: str
    tools: list[str]
    skills: list[str]
    loop: str | dict
    policy: dict
    keywords: list[str]
    instructions: str
    base_url: str | None
    api_key: str | None
    strip_thinking: bool | list[str] | None
    max_depth: int
    sub_agents: list
    mode: str | None
    backend_url: str | None
    backend_api_key: str | None
    backend_headers: dict | None
    agent_id: str | None


# Pre-built templates
TEMPLATES: dict[str, AgentTemplate] = {
    "coder": {
        "name": "coder",
        "description": "Agent specialized in code generation, debugging, and technical tasks",
        "system_prompt": "You are an expert programmer. You excel at writing clean, efficient code. "
        "You analyze requirements carefully and provide well-structured solutions. "
        "You debug issues systematically and explain your reasoning clearly.",
        "model": "gpt-4o-mini",
        "provider": "openai",
        "tools": ["bash", "read_file", "write_file", "list_directory"],
        "skills": [],
        "loop": "default",
        "policy": {"max_tool_calls": 15, "temperature": 0.7},
        "keywords": ["code", "program", "debug", "implement", "fix"],
    },
    "researcher": {
        "name": "researcher",
        "description": "Agent specialized in research, information gathering, and analysis",
        "system_prompt": "You are a research assistant. You excel at finding accurate information, "
        "analyzing sources, and synthesizing findings. You provide well-organized "
        "summaries with proper citations.",
        "model": "gpt-4o-mini",
        "provider": "openai",
        "tools": ["search_web", "read_file", "visit_url"],
        "skills": [],
        "loop": "react",
        "policy": {"max_tool_calls": 10, "temperature": 0.5},
        "keywords": ["research", "find", "analyze", "investigate", "explain"],
    },
    "assistant": {
        "name": "assistant",
        "description": "General-purpose helpful assistant",
        "system_prompt": "You are a helpful, friendly assistant. You provide accurate information, "
        "answer questions clearly, and help users accomplish their tasks.",
        "model": "gpt-4o-mini",
        "provider": "openai",
        "tools": [],
        "skills": [],
        "loop": "default",
        "policy": {"max_tool_calls": 10, "temperature": 1.0},
        "keywords": ["help", "question", "assist", "general"],
    },
}


# Allowed template fields for override validation
ALLOWED_OVERRIDE_FIELDS = {
    "name",
    "system_prompt",
    "instructions",
    "model",
    "provider",
    "base_url",
    "api_key",
    "tools",
    "skills",
    "loop",
    "policy",
    "keywords",
    "strip_thinking",
    "max_depth",
    "sub_agents",
    # Additional fields for deployed agents
    "mode",
    "backend_url",
    "backend_api_key",
    "backend_headers",
    "agent_id",
}


def get_template(name: str) -> AgentTemplate:
    """Get template by name.

    Args:
        name: Template name (case-insensitive)

    Returns:
        Template definition dictionary

    Raises:
        ValueError: If template name is not found
    """
    normalized = name.lower()
    if normalized not in TEMPLATES:
        available = ", ".join(sorted(TEMPLATES.keys()))
        raise ValueError(
            f"Template '{name}' not found. Available templates: {available}"
        )
    return TEMPLATES[normalized].copy()


def list_templates() -> list[str]:
    """List all available template names.

    Returns:
        List of template names
    """
    return sorted(TEMPLATES.keys())


def template_exists(name: str) -> bool:
    """Check if template exists.

    Args:
        name: Template name (case-insensitive)

    Returns:
        True if template exists, False otherwise
    """
    return name.lower() in TEMPLATES


def validate_template(template: dict) -> None:
    """Validate template structure.

    Args:
        template: Template dictionary to validate

    Raises:
        ValueError: If template is invalid (missing required fields)
    """
    required_fields = ["name", "system_prompt"]
    for field in required_fields:
        if field not in template:
            raise ValueError(f"Template missing required field: {field}")


def apply_template_overrides(
    template: AgentTemplate,
    overrides: dict | None,
) -> AgentTemplate:
    """Apply overrides to template with validation.

    Args:
        template: Base template dictionary
        overrides: Override values (can include nested dicts)

    Returns:
        Merged template dictionary

    Raises:
        ValueError: If override contains unknown keys
    """
    if overrides is None:
        return template.copy()

    # Validate override keys
    unknown_keys = set(overrides.keys()) - ALLOWED_OVERRIDE_FIELDS
    if unknown_keys:
        raise ValueError(
            f"Invalid override keys: {', '.join(sorted(unknown_keys))}. "
            f"Allowed keys: {', '.join(sorted(ALLOWED_OVERRIDE_FIELDS))}"
        )

    result = template.copy()

    for key, value in overrides.items():
        if key == "policy" and isinstance(value, dict):
            # Deep merge policy
            result["policy"] = {**result.get("policy", {}), **value}
        elif key == "loop" and isinstance(value, dict):
            # Loop config - store as-is
            result["loop"] = value
        elif key == "tools" and isinstance(value, list):
            # Replace tools list
            result["tools"] = value
        elif key == "skills" and isinstance(value, list):
            # Replace skills list
            result["skills"] = value
        else:
            # Direct override (model, provider, etc.)
            result[key] = value

    return result


__all__ = [
    "AgentTemplate",
    "TEMPLATES",
    "get_template",
    "list_templates",
    "template_exists",
    "validate_template",
    "apply_template_overrides",
]
