#!/usr/bin/env python3
"""Run a small, stateless Playwright browser scenario."""

import argparse
import json
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

from playwright.sync_api import sync_playwright


MAX_TEXT_CHARS = 10_000


def parse_args() -> argparse.Namespace:
    """Parse one browser scenario from command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--wait-for-selector", action="append", default=[])
    parser.add_argument("--fill", action="append", nargs=2, default=[])
    parser.add_argument("--click", action="append", default=[])
    parser.add_argument("--click-at", action="append", nargs=2, type=float, default=[])
    parser.add_argument("--expect-selector", action="append", default=[])
    parser.add_argument("--expect-text", action="append", default=[])
    parser.add_argument("--wait-ms", type=int, default=0)
    parser.add_argument("--screenshot")
    return parser.parse_args()


def workspace_path(value: str) -> Path:
    """Resolve an output path and require it to remain under the workdir."""
    workspace = Path.cwd().resolve()
    resolved = (workspace / value).resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as error:
        raise ValueError("screenshot path must be inside the workdir") from error
    return resolved


def validate_url(value: str) -> str:
    """Allow web URLs and workdir-local file URLs."""
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return value
    if parsed.scheme != "file":
        raise ValueError("url must use http, https, or file")
    target = Path(unquote(parsed.path)).resolve()
    try:
        target.relative_to(Path.cwd().resolve())
    except ValueError as error:
        raise ValueError("file URL must point inside the workdir") from error
    return value


def run() -> dict[str, object]:
    """Open the page, perform requested actions, and return visible state."""
    args = parse_args()
    if args.wait_ms < 0:
        raise ValueError("wait-ms must be non-negative")
    browser_path = shutil.which("chromium") or shutil.which("chromium-browser")
    if browser_path is None:
        raise RuntimeError("Chromium is not installed in this fixture image")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=browser_path,
            headless=True,
        )
        try:
            page = browser.new_page()
            page.goto(validate_url(args.url), wait_until="networkidle", timeout=15_000)
            for selector in args.wait_for_selector:
                page.locator(selector).wait_for(timeout=15_000)
            for selector, value in args.fill:
                page.locator(selector).fill(value)
            for selector in args.click:
                page.locator(selector).click()
            for x, y in args.click_at:
                page.mouse.click(x, y)
            for selector in args.expect_selector:
                page.locator(selector).wait_for(timeout=15_000)
            for text in args.expect_text:
                page.get_by_text(text, exact=True).wait_for(timeout=15_000)
            if args.wait_ms:
                page.wait_for_timeout(args.wait_ms)
            screenshot = None
            if args.screenshot:
                screenshot_path = workspace_path(args.screenshot)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot_path), full_page=True)
                screenshot = str(screenshot_path.relative_to(Path.cwd().resolve()))
            return {
                "success": True,
                "title": page.title(),
                "url": page.url,
                "visible_text": page.locator("body").inner_text()[:MAX_TEXT_CHARS],
                "screenshot": screenshot,
            }
        finally:
            browser.close()


def main() -> int:
    """Run the scenario and emit machine-readable output."""
    try:
        print(json.dumps(run()))
    except Exception as error:
        print(json.dumps({"success": False, "error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
