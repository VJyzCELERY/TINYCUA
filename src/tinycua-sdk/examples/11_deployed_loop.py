"""Example: Deployed Agent with Custom Loop and Helper Functions.

This example demonstrates:
1. Custom loop with helper functions (auto-detected and packaged)
2. External dependencies (auto-installed before deployment)
3. Deployment to backend with bundled helpers

The loop_resolver module automatically:
- Extracts helper functions from loop source
- Detects external dependencies via AST analysis
- Packages everything for deployment

Prerequisites:
- PostgreSQL running (make docker-up)
- Backend running (src/tinycua-backend)
- Runner running (src/tinycua-runner)
- LM Studio with model loaded

Usage:
    python examples/11_deployed_loop.py
"""

import asyncio
import os

import httpx

from tinycua_sdk.agent.loop import DefaultLoop
from tinycua_sdk.clients import BackendClient


# =============================================================================
# Helper Functions (auto-detected by loop_resolver)
# =============================================================================


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format a number as currency.

    Args:
        amount: The amount to format
        currency: Currency code (default: USD)

    Returns:
        Formatted currency string
    """
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"


def calculate_tip(amount: float, percentage: float) -> tuple[float, float]:
    """Calculate tip amount and total.

    Args:
        amount: The bill amount
        percentage: Tip percentage (e.g., 15 for 15%)

    Returns:
        Tuple of (tip_amount, total)
    """
    tip = amount * (percentage / 100)
    total = amount + tip
    return round(tip, 2), round(total, 2)


# =============================================================================
# Custom Loop with External Dependency
# =============================================================================
# Note: This loop uses 'requests' which will be auto-detected and installed


class BudgetLoop(DefaultLoop):
    """Custom loop for budget calculations.

    This loop provides additional context about calculations
    and formats currency output nicely.
    """

    async def run(self, agent, user_input, **kwargs):
        if self.runner:
            self.runner.emit_loop_log(
                f"Processing budget request: {user_input[:50]}...", "info"
            )

        result = await super().run(agent, user_input, **kwargs)

        if self.runner:
            self.runner.emit_loop_log("Completed budget calculation", "info")
        return result


# =============================================================================
# Another Example: Loop with External API Call
# =============================================================================


class ExternalDataLoop(DefaultLoop):
    """Custom loop that fetches external data.

    Uses 'requests' library to fetch data from APIs.
    The dependency is auto-detected and installed.
    """

    async def run(self, agent, user_input, **kwargs):
        print("[ExternalDataLoop] Fetching external data...")

        # requests is auto-detected as an external dependency
        # import requests  # Not needed directly - helpers handle it

        result = await super().run(agent, user_input, **kwargs)

        print("[ExternalDataLoop] External data processed")
        return result


# =============================================================================
# Main Demo
# =============================================================================


async def demo_deployment():
    """Demonstrate deployment with custom loop and helpers."""
    print("=" * 70)
    print("TINYCUA - Deployed Agent with Custom Loop & Helpers")
    print("=" * 70)

    BACKEND_URL = os.getenv("TINYCUA_BACKEND_URL", "http://localhost:8000")
    print(f"Backend: {BACKEND_URL}")

    client = BackendClient(base_url=BACKEND_URL)

    import time

    email = f"demo_loop_{int(time.time())}@example.com"
    # WARNING: Do not use the default password in production.
    # Set TINYCUA_PASSWORD environment variable to use a secure password.
    password = os.environ.get("TINYCUA_PASSWORD", "changeme")

    try:
        await client.register(
            email=email, password=password, tenant_name="Loop Demo Tenant"
        )
        print(f"\n[✓] Registered: {email}")
    except httpx.HTTPStatusError:
        print("\n[~] User exists, logging in...")
        await client.login(email=email, password=password)
        print(f"[✓] Logged in: {email}")

    print(f"[✓] Tenant: {client.tenant_id}")

    from tinycua_sdk.agent import Agent

    print("\n[1] Creating agent with custom loop...")

    agent = Agent(
        name="budget-assistant",
        instructions="""You are a helpful budget assistant.
        Use the format_currency and calculate_tip helpers for currency formatting.
        Example: format_currency(100.50, 'USD') returns '$100.50'
        Example: calculate_tip(50, 15) returns (7.5, 57.5) for tip and total.""",
        provider=os.getenv("TINYCUA_PROVIDER", "lmstudio"),
        model=os.getenv("TINYCUA_MODEL", "qwen/qwen3.5-9b"),
        base_url="http://127.0.0.1:1234",
        loop=BudgetLoop(),
        backend_url=BACKEND_URL,
        backend_api_key=client.api_key,
    )

    print(f"    Agent: {agent.name}")
    print(f"    Loop: {agent.config.loop.__class__.__name__}")

    print("\n[2] Serializing agent config (shows extracted helpers)...")
    config = agent.config.to_config()
    loop_cfg = config.get("loop", {})
    print(f"    Class: {loop_cfg.get('class_name')}")
    print(f"    Dependencies: {loop_cfg.get('dependencies', [])}")
    print(f"    Helpers: {[h['name'] for h in loop_cfg.get('helpers', [])]}")

    if loop_cfg.get("helpers"):
        print("    Helper sources:")
        for h in loop_cfg.get("helpers", []):
            print(f"      - {h['name']}: {h['source'][:60]}...")

    print("\n[3] Deploying to backend...")
    deployment = await agent.deploy()
    print(f"    [✓] Deployed! Agent ID: {deployment.get('id', 'N/A')}")

    print("\n[4] Verifying loop config in backend...")
    saved_agent = await client.get_agent(deployment.get("id"))
    loop_cfg = saved_agent.get("config", {}).get("loop", {})
    print(f"    Stored class: {loop_cfg.get('class_name')}")
    print(f"    Stored deps: {loop_cfg.get('dependencies', [])}")
    print(f"    Stored helpers: {[h['name'] for h in loop_cfg.get('helpers', [])]}")

    print("\n[5] Running agent via backend...")
    try:
        response = await agent.run("What is 15% tip on $50?")
        if response:
            print(f"    Response: {response[:400]}...")
        else:
            print("    Response: No response")
    except Exception as e:
        print(f"    Error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

    print("\n[6] Listing deployed agents...")
    agents = await client.list_agents()
    print(f"    Total agents: {len(agents)}")
    for a in agents[-3:]:
        print(f"    - {a['name']} (ID: {a['id'][:8]}...)")

    print("\n" + "=" * 70)
    print("Deployed loop example completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo_deployment())
