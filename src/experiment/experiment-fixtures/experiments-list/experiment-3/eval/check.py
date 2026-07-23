"""Browser-execute and score the Experiment 3 analog clock."""

import json
import math
import sys
from pathlib import Path
from typing import Callable

from playwright.sync_api import Page, sync_playwright


PASS_THRESHOLD = 9
CRITICAL_CATEGORIES = (
    "clock_loads",
    "clock_surface",
    "second_hand",
    "minute_hand",
    "hour_hand",
    "second_updates_clockwise",
    "minute_updates_clockwise",
    "hour_updates_clockwise",
    "self_contained",
)
INSTRUMENTATION = r"""
(() => {
  const RealDate = Date;
  let now = Date.UTC(2026, 0, 1, 3, 20, 10);
  class FrozenDate extends RealDate {
    constructor(...args) { super(...(args.length ? args : [now])); }
    static now() { return now; }
  }
  FrozenDate.parse = RealDate.parse;
  FrozenDate.UTC = RealDate.UTC;
  window.Date = FrozenDate;
  window.__setClockNow = value => { now = value; };
  window.__clockCallbacks = [];
  window.__clockIntervals = [];
  const schedule = callback => {
    if (typeof callback === 'function') window.__clockCallbacks.push(callback);
    return window.__clockCallbacks.length;
  };
  window.requestAnimationFrame = schedule;
  window.setInterval = callback => {
    if (typeof callback === 'function') window.__clockIntervals.push(callback);
    return window.__clockIntervals.length;
  };
  window.setTimeout = schedule;
  window.cancelAnimationFrame = () => {};
  window.clearInterval = () => {};
  window.clearTimeout = () => {};
  window.__clockStrokes = [];
  const paths = new WeakMap();
  const prototype = CanvasRenderingContext2D.prototype;
  const beginPath = prototype.beginPath;
  const moveTo = prototype.moveTo;
  const lineTo = prototype.lineTo;
  const stroke = prototype.stroke;
  prototype.beginPath = function(...args) {
    paths.set(this, []);
    return beginPath.apply(this, args);
  };
  const recordPoint = function(context, x, y) {
    const matrix = context.getTransform();
    const point = new DOMPoint(x, y).matrixTransform(matrix);
    const path = paths.get(context) || [];
    path.push([point.x, point.y]);
    paths.set(context, path);
  };
  prototype.moveTo = function(x, y) {
    recordPoint(this, x, y);
    return moveTo.call(this, x, y);
  };
  prototype.lineTo = function(x, y) {
    recordPoint(this, x, y);
    return lineTo.call(this, x, y);
  };
  prototype.stroke = function(...args) {
    const canvas = this.canvas;
    window.__clockStrokes.push({
      width: canvas.width,
      height: canvas.height,
      points: paths.get(this) || []
    });
    return stroke.apply(this, args);
  };
  window.__flushClock = () => {
    window.__clockIntervals.forEach(callback => callback(now));
    for (let round = 0; round < 4; round += 1) {
      const callbacks = window.__clockCallbacks.splice(0);
      if (!callbacks.length) break;
      callbacks.forEach(callback => callback(now));
    }
  };
})();
"""


def require(condition: bool, message: str) -> str:
    """Return evidence or fail one binary check."""
    if not condition:
        raise ValueError(message)
    return message


def evaluate(checks: dict[str, Callable[[], str]], result: Path) -> int:
    """Run binary checks and write category evidence."""
    outcomes: dict[str, bool] = {}
    evidence: dict[str, list[str]] = {}
    for name, check in checks.items():
        try:
            evidence[name] = [check()]
            outcomes[name] = True
        except Exception as error:
            evidence[name] = [f"failed: {error}"]
            outcomes[name] = False
            print(f"{name}: {error}", file=sys.stderr)
    total = sum(outcomes.values())
    score = {
        "categories": {
            name: {
                "points": int(outcomes[name]),
                "max_points": 1,
                "evidence": evidence[name],
            }
            for name in checks
        },
        "total": total,
        "pass_threshold": PASS_THRESHOLD,
        "critical_categories": list(CRITICAL_CATEGORIES),
    }
    result.mkdir(parents=True, exist_ok=True)
    (result / "score.json").write_text(json.dumps(score, indent=2) + "\n")
    return int(
        total < PASS_THRESHOLD
        or any(not outcomes[name] for name in CRITICAL_CATEGORIES)
    )


