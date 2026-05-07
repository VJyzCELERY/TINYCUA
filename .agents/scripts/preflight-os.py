"""Detect the current operating system.

Run this at session start so the agent knows which platform it's running on.
Different OSes have different paths, commands, and behaviors.

Usage:
    uv run python .agents/scripts/preflight-os.py

Exits 0. Prints OS info to stdout.
<EOF_DESC>
"""

import platform, sys


def main():
    system = platform.system().lower()
    release = platform.release()
    machine = platform.machine()

    # Normalize names
    if system == "darwin":
        os_name = "macOS"
    elif system == "windows":
        os_name = "Windows"
    elif system == "linux":
        os_name = "Linux"
    else:
        os_name = system

    print(f"[OS] {os_name} {release} ({machine})")
    print(f"[OS] Python: {sys.version.split()[0]}")

    # Platform-specific notes
    if os_name == "Windows":
        print("[OS] Note: Use PowerShell-compatible commands. Path separator is '\\'.")
        print("[OS] Note: Use `where` instead of `which` for finding executables.")
    elif os_name == "macOS":
        print("[OS] Note: Uses BSD-style commands. Install GNU utils via Homebrew if needed.")
    elif os_name == "Linux":
        print("[OS] Note: Standard GNU/Linux environment. Use apt/yum/pacman for packages.")


if __name__ == "__main__":
    main()
