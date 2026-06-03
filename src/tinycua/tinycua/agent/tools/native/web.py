"""Backward-compatible shim for tinycua.tools.native.web.

Re-exports the web tool so that existing code importing from
``tinycua.agent.tools.native.web`` continues to work.
"""

from tinycua.tools.native.web import fetch_url

__all__ = ["fetch_url"]
