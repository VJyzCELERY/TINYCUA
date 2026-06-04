"""No-op CLI entry point for workspace verification."""


def main() -> None:
    """Print a workspace-ready confirmation and exit.

    This is a no-op entry point that confirms the tinycua workspace
    is correctly set up and the entry point is wired properly.
    """
    print("tinycua: workspace is ready.")
    raise SystemExit(0)