def browser_sample(page: Page, timestamp: int) -> dict[str, object]:
    """Advance the frozen browser clock and return rendered hand geometry."""
    return page.evaluate(
        """timestamp => {
          window.__setClockNow(timestamp);
          window.__clockStrokes.length = 0;
          window.__flushClock();
          const svgLines = [];
          for (const svg of document.querySelectorAll('svg')) {
            const box = svg.getBoundingClientRect();
            for (const line of svg.querySelectorAll('line')) {
              const matrix = line.getScreenCTM();
              if (!matrix) continue;
              const start = new DOMPoint(
                Number(line.getAttribute('x1') || 0),
                Number(line.getAttribute('y1') || 0)
              ).matrixTransform(matrix);
              const end = new DOMPoint(
                Number(line.getAttribute('x2') || 0),
                Number(line.getAttribute('y2') || 0)
              ).matrixTransform(matrix);
              svgLines.push({
                width: box.width,
                height: box.height,
                center: [box.x + box.width / 2, box.y + box.height / 2],
                points: [[start.x, start.y], [end.x, end.y]]
              });
            }
          }
          return {
            scheduled: window.__clockCallbacks.length + window.__clockIntervals.length,
            surfaces: Array.from(document.querySelectorAll('canvas, svg')).filter(
              element => {
                const box = element.getBoundingClientRect();
                return box.width > 0 && box.height > 0;
              }
            ).length,
            strokes: window.__clockStrokes,
            svgLines
          };
        }""",
        timestamp,
    )


def _distance(point: list[float], center: tuple[float, float]) -> float:
    return math.hypot(point[0] - center[0], point[1] - center[1])


def rendered_angles(sample: dict[str, object]) -> list[float]:
    """Extract center-originating line angles clockwise from twelve o'clock."""
    segments = [*sample["strokes"], *sample["svgLines"]]
    angles: list[float] = []
    for segment in segments:
        points = segment["points"]
        if len(points) < 2:
            continue
        center = tuple(
            segment.get("center", (segment["width"] / 2, segment["height"] / 2))
        )
        radius = min(segment["width"], segment["height"]) / 2
        for start, end in zip(points, points[1:]):
            distances = (_distance(start, center), _distance(end, center))
            if min(distances) > radius * 0.25 or max(distances) < radius * 0.3:
                continue
            target = start if distances[0] > distances[1] else end
            angle = (
                math.degrees(math.atan2(target[0] - center[0], center[1] - target[1]))
                % 360
            )
            angles.append(angle)
    return angles


def has_angle(sample: dict[str, object], expected: float, tolerance: float = 4) -> bool:
    """Return whether rendered geometry contains one expected hand angle."""
    return any(
        min((angle - expected) % 360, (expected - angle) % 360) <= tolerance
        for angle in rendered_angles(sample)
    )


def probe_clock(clock: Path) -> tuple[dict[str, dict[str, object]], list[str]]:
    """Execute the clock at fixed times in one isolated Chromium page."""
    external_requests: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path="/usr/bin/chromium")
        context = browser.new_context()
        context.add_init_script(INSTRUMENTATION)
        context.route(
            "http://**/*",
            lambda route: (external_requests.append(route.request.url), route.abort()),
        )
        context.route(
            "https://**/*",
            lambda route: (external_requests.append(route.request.url), route.abort()),
        )
        page = context.new_page()
        page.set_content(clock.read_text(), wait_until="load")
        samples = {
            "base": browser_sample(page, 1767237610000),  # 03:20:10 UTC
            "second": browser_sample(page, 1767237611000),
            "minute": browser_sample(page, 1767237660000),  # 03:21:00 UTC
            "hour": browser_sample(page, 1767243610000),  # 05:00:10 UTC
        }
        browser.close()
    return samples, external_requests


def main() -> int:
    """Score browser-observed clock rendering and time-derived motion."""
    submission = Path(sys.argv[1])
    result = Path(sys.argv[2])
    clock = submission / "clock.html"
    state: dict[str, object] = {}

    def probes() -> dict[str, dict[str, object]]:
        if "samples" not in state:
            samples, requests = probe_clock(clock)
            state["samples"] = samples
            state["requests"] = requests
        return state["samples"]

    checks: dict[str, Callable[[], str]] = {
        "clock_loads": lambda: require(
            clock.is_file() and bool(probes()), "clock.html loads in Chromium"
        ),
        "clock_surface": lambda: require(
            probes()["base"]["surfaces"] > 0, "a visible Canvas or SVG surface renders"
        ),
        "second_hand": lambda: require(
            has_angle(probes()["base"], 60), "second hand renders at 60 degrees"
        ),
        "minute_hand": lambda: require(
            has_angle(probes()["base"], 120) or has_angle(probes()["base"], 121),
            "minute hand renders from the frozen current time",
        ),
        "hour_hand": lambda: require(
            has_angle(probes()["base"], 90) or has_angle(probes()["base"], 100),
            "hour hand renders from the frozen current time",
        ),
        "second_updates_clockwise": lambda: require(
            probes()["base"]["scheduled"] > 0 and has_angle(probes()["second"], 66),
            "scheduled update moves the second hand clockwise",
        ),
        "minute_updates_clockwise": lambda: require(
            has_angle(probes()["minute"], 126),
            "forward time moves the minute hand clockwise",
        ),
        "hour_updates_clockwise": lambda: require(
            has_angle(probes()["hour"], 150),
            "forward time moves the hour hand clockwise",
        ),
        "self_contained": lambda: require(
            not state.get("requests") and bool(probes()),
            "clock makes no external HTTP requests",
        ),
    }
    return evaluate(checks, result)


if __name__ == "__main__":
    raise SystemExit(main())
