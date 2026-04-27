"""Agent command mixin for ChatScreen decomposition."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinycua.constants import DEFAULT_MODEL, DEFAULT_PROVIDER, DEFAULT_SYSTEM_PROMPT
from tinycua.tui.widgets import OutputPanel

if TYPE_CHECKING:
    from tinycua.tui.agent_manager import AgentManager


class AgentCommandMixin:
    """Mixin providing agent-related command handlers."""

    async def _cmd_agents(self, args: str, output: OutputPanel) -> None:
        """Handle /agents command."""
        agents = self._agent_manager.list_agents()
        if agents:
            lines = ["[bold]Available agents:[/bold]"]
            current = self._agent_manager.get_current_agent()
            for agent in agents:
                marker = " *" if current and current.id == agent.id else ""
                lines.append(f"  {agent.name} ({agent.config.model}){marker}")
            output.append_line("\n".join(lines))
        else:
            output.append_line("No agents configured. Use /agent-create to add one.")

    async def _cmd_agent(self, args: str, output: OutputPanel) -> None:
        """Handle /agent command."""
        if not args:
            output.append_line("[yellow]Usage: /agent <name>[/yellow]")
            return
        agents = self._agent_manager.list_agents()
        target = None
        for agent in agents:
            if agent.name.lower() == args.lower():
                target = agent
                break
        if target:
            if self._agent_manager.set_current_agent(target.id):
                agent_instance = self._agent_manager.create_agent_instance(target)
                if agent_instance:
                    self.app.current_agent_instance = agent_instance
                    output.append_line(
                        f"[green]Switched to agent: {target.name}[/green]"
                    )
                    self._update_status_bar()
                else:
                    output.append_line("[red]Failed to create agent instance.[/red]")
            else:
                output.append_line("[red]Failed to switch agent.[/red]")
        else:
            output.append_line(f"[red]Agent '{args}' not found.[/red]")

    async def _cmd_agent_create(self, args: str, output: OutputPanel) -> None:
        """Handle /agent-create command."""
        if not args:
            output.append_line(
                f"[yellow]Usage: /agent-create <name> [--model {DEFAULT_MODEL}] [--provider {DEFAULT_PROVIDER}] [--base-url URL] [--api-key KEY] [--system-prompt PROMPT] [--instructions TEXT] [--temperature 1.0] [--max-turns N][/yellow]"
            )
            return

        parts = args.split()
        name = parts[0]

        model = DEFAULT_MODEL
        provider = DEFAULT_PROVIDER
        base_url = None
        api_key = None
        system_prompt = DEFAULT_SYSTEM_PROMPT
        instructions = ""
        temperature = 1.0
        max_turns = None

        i = 1
        while i < len(parts):
            if parts[i] == "--model" and i + 1 < len(parts):
                model = parts[i + 1]
                i += 2
            elif parts[i] == "--provider" and i + 1 < len(parts):
                provider = parts[i + 1]
                i += 2
            elif parts[i] == "--base-url" and i + 1 < len(parts):
                base_url = parts[i + 1]
                i += 2
            elif parts[i] == "--api-key" and i + 1 < len(parts):
                api_key = parts[i + 1]
                i += 2
            elif parts[i] == "--system-prompt" and i + 1 < len(parts):
                system_prompt = parts[i + 1]
                i += 2
            elif parts[i] == "--instructions" and i + 1 < len(parts):
                instructions = parts[i + 1]
                i += 2
            elif parts[i] == "--temperature" and i + 1 < len(parts):
                temperature = float(parts[i + 1])
                i += 2
            elif parts[i] == "--max-turns" and i + 1 < len(parts):
                max_turns = int(parts[i + 1])
                i += 2
            else:
                i += 1

        agent_info = self._agent_manager.create_agent(
            name,
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            system_prompt=system_prompt,
            instructions=instructions,
            temperature=temperature,
            max_turns=max_turns,
        )
        if agent_info:
            output.append_line(f"[green]Created agent: {agent_info.name}[/green]")
        else:
            output.append_line("[red]Failed to create agent.[/red]")
