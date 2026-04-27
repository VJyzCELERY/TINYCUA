"""Export/import command mixins for ChatScreen decomposition."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tinycua.storage import ExportManager, ExportOptions, ImportManager, ImportMode
from tinycua.tui.widgets import OutputPanel

if TYPE_CHECKING:
    from textual.widgets import Input


def parse_export_args(args: str) -> tuple[ExportOptions, Path, str]:
    """Parse /export command arguments.

    Args:
        args: Raw argument string.

    Returns:
        Tuple of (options, output_path, export_format).
    """
    include_sessions = True
    include_agents = True
    include_memory = True
    include_skills = True
    export_format = "json"
    output_path_str = ""

    parts = args.split()
    i = 0
    while i < len(parts):
        part = parts[i]
        if part == "--no-sessions":
            include_sessions = False
            i += 1
        elif part == "--no-agents":
            include_agents = False
            i += 1
        elif part == "--no-memory":
            include_memory = False
            i += 1
        elif part == "--no-skills":
            include_skills = False
            i += 1
        elif part == "--format" and i + 1 < len(parts):
            fmt = parts[i + 1].lower()
            if fmt in ("json", "zip"):
                export_format = fmt
            i += 2
        elif not output_path_str:
            output_path_str = part
            i += 1
        else:
            i += 1

    if not output_path_str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        ext = "zip" if export_format == "zip" else "json"
        output_path_str = str(
            Path.home() / ".tinycua" / f"export-{timestamp}.{ext}"
        )

    options = ExportOptions(
        include_sessions=include_sessions,
        include_agents=include_agents,
        include_memory=include_memory,
        include_skills=include_skills,
    )
    return options, Path(output_path_str), export_format


class ExportImportCommandMixin:
    """Mixin providing export and import command handlers."""

    async def _cmd_export(self, args: str, output: OutputPanel) -> None:
        """Handle the /export command."""
        if not args:
            from tinycua.tui.app import ExportScreen

            self.app.push_screen(
                ExportScreen(
                    session_manager=self._session_manager,
                    agent_manager=self._agent_manager,
                    memory_store=self.app.get_memory_store(),
                    skills_manager=self._skills_manager,
                )
            )
            return

        from tinycua.tui.app import ExportPreviewScreen, _validate_path

        options, output_path, export_format = parse_export_args(args)
        valid, error = _validate_path(output_path)
        if not valid:
            output.append_line(f"[red]Invalid export path: {error}[/red]")
            return

        memory_store = self.app.get_memory_store()
        self.app.push_screen(
            ExportPreviewScreen(
                session_store=self.app.get_session_store(),
                agent_manager=self._agent_manager,
                memory_store=memory_store,
                skills_manager=self._skills_manager,
                options=options,
                output_path=output_path,
                export_format=export_format,
            )
        )

    async def _cmd_import(self, args: str, output: OutputPanel) -> None:
        """Handle the /import command."""
        if not args:
            from tinycua.tui.app import ImportScreen

            self.app.push_screen(
                ImportScreen(
                    session_manager=self._session_manager,
                    agent_manager=self._agent_manager,
                    memory_store=self.app.get_memory_store(),
                    skills_manager=self._skills_manager,
                )
            )
            return

        from tinycua.tui.app import _validate_path

        parts = args.split()
        input_path = Path(parts[0])
        valid, error = _validate_path(input_path, must_exist=True)
        if not valid:
            output.append_line(f"[red]Invalid import path: {error}[/red]")
            return

        mode = ImportMode.MERGE

        i = 1
        while i < len(parts):
            if parts[i] == "--mode" and i + 1 < len(parts):
                mode_str = parts[i + 1].lower()
                if mode_str == "replace":
                    output.append_line(
                        "[red]Replace mode is not allowed via CLI. "
                        "Use the Import screen for destructive operations.[/red]"
                    )
                    return
                elif mode_str != "merge":
                    output.append_line(
                        f"[yellow]Unknown mode '{mode_str}', using merge[/yellow]"
                    )
                i += 2
            else:
                i += 1

        try:
            import_mgr = self.app.get_import_manager()
            validation = import_mgr.validate(input_path)
            if not validation.valid:
                output.append_line(
                    f"[red]Import validation failed: {'; '.join(validation.errors)}[/red]"
                )
                return

            result = import_mgr.import_data(
                input_path,
                mode=mode,
                progress_callback=lambda msg: output.append_line(f"[dim]{msg}[/dim]"),
            )
            if result.success:
                output.append_line(
                    f"[green]Imported {result.items_imported} items[/green]"
                )
                if result.warnings:
                    for warning in result.warnings:
                        output.append_line(f"[yellow]Warning: {warning}[/yellow]")
            else:
                output.append_line(f"[red]Import failed: {result.error}[/red]")
        except (OSError, ValueError, TypeError) as e:
            output.append_line(f"[red]Import error: {e}[/red]")
