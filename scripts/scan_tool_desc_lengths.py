"""Scan all tool description fields for Anthropic 1024-char limit."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "creative-os"))
sys.path.insert(0, str(ROOT))

from services.managed_agent_client import _custom_tools_for_agent  # noqa: E402


def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k == "description" and isinstance(v, str) and len(v) > 1024:
                print(f"OVER {len(v)} at {p}")
            walk(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{path}[{i}]")


def main():
    tools = _custom_tools_for_agent()
    print(f"total tools: {len(tools)}")
    for i, t in enumerate(tools):
        d = t.get("description", "")
        if len(d) > 1024:
            print(f"tool[{i}] {t['name']} top-level OVER {len(d)}")
        elif i >= 52:
            print(f"tool[{i}] {t['name']} len={len(d)}")
    walk(tools)
    print("scan complete")


if __name__ == "__main__":
    main()
