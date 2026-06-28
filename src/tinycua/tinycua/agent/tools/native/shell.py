"""Shell execution tool with safety gating and bounded output.

Provides ``run_shell`` for executing arbitrary shell commands, capturing
stdout, stderr, and exit codes with configurable timeout, ANSI stripping,
head+tail output truncation, and a two-layer safety gate (hardline block +
recoverable-destructive warning). The ResultReviewer uses the same tool the
executor uses — the per-command gate replaces the old ``run_shell_readonly``
broad-regex approach that false-positived on legitimate verification commands
like ``grep "install"``.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
from typing import Any

from tinycua_sdk.tools.decorators import tool

from tinycua.agent.tools.native.context import bind_workspace_to_tool, get_workspace_dir

_DEFAULT_TIMEOUT_SECONDS = 120
_MAX_TIMEOUT_SECONDS = 600

# Head+tail output truncation cap (chars). ~20K head + ~30K tail.
_MAX_OUTPUT_CHARS = 50_000
_OUTPUT_HEAD_CHARS = 20_000


# ---------------------------------------------------------------------------
# ANSI escape stripping
# ---------------------------------------------------------------------------

# Covers the full ECMA-48 spec: CSI (including private-mode, colon-separated
# params, intermediate bytes), OSC (BEL and ST terminators), DCS/SOS/PM/APC
# string sequences, nF multi-byte escapes, Fp/Fe/Fs single-byte escapes, and
# 8-bit C1 control characters. Adapted verbatim from hermes-agent ansi_strip.py.
_ANSI_ESCAPE_RE = re.compile(
    r"\x1b"
    r"(?:"
        r"\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]"     # CSI sequence
        r"|\][\s\S]*?(?:\x07|\x1b\\)"                  # OSC (BEL or ST terminator)
        r"|[PX^_][\s\S]*?(?:\x1b\\)"                   # DCS/SOS/PM/APC strings
        r"|[\x20-\x2f]+[\x30-\x7e]"                    # nF escape sequences
        r"|[\x30-\x7e]"                                 # Fp/Fe/Fs single-byte
    r")"
    r"|\x9b[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]"       # 8-bit CSI
    r"|\x9d[\s\S]*?(?:\x07|\x9c)"                       # 8-bit OSC
    r"|[\x80-\x9f]",                                    # Other 8-bit C1 controls
    re.DOTALL,
)
# Fast-path check — skip full regex when no escape-like bytes are present.
_HAS_ESCAPE = re.compile(r"[\x1b\x80-\x9f]")


def strip_ansi(text: str) -> str:
    """Strip ANSI/VT100 escape sequences from ``text``.

    Fast-path: if no ESC/C1 bytes are present, return unchanged (avoids the
    regex cost on the common case of plain command output).
    """
    if not text or not _HAS_ESCAPE.search(text):
        return text
    return _ANSI_ESCAPE_RE.sub("", text)


# ---------------------------------------------------------------------------
# Command normalization (defeats trivial obfuscation before pattern matching)
# ---------------------------------------------------------------------------

def _normalize_command_for_detection(command: str) -> str:
    """Normalize a command string before safety-pattern matching.

    Strips ANSI escapes, null bytes, and backslash-escapes; applies Unicode
    NFKC normalization so fullwidth-character bypass doesn't sneak past the
    hardline patterns. Mirrors hermes-agent's ``_normalize_command_for_detection``.
    """
    cleaned = strip_ansi(command)
    cleaned = cleaned.replace("\x00", "")
    # Fold backslash-escapes: r\m -> rm  (a trivial obfuscation)
    cleaned = re.sub(r"\\(.)", r"\1", cleaned)
    import unicodedata

    cleaned = unicodedata.normalize("NFKC", cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# Safety gate: hardline blocklist + recoverable-destructive warnings
# ---------------------------------------------------------------------------

# Regex fragment matching the *start* of a command (positions where a shell
# would begin parsing a new command). Used by shutdown/reboot patterns so they
# don't false-positive on "echo reboot" or "grep 'shutdown' log". Matches:
# start of string, after command separators (; && || | newline), after
# subshell openers ($( or backtick), optionally consuming leading wrapper
# commands (sudo, env VAR=VAL, exec, nohup, setsid, time).
_CMDPOS = (
    r"(?:^|[;&|\n`]|\$\()"         # start position
    r"\s*"                          # optional whitespace
    r"(?:sudo\s+(?:-[^\s]+\s+)*)?"  # optional sudo with flags
    r"(?:env\s+(?:\w+=\S*\s+)*)?"   # optional env with VAR=VAL pairs
    r"(?:(?:exec|nohup|setsid|time)\s+)*"  # optional wrapper commands
    r"\s*"
)

# Unrecoverable commands — blocked unconditionally, even in one-shot mode.
# Adapted from hermes-agent tools/approval.py:255-277.
_HARDLINE_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+(-[^\s]*\s+)*(/|/\*|/ \*)(\s|$)", "recursive delete of root filesystem"),
    (
        r"\brm\s+(-[^\s]*\s+)*(/home|/home/\*|/root|/root/\*|/etc|/etc/\*|/usr|/usr/\*|/var|/var/\*|/bin|/bin/\*|/sbin|/sbin/\*|/boot|/boot/\*|/lib|/lib/\*)(\s|$)",
        "recursive delete of system directory",
    ),
    (r"\brm\s+(-[^\s]*\s+)*(~|\$HOME)(/?|/\*)?(\s|$)", "recursive delete of home directory"),
    (r"\bmkfs(\.[a-z0-9]+)?\b", "format filesystem (mkfs)"),
    (r"\bdd\b[^\n]*\bof=/dev/(sd|nvme|hd|mmcblk|vd|xvd)[a-z0-9]*", "dd to raw block device"),
    (r">\s*/dev/(sd|nvme|hd|mmcblk|vd|xvd)[a-z0-9]*\b", "redirect to raw block device"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork bomb"),
    # kill -1 (all processes) — anchored to command position so "echo 'kill -1'" doesn't match.
    (_CMDPOS + r"kill\s+(-[^\s]+\s+)*-1\b", "kill all processes"),
    (_CMDPOS + r"(shutdown|reboot|halt|poweroff)\b", "system shutdown/reboot"),
    (_CMDPOS + r"init\s+[06]\b", "init 0/6 (shutdown/reboot)"),
    (_CMDPOS + r"systemctl\s+(poweroff|reboot|halt|kexec)\b", "systemctl poweroff/reboot"),
    (_CMDPOS + r"telinit\s+[06]\b", "telinit 0/6 (shutdown/reboot)"),
]

# Recoverable destructive commands — execute, but annotate with a warning so
# the model is aware. These are NOT blocked (one-shot mode requires the agent
# to delete files, kill processes, install packages, etc. as needed).
_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+(-[^\s]*r[^\s]*\s+|-[^\s]*\s+)+\S", "rm -r deletes recursively"),
    (r"\bchmod\b[^\n]*\b777\b", "chmod 777 opens permissions broadly"),
    (r"\bgit\s+push\b[^\n]*--force\b", "git push --force rewrites remote history"),
    (r"\bgit\s+(reset|clean|checkout)\b[^\n]*--hard\b", "git hard reset/clean discards work"),
    (r">\s*/etc/", "redirect writes to /etc (system config)"),
    (r"\bsed\b[^\n]*-i\b", "sed -i edits files in place"),
    (r"\bpip\b[^\n]*\binstall\b", "pip install modifies environment"),
    (r"\bapt\b[^\n]*\binstall\b", "apt install modifies system"),
    (r"\bnpm\b[^\n]*\binstall\b", "npm install modifies environment"),
    (r"\btruncate\b", "truncate modifies files"),
    (r"\bshred\b", "shred irrecoverably deletes file content"),
    (r"curl\b[^\n]*\|\s*(sh|bash|zsh)\b", "curl | sh executes remote code"),
    (r"wget\b[^\n]*\|\s*(sh|bash|zsh)\b", "wget | sh executes remote code"),
    # kill/pkill send signals — recoverable (the agent may need to kill a stuck
    # process). kill -1 itself is hardline-blocked above; this catches per-pid kills.
    (_CMDPOS + r"kill\s+(-\S+\s+)?\d+\b", "kill sends a signal to a process"),
    (_CMDPOS + r"pkill\b", "pkill signals processes by name"),
]

_RE_FLAGS = re.IGNORECASE | re.DOTALL
_HARDLINE_COMPILED = [(re.compile(p, _RE_FLAGS), d) for p, d in _HARDLINE_PATTERNS]
_DANGEROUS_COMPILED = [(re.compile(p, _RE_FLAGS), d) for p, d in _DANGEROUS_PATTERNS]

# sudo -S (stdin password) without a configured password is a brute-force
# vector. Blocked unconditionally.
_SUDO_STDIN_RE = re.compile(r"(?:^|[;&|`\n]|&&|\|\||\$\()\s*sudo\s+-S\b", re.IGNORECASE)


def _check_command_safety(command: str) -> tuple[bool, str | None, str | None]:
    """Check a command against the safety gate.

    Returns ``(blocked, block_reason, warning)``:
    - ``blocked=True`` → the command must not execute; ``block_reason`` explains why.
    - ``blocked=False, warning set`` → the command may execute; the result should
      carry the warning annotation so the model is aware it ran something destructive.
    - ``blocked=False, warning=None`` → the command is benign.
    """
    normalized = _normalize_command_for_detection(command)
    lower = normalized.lower()

    # Hardline: unrecoverable — always block.
    for pattern_re, description in _HARDLINE_COMPILED:
        if pattern_re.search(lower):
            return True, f"BLOCKED (hardline): {description}", None

    # sudo -S password-piping — always block.
    if _SUDO_STDIN_RE.search(lower):
        return True, "BLOCKED: sudo password guessing via stdin (sudo -S)", None

    # Dangerous: recoverable — warn but allow.
    for pattern_re, description in _DANGEROUS_COMPILED:
        if pattern_re.search(lower):
            return False, None, f"destructive: {description}"

    return False, None, None


# ---------------------------------------------------------------------------
# Exit-code interpretation — stop the model wasting turns on expected non-zero exits
# ---------------------------------------------------------------------------

def _interpret_exit_code(command: str, exit_code: int) -> str | None:
    """Return a human-readable note when a non-zero exit code is non-erroneous.

    Returns ``None`` when the exit code is 0 or genuinely signals an error.
    The note is added to the tool result so the model doesn't waste turns
    investigating expected exit codes (e.g. grep=1, diff=1, test=1).

    Adapted from hermes-agent tools/terminal_tool.py:1610-1671.
    """
    if exit_code == 0:
        return None

    # Extract the last command in a pipeline/chain — that determines the exit
    # code. Handles `cmd1 && cmd2`, `cmd1 | cmd2`, `cmd1; cmd2`.
    segments = re.split(r"\s*(?:\|\||&&|[|;])\s*", command)
    last_segment = (segments[-1] if segments else command).strip()

    # Get base command name (first word), stripping env var assignments like
    # VAR=val cmd ...
    words = last_segment.split()
    base_cmd = ""
    for w in words:
        if "=" in w and not w.startswith("-"):
            continue  # skip VAR=val
        base_cmd = w.split("/")[-1]  # handle /usr/bin/grep -> grep
        break

    if not base_cmd:
        return None

    semantics: dict[str, dict[int, str]] = {
        "grep": {1: "No matches found (not an error)"},
        "egrep": {1: "No matches found (not an error)"},
        "fgrep": {1: "No matches found (not an error)"},
        "rg": {1: "No matches found (not an error)"},
        "ag": {1: "No matches found (not an error)"},
        "ack": {1: "No matches found (not an error)"},
        "diff": {1: "Files differ (expected, not an error)"},
        "colordiff": {1: "Files differ (expected, not an error)"},
        "find": {1: "Some directories were inaccessible (partial results may still be valid)"},
        "test": {1: "Condition evaluated to false (expected, not an error)"},
        "[": {1: "Condition evaluated to false (expected, not an error)"},
        "curl": {
            6: "Could not resolve host",
            7: "Failed to connect to host",
            22: "HTTP response code indicated error (e.g. 404, 500)",
            28: "Operation timed out",
        },
        "git": {1: "Non-zero exit (often normal — e.g. 'git diff' returns 1 when files differ)"},
    }

    cmd_semantics = semantics.get(base_cmd)
    if cmd_semantics and exit_code in cmd_semantics:
        return cmd_semantics[exit_code]

    return None


# ---------------------------------------------------------------------------
# Output truncation — head + tail
# ---------------------------------------------------------------------------

def _truncate_output(text: str) -> str:
    """Head+tail truncate to ``_MAX_OUTPUT_CHARS`` with an omission notice.

    Keeps the first ``_OUTPUT_HEAD_CHARS`` chars (command echo / early errors)
    and the last ``(_MAX_OUTPUT_CHARS - _OUTPUT_HEAD_CHARS)`` chars (most
    recent output / exit errors), dropping the middle with a visible notice.
    """
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    head = text[:_OUTPUT_HEAD_CHARS]
    tail_chars = _MAX_OUTPUT_CHARS - _OUTPUT_HEAD_CHARS
    tail = text[-tail_chars:]
    omitted = len(text) - _OUTPUT_HEAD_CHARS - tail_chars
    return f"{head}\n\n... [OUTPUT TRUNCATED - {omitted} chars omitted out of {len(text)} total] ...\n\n{tail}"


# ---------------------------------------------------------------------------
# Timeout bounding
# ---------------------------------------------------------------------------

def _bounded_timeout(timeout: int) -> int:
    """Return a safe timeout for model-requested shell execution.

    Clamps to ``[1, _MAX_TIMEOUT_SECONDS]``. Values above the max are rejected
    by the caller (not silently clamped) so the model is nudged to narrow its
    command rather than pick absurd timeouts.
    """
    from tinycua.agent.tools.native._timeout import bounded_timeout

    result = bounded_timeout(timeout, default=_DEFAULT_TIMEOUT_SECONDS, max_seconds=_MAX_TIMEOUT_SECONDS)
    # shell's policy is clamp (never None), so coerce the None case to max.
    return result if result is not None else _MAX_TIMEOUT_SECONDS


def _uses_unsafe_mkdir_braces(command: str) -> bool:
    """Detect mkdir with brace expansion that POSIX /bin/sh won't expand."""
    if "mkdir" not in command or "{" not in command or "}" not in command:
        return False
    start = command.find("{")
    end = command.find("}", start)
    return start < end and "," in command[start:end]


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------

