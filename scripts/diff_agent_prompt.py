"""
Diff a live Anthropic Managed Agent against the current code.

Read-only diagnostic. Use this before deciding to refresh the production
agent. Compares the live agent's stored `system` prompt and tools list
against the current source's `SYSTEM_PROMPT` and `_custom_tools_for_agent()`.

When the live agent matches the code, a Railway redeploy is enough to
pick up any recent fixes. When they diverge, the system prompt and/or
tool schemas were edited since the agent was created and you need to
mint a new agent (run `scripts/create_new_agent.py`).

Setup:
  - `pip install anthropic>=0.40.0`
  - ANTHROPIC_API_KEY in env.saas (the production key is fine — this is
    a read-only call against an existing agent)
  - ANTHROPIC_AGENT_ID set to the production agent id you want to inspect

Run:
  cd /Users/MD/ugc-engine
  python scripts/diff_agent_prompt.py
"""
from __future__ import annotations

import asyncio
import difflib
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

from anthropic import AsyncAnthropic  # noqa: E402

from services.managed_agent_client import (  # noqa: E402
    BETA_HEADER,
    SYSTEM_PROMPT,
    _custom_tools_for_agent,
)


def _truncate_diff(diff_lines: list[str], max_lines: int = 200) -> str:
    if len(diff_lines) <= max_lines:
        return "\n".join(diff_lines)
    head = diff_lines[: max_lines // 2]
    tail = diff_lines[-max_lines // 2 :]
    omitted = len(diff_lines) - max_lines
    return "\n".join(head + [f"\n  ... [{omitted} more diff lines omitted] ...\n"] + tail)


def _live_tool_names(live_tools) -> tuple[set[str], list[str]]:
    """Extract custom tool names and built-in toolset references."""
    names: set[str] = set()
    builtins: list[str] = []
    for t in (live_tools or []):
        # SDK objects carry attrs; some may also be plain dicts.
        ttype = getattr(t, "type", None) or (t.get("type") if isinstance(t, dict) else None)
        tname = getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else None)
        if ttype and ttype != "custom" and "toolset" in str(ttype):
            builtins.append(str(ttype))
        elif tname:
            names.add(str(tname))
    return names, builtins


async def main() -> int:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to env.saas.")
        return 2

    agent_id = os.getenv("ANTHROPIC_AGENT_ID")
    if not agent_id:
        print(
            "ERROR: ANTHROPIC_AGENT_ID not set.\n"
            "       Export the value currently in Railway so this script can fetch it."
        )
        return 2

    client = AsyncAnthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": BETA_HEADER},
    )

    print(f"Fetching live agent {agent_id} ...")
    try:
        live = await client.beta.agents.retrieve(agent_id)
    except Exception as e:
        print(f"ERROR: failed to retrieve agent: {type(e).__name__}: {e}")
        return 3

    live_system_raw = getattr(live, "system", None)
    # `system` may come back as a string or a list of system blocks.
    if isinstance(live_system_raw, list):
        live_system = "".join(
            (b.get("text") if isinstance(b, dict) else getattr(b, "text", "")) or ""
            for b in live_system_raw
        )
    else:
        live_system = live_system_raw or ""

    code_system = SYSTEM_PROMPT

    system_match = live_system == code_system

    code_tools = _custom_tools_for_agent()
    code_tool_names = {t["name"] for t in code_tools if t.get("type") == "custom" and t.get("name")}
    live_names, live_builtins = _live_tool_names(getattr(live, "tools", None))

    only_in_code = sorted(code_tool_names - live_names)
    only_in_live = sorted(live_names - code_tool_names)

    print()
    print(f"Agent ID:           {agent_id}")
    print(f"Created at:         {getattr(live, 'created_at', 'unknown')}")
    print(f"Model:              {getattr(live, 'model', 'unknown')}")
    print(f"Live tool count:    {len(live_names)} custom + {len(live_builtins)} builtin ({live_builtins})")
    print(f"Code tool count:    {len(code_tool_names)} custom")
    print()

    if system_match:
        print("System prompt:      IDENTICAL  ✓")
    else:
        print("System prompt:      DIVERGED  ✗")
        diff = list(
            difflib.unified_diff(
                live_system.splitlines(),
                code_system.splitlines(),
                fromfile="live agent.system",
                tofile="code SYSTEM_PROMPT",
                lineterm="",
            )
        )
        print()
        print(_truncate_diff(diff, max_lines=200))
        print()

    if not only_in_code and not only_in_live:
        print("Tool schemas:       SAME NAMES  ✓  (note: input_schema fields not deeply compared)")
    else:
        print("Tool schemas:       DIVERGED  ✗")
        if only_in_code:
            print(f"  Tools added in code (missing from live agent):")
            for n in only_in_code:
                print(f"    + {n}")
        if only_in_live:
            print(f"  Tools removed from code (still present on live agent):")
            for n in only_in_live:
                print(f"    - {n}")

    print()
    if system_match and not only_in_code and not only_in_live:
        print("VERDICT: IN SYNC — no agent refresh needed. Code redeploy is sufficient.")
        return 0
    print("VERDICT: OUT OF SYNC — refresh required. Run scripts/create_new_agent.py.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
