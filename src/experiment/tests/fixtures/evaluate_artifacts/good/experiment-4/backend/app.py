"""Submitted SQLite-backed browser fixture."""

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DATABASE = Path("fixture.sqlite")


def state() -> dict[str, str]:
    """Return the page and block shown by the submitted UI."""
    with sqlite3.connect(DATABASE) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS page (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS block (id INTEGER PRIMARY KEY, content TEXT NOT NULL)"
        )
        page = connection.execute(
            "SELECT title FROM page ORDER BY id LIMIT 1"
        ).fetchone()
        block = connection.execute(
            "SELECT content FROM block ORDER BY id LIMIT 1"
        ).fetchone()
        blocks = connection.execute("SELECT COUNT(*) FROM block").fetchone()[0]
        return {
            "title": page[0] if page else "",
            "block": block[0] if block else "",
            "blocks": blocks,
        }


class App(BaseHTTPRequestHandler):
    """Serve the submitted UI and its SQLite-backed UI actions."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/state":
            self.respond(state())
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode())

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/page":
            with sqlite3.connect(DATABASE) as connection:
                connection.execute("INSERT INTO page (title) VALUES ('Untitled')")
        elif self.path == "/api/block":
            with sqlite3.connect(DATABASE) as connection:
                connection.execute("INSERT INTO block (content) VALUES ('')")
        self.respond(state())

    def do_PUT(self) -> None:  # noqa: N802
        size = int(self.headers["Content-Length"])
        value = json.loads(self.rfile.read(size))["value"]
        column = "title" if self.path == "/api/page" else "content"
        table = "page" if self.path == "/api/page" else "block"
        with sqlite3.connect(DATABASE) as connection:
            connection.execute(
                f"UPDATE {table} SET {column} = ? WHERE id = 1", (value,)
            )
        self.respond(state())

    def respond(self, body: dict[str, str]) -> None:
        """Write a JSON response."""
        encoded = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_: object) -> None:
        """Keep fixture server output deterministic."""


class Server(ThreadingHTTPServer):
    """Permit the submitted app to restart on its declared local port."""

    allow_reuse_address = True


PAGE = """<!doctype html>
<title>SQLite Notion fixture</title>
<button class="btn-new-page" onclick="createPage()">New page</button>
<input id="pageTitleInput" onchange="save('/api/page', this.value)">
<button class="btn-block-action" onclick="createBlock()">Add block</button>
<input id="blockEditor" onchange="save('/api/block', this.value)">
<p class="block-container"></p>
<script>
async function load() { const state = await (await fetch('/api/state')).json(); pageTitleInput.value = state.title; blockEditor.value = state.block; document.querySelector('.block-container').textContent = `${state.blocks} blocks`; }
async function createPage() { await fetch('/api/page', {method: 'POST'}); await load(); }
async function createBlock() { await fetch('/api/block', {method: 'POST'}); await load(); }
async function save(path, value) { await fetch(path, {method: 'PUT', body: JSON.stringify({value})}); }
load();
</script>"""


if __name__ == "__main__":
    Server(("127.0.0.1", 5000), App).serve_forever()