@tool
def run_shell(command: str, timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Execute a shell command and capture its output.

    Use this for inspection, verification, and execution: listing files
    (``ls -la``), checking tool versions, running tests (``pytest``), grepping
    output, building projects, or any shell work. File changes are also
    possible — prefer ``write_file``/``edit_file`` for file edits so the
    workspace stays auditable, but shell writes (``mkdir``, ``rm``, ``cp``,
    ``pip install``) are allowed when needed.

    Safety: a small set of unrecoverable commands (``rm -rf /``, ``mkfs``,
    ``dd of=/dev/sd*``, ``shutdown``, ``kill -1``, fork bombs) is blocked
    unconditionally. Recoverable destructive commands (``rm -r ./tmp``,
    ``pip install``, ``git push --force``, ``kill <pid>``) execute and the
    result carries a ``warning`` field noting what it did.

    Output: stdout/stderr are ANSI-stripped and head+tail truncated to 50K
    chars with an omission notice when large. Non-zero exit codes for known
    commands (grep/diff/test/curl/git) carry an ``exit_code_meaning`` note so
    you don't waste a turn investigating expected non-error exits.

    Args:
        command: The shell command to execute. Runs under ``/bin/sh``; do not
            rely on shell-specific brace expansion such as ``mkdir -p {a,b}``.
        timeout: Maximum execution time in seconds (default 120, max 600).
            Values above 600 are rejected — narrow the command instead.

    Returns:
        A dict with keys: stdout, stderr, exit_code, timed_out, error, and
        optionally exit_code_meaning (for known non-error non-zero exits) and
        warning (when a recoverable destructive command ran).
    """
    if _uses_unsafe_mkdir_braces(command):
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": "POSIX /bin/sh does not expand mkdir braces; use explicit paths instead.",
        }

    # Safety gate (before any execution).
    blocked, block_reason, warning = _check_command_safety(command)
    if blocked:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": block_reason,
        }

    # Timeout: reject above-max so the model is nudged to narrow the command.
    try:
        requested_timeout = int(timeout)
    except (TypeError, ValueError):
        requested_timeout = _DEFAULT_TIMEOUT_SECONDS
    if requested_timeout > _MAX_TIMEOUT_SECONDS:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": (
                f"timeout {requested_timeout}s exceeds the { _MAX_TIMEOUT_SECONDS}s max; "
                "narrow the command (e.g. run a subset of tests) instead of raising the timeout."
            ),
        }
    effective_timeout = min(max(requested_timeout, 1), _MAX_TIMEOUT_SECONDS)

    try:
        workspace = get_workspace_dir()
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            preexec_fn=os.setsid,
            cwd=str(workspace) if workspace is not None else None,
        )
        stdout, stderr = process.communicate(timeout=effective_timeout)
        stdout = strip_ansi(stdout or "")
        stderr = strip_ansi(stderr or "")
        stdout = _truncate_output(stdout)
        stderr = _truncate_output(stderr)
        result: dict[str, Any] = {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": process.returncode,
            "timed_out": False,
            "error": None,
        }
        meaning = _interpret_exit_code(command, process.returncode)
        if meaning:
            result["exit_code_meaning"] = meaning
        if warning:
            result["warning"] = warning
        return result
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        stdout, stderr = process.communicate()
        stdout = strip_ansi(stdout or "")
        stderr = strip_ansi(stderr or "")
        stdout = _truncate_output(stdout)
        stderr = _truncate_output(stderr)
        result = {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": -1,
            "timed_out": True,
            "error": f"Command timed out after {effective_timeout}s",
        }
        if warning:
            result["warning"] = warning
        return result
    except subprocess.SubprocessError as exc:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": str(exc),
        }


bind_workspace_to_tool(run_shell)


# ---------------------------------------------------------------------------
# Self-check — run `python -m tinycua.agent.tools.native.shell` to verify.
# ponytail: one runnable check, no framework. Fails fast if the gate or
# exit-code logic breaks.
# ---------------------------------------------------------------------------

def _self_check() -> None:
    """Assert the gate and exit-code logic behave. Not a test suite."""
    # Hardline blocks
    for cmd in ["rm -rf /", "rm -rf /etc", "mkfs.ext4 /dev/sda1", "dd if=/dev/zero of=/dev/sda",
                "shutdown now", "reboot", "kill -1", ":(){ :|:& };:"]:
        blocked, reason, _warn = _check_command_safety(cmd)
        assert blocked, f"expected block for: {cmd!r}"
        assert reason, f"expected block reason for: {cmd!r}"

    # _CMDPOS anchoring — echo reboot / grep shutdown must NOT block
    for cmd in ["echo reboot", "grep 'shutdown' log.txt", "echo 'kill -1'"]:
        blocked, _r, _w = _check_command_safety(cmd)
        assert not blocked, f"false-positive block for: {cmd!r}"

    # grep "install" must NOT block and NOT warn (no broad \binstall\b)
    blocked, _r, warning = _check_command_safety('grep "install" file.txt')
    assert not blocked, "grep install must not be blocked"
    assert warning is None, f"grep install must not warn, got: {warning!r}"

    # Recoverable destructive — warns but allows
    for cmd in ["rm -rf ./tmp/build", "pip install requests", "git push --force origin main",
                "kill 12345", "chmod 777 ./run.sh"]:
        blocked, _r, warning = _check_command_safety(cmd)
        assert not blocked, f"recoverable cmd must not block: {cmd!r}"
        assert warning, f"expected warning for: {cmd!r}"

    # Exit-code interpretation
    assert _interpret_exit_code("grep foo /nope", 1) == "No matches found (not an error)"
    assert _interpret_exit_code("diff a b", 1) == "Files differ (expected, not an error)"
    assert _interpret_exit_code("test -f x", 1) == "Condition evaluated to false (expected, not an error)"
    assert _interpret_exit_code("echo ok", 0) is None
    assert _interpret_exit_code("ls /nope", 2) is None  # unknown cmd/code → None

    # Truncation
    big = "x" * 100_000
    trunc = _truncate_output(big)
    assert len(trunc) <= _MAX_OUTPUT_CHARS + 200  # +notice overhead
    assert "TRUNCATED" in trunc

    # Real execution
    r = run_shell("echo hello")
    assert r["exit_code"] == 0 and "hello" in r["stdout"], r
    # grep with no match on an existing file → exit 1 + exit_code_meaning
    r = run_shell("grep nomatch_does_not_exist___ /etc/hostname")
    assert r["exit_code"] == 1 and r.get("exit_code_meaning") == "No matches found (not an error)", r

    print("shell.py self-check OK")


if __name__ == "__main__":
    _self_check()
