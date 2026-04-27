"""Sync command mixin for ChatScreen decomposition."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tinycua.tui.widgets import OutputPanel

if TYPE_CHECKING:
    pass


class SyncCommandMixin:
    """Mixin providing sync-related command handlers."""

    async def _cmd_connect(self, args: str, output: OutputPanel) -> None:
        """Handle /connect command."""
        if not args:
            output.append_line(
                "[yellow]Usage: /connect <backend_url> [--api-key KEY][/yellow]"
            )
            return

        parts = args.split()
        backend_url = parts[0]
        api_key = None

        i = 1
        while i < len(parts):
            if parts[i] == "--api-key" and i + 1 < len(parts):
                api_key = parts[i + 1]
                i += 2
            else:
                i += 1

        try:
            self.app.init_remote(backend_url, api_key)
            output.append_line(
                f"[green]Initialized remote connection to {backend_url}[/green]"
            )
            output.append_line("[dim]Use /sync to sync with backend[/dim]")
        except (OSError, ValueError) as e:
            output.append_line(
                f"[red]Failed to initialize remote connection: {e}[/red]"
            )

    async def _cmd_sync(self, args: str, output: OutputPanel) -> None:
        """Handle /sync command."""
        remote_manager = self.app.get_remote_manager()
        sync_engine = self.app.get_sync_engine()
        if not remote_manager:
            output.append_line("[red]Remote not initialized. Use /connect first.[/red]")
            return
        if not remote_manager.is_connected:
            output.append_line(
                "[red]Not connected to remote. Use /connect first.[/red]"
            )
            return
        try:
            result = await sync_engine.push_all()
            if result.success:
                output.append_line(
                    f"[green]Sync successful: {result.items_synced} items synced[/green]"
                )
            else:
                output.append_line(f"[red]Sync failed: {result.errors}[/red]")
        except (OSError, ConnectionError, ValueError) as e:
            output.append_line(f"[red]Sync error: {e}[/red]")
