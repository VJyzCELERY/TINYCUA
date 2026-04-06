"""Agent CLI commands for creating and managing agents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from tinycua_sdk.agent.config import AgentConfig
from tinycua_sdk.agent.loader import AgentLoader, AgentNotFoundError, AgentParseError
from tinycua_sdk.agent.templates import (
    apply_template_overrides,
    get_template,
    list_templates,
)

console = Console()


def _validate_agent_path(path: Path) -> Path:
    """Validate path to prevent directory traversal attacks.

    Args:
        path: Path to validate

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path attempts directory traversal
    """
    # Resolve to absolute path
    resolved = path.expanduser().resolve()

    # Check for directory traversal attempts
    # Check if path tries to escape to parent directories
    original_str = str(path)
    if ".." in original_str:
        raise ValueError("Invalid path - directory traversal not allowed")

    return resolved


def _load_override_file(path: Path) -> dict:
    """Load override values from JSON or YAML file.

    Args:
        path: Path to override file

    Returns:
        Dictionary of override values

    Raises:
        ValueError: If file not found or invalid format
    """
    if not path.exists():
        raise ValueError(f"Override file not found: {path}")

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"Override file is empty: {path}")

    if path.suffix == ".json":
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse override file: {e}") from e
    elif path.suffix in (".yaml", ".yml"):
        try:
            return yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse override file: {e}") from e
    else:
        raise ValueError(
            f"Unsupported override file format. Use .json or .yaml/.yml: {path}"
        )


def _build_cli_overrides(args: argparse.Namespace) -> dict:
    """Build CLI overrides from command line arguments.

    Args:
        args: Parsed CLI arguments

    Returns:
        Dictionary of CLI overrides
    """
    cli_overrides = {}
    if args.model:
        cli_overrides["model"] = args.model
    if args.provider:
        cli_overrides["provider"] = args.provider
    if args.tools:
        cli_overrides["tools"] = [t.strip() for t in args.tools.split(",")]
    if args.skills:
        cli_overrides["skills"] = [s.strip() for s in args.skills.split(",")]
    if args.loop:
        cli_overrides["loop"] = args.loop
    if args.temperature is not None:
        cli_overrides["temperature"] = args.temperature
    return cli_overrides


async def cmd_agent_create(args: argparse.Namespace) -> int:
    """Create agent from AGENT.md or template.

    Args:
        args: Parsed CLI arguments with:
            - path: Optional path to AGENT.md file
            - template: Optional template name
            - model: Optional model override
            - provider: Optional provider override
            - tools: Optional tools override (comma-separated)
            - skills: Optional skills override (comma-separated)
            - loop: Optional loop type override
            - temperature: Optional temperature override
            - override_file: Optional path to JSON/YAML override file

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        # Determine if we're loading from file or template
        if args.path:
            return await _create_from_file(args)
        elif args.template:
            return await _create_from_template(args)
        else:
            console.print(
                "[red]Error: Specify either a path to AGENT.md or --template name[/red]"
            )
            console.print("Use 'tinycua agent create --help' for usage information")
            return 1

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


async def _create_from_file(args: argparse.Namespace) -> int:
    """Create agent from AGENT.md file.

    Args:
        args: Parsed CLI arguments

    Returns:
        Exit code (0 for success, 1 for error).
    """
    agent_path = Path(args.path)

    # Validate path
    try:
        agent_path = _validate_agent_path(agent_path)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1

    # Load agent configuration
    loader = AgentLoader()
    try:
        config = loader.load_from_markdown(agent_path)
    except AgentNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except AgentParseError as e:
        console.print(f"[red]Error: Failed to parse AGENT.md: {e}[/red]")
        return 1

    # Display success message
    console.print(
        f"[green]Agent '{config.name}' created successfully![/green]\n"
        f"  Model: {config.model}\n"
        f"  Provider: {config.provider}\n"
        f"  Tools: {len(config.tools)}"
    )
    return 0


async def _create_from_template(args: argparse.Namespace) -> int:
    """Create agent from template.

    Args:
        args: Parsed CLI arguments

    Returns:
        Exit code (0 for success, 1 for error).
    """
    # Load from template
    try:
        template = get_template(args.template)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1

    # Build overrides from file if provided
    file_overrides = {}
    if args.override_file:
        try:
            override_path = Path(args.override_file)
            file_overrides = _load_override_file(override_path)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            return 1

    # Build CLI overrides
    cli_overrides = _build_cli_overrides(args)

    # Merge overrides: file overrides first, then CLI overrides (CLI wins)
    merged_overrides = {**file_overrides, **cli_overrides}

    # Apply overrides to template
    final_template = apply_template_overrides(template, merged_overrides)

    # Display success message
    tool_count = len(final_template.get("tools", []))
    console.print(
        f"[green]Agent '{final_template['name']}' created successfully![/green]\n"
        f"  Model: {final_template.get('model')}\n"
        f"  Provider: {final_template.get('provider')}\n"
        f"  Tools: {tool_count}"
    )
    return 0


