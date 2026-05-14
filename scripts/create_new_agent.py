"""
Create a fresh Anthropic Managed Agent against the current code.

Use only after `scripts/diff_agent_prompt.py` reports OUT OF SYNC.

This script intentionally bypasses the cached `ANTHROPIC_AGENT_ID` env
var so it always mints a NEW agent against the live `SYSTEM_PROMPT` and
`_custom_tools_for_agent()` from this checkout. Prints the new agent id
for the user to paste into Railway as `ANTHROPIC_AGENT_ID`.

The previous agent is NOT deleted — keep its id around as
`ANTHROPIC_AGENT_ID_PREVIOUS` for instant rollback.

Setup:
  - `pip install anthropic>=0.40.0`
  - ANTHROPIC_API_KEY in env.saas (production key — agents are tied to
    the API key, so the new id only works in the same account)

Run:
  cd /Users/MD/ugc-engine
  unset ANTHROPIC_AGENT_ID            # critical so the singleton creates
  python scripts/create_new_agent.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "env.saas", override=False)
load_dotenv(ROOT / ".env.saas", override=False)
load_dotenv(ROOT / "env", override=False)
load_dotenv(ROOT / ".env", override=False)

sys.path.insert(0, str(ROOT / "services" / "creative-os"))


async def main() -> int:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to env.saas.")
        return 2

    # Force a fresh agent: clear the env var so the cached singleton in
    # _ensure_agent doesn't short-circuit with the old id.
    os.environ.pop("ANTHROPIC_AGENT_ID", None)

    from services.managed_agent_client import (
        ManagedAgentClient,
        _custom_tools_for_agent,
    )

    client = ManagedAgentClient()
    client._agent_id = None  # belt-and-braces — clear the in-process cache

    print("Creating new Anthropic Managed Agent against current code ...")
    try:
        new_id = await client._ensure_agent()
    except Exception as e:
        print(f"ERROR: agent creation failed: {type(e).__name__}: {e}")
        return 3

    # Best-effort: fetch the freshly-created agent to confirm metadata.
    created_at = "unknown"
    model = "unknown"
    try:
        live = await client._client.beta.agents.retrieve(new_id)
        created_at = str(getattr(live, "created_at", "unknown"))
        model = str(getattr(live, "model", "unknown"))
    except Exception as e:
        print(f"WARN: agent created but follow-up retrieve failed: {e}")

    custom_count = sum(
        1 for t in _custom_tools_for_agent()
        if t.get("type") == "custom"
    )

    print()
    print("=" * 64)
    print(f"NEW AGENT ID:  {new_id}")
    print(f"Created at:    {created_at}")
    print(f"Model:         {model}")
    print(f"Tool count:    {custom_count} custom + 1 agent_toolset_20260401")
    print("=" * 64)
    print()
    print("Next steps:")
    print(f"  1. In Railway, rename current ANTHROPIC_AGENT_ID → ANTHROPIC_AGENT_ID_PREVIOUS")
    print(f"     (rollback path — do NOT delete the old id)")
    print(f"  2. Set ANTHROPIC_AGENT_ID={new_id}")
    print(f"  3. Restart the creative-os service")
    print(f"  4. Smoke-test in production: send a Spanish-script UGC ad request")
    print(f"     and confirm the dialogue stays in Spanish in the KIE dashboard")
    print(f"  5. After 24-48h of stability, re-run scripts/diff_agent_prompt.py")
    print(f"     to verify IN SYNC against the new id")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