async def cmd_agent_templates(args: argparse.Namespace) -> int:
    """List available agent templates.

    Args:
        args: Parsed CLI arguments with:
            - verbose: Show detailed template info

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        templates = list_templates()

        if args.verbose:
            # Show detailed template information
            table = Table(title="Available Agent Templates (Detailed)")
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="white")
            table.add_column("Model", style="green")
            table.add_column("Provider", style="yellow")
            table.add_column("Tools", style="magenta")
            table.add_column("Loop", style="blue")

            for name in templates:
                template = get_template(name)
                tools_str = ", ".join(template.get("tools", []))
                table.add_row(
                    name,
                    template.get("description", ""),
                    template.get("model", ""),
                    template.get("provider", ""),
                    tools_str,
                    str(template.get("loop", "")),
                )
        else:
            # Show simple template list
            table = Table(title="Available Agent Templates")
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="white")

            for name in templates:
                template = get_template(name)
                table.add_row(name, template.get("description", ""))

        console.print(table)
        return 0

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


async def cmd_agent_info(args: argparse.Namespace) -> int:
    """Show agent configuration details.

    Args:
        args: Parsed CLI arguments with:
            - file: Optional path to AGENT.md
            - template: Optional template name

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        if not args.file and not args.template:
            console.print("[red]Error: Specify either --file or --template[/red]")
            console.print("Use 'tinycua agent info --help' for usage information")
            return 1

        if args.file:
            # Load from AGENT.md file
            agent_path = Path(args.file)

            # Validate path
            try:
                agent_path = _validate_agent_path(agent_path)
            except ValueError as e:
                console.print(f"[red]Error: {e}[/red]")
                return 1

            if not agent_path.exists():
                console.print(f"[red]Error: File not found: {agent_path}[/red]")
                return 1

            # Load agent configuration
            loader = AgentLoader()
            try:
                config = loader.load_from_markdown(agent_path)
            except AgentNotFoundError as e:
                console.print(f"[red]Error: {e}[/red]")
                return 1
            except AgentParseError as e:
                console.print(f"[red]Error: Failed to parse AGENT.md: {e}[/red]")
                return 1

            # Display agent configuration
            _display_agent_config(config)

        elif args.template:
            # Load from template
            try:
                template = get_template(args.template)
            except ValueError as e:
                console.print(f"[red]Error: {e}[/red]")
                return 1

            # Display template configuration
            _display_template_config(template)

        return 0

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


def _display_agent_config(config: AgentConfig) -> None:
    """Display agent configuration details.

    Args:
        config: AgentConfig instance
    """
    table = Table(title=f"Agent Configuration: {config.name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Name", config.name)
    table.add_row("Model", config.model)
    table.add_row("Provider", config.provider)
    if config.base_url:
        table.add_row("Base URL", config.base_url)

    tools_str = ", ".join(str(t) for t in config.tools) if config.tools else "None"
    table.add_row("Tools", tools_str)

    skills_str = ", ".join(config.skills) if config.skills else "None"
    table.add_row("Skills", skills_str)

    if config.loop:
        table.add_row("Loop", str(config.loop))

    table.add_row("Temperature", str(config.policy.temperature))
    table.add_row("Max Tool Calls", str(config.policy.max_tool_calls))

    console.print(table)


def _display_template_config(template: dict) -> None:
    """Display template configuration details.

    Args:
        template: Template dictionary
    """
    table = Table(title=f"Template Configuration: {template.get('name')}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Name", template.get("name", ""))
    table.add_row("Description", template.get("description", ""))
    table.add_row("Model", template.get("model", ""))
    table.add_row("Provider", template.get("provider", ""))
    if template.get("base_url"):
        table.add_row("Base URL", template.get("base_url"))

    tools_str = (
        ", ".join(template.get("tools", [])) if template.get("tools") else "None"
    )
    table.add_row("Tools", tools_str)

    skills_str = (
        ", ".join(template.get("skills", [])) if template.get("skills") else "None"
    )
    table.add_row("Skills", skills_str)

    if template.get("loop"):
        table.add_row("Loop", str(template.get("loop")))

    policy = template.get("policy", {})
    if policy:
        table.add_row("Temperature", str(policy.get("temperature", "")))
        table.add_row("Max Tool Calls", str(policy.get("max_tool_calls", "")))

    console.print(table)


__all__ = [
    "cmd_agent_create",
    "cmd_agent_templates",
    "cmd_agent_info",
    "_validate_agent_path",
    "_load_override_file",
]
