#!/usr/bin/env python3
"""Post-deploy check: Brevo admin list_id endpoints exist on the production API.

Usage:
  python scripts/verify_brevo_admin_deploy.py
  API_URL=https://your-api.railway.app python scripts/verify_brevo_admin_deploy.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    api_url = (os.getenv("API_URL") or os.getenv("NEXT_PUBLIC_API_URL") or "").rstrip("/")
    if not api_url:
        print("Set API_URL or NEXT_PUBLIC_API_URL to your Railway API base URL.", file=sys.stderr)
        return 1

    openapi_url = f"{api_url}/openapi.json"
    try:
        with urllib.request.urlopen(openapi_url, timeout=20) as resp:
            spec = json.load(resp)
    except urllib.error.HTTPError as exc:
        print(f"Failed to fetch {openapi_url}: HTTP {exc.code}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch {openapi_url}: {exc}", file=sys.stderr)
        return 1

    paths = spec.get("paths") or {}
    pull = paths.get("/api/admin/invites/pull-brevo") or {}
    sync = paths.get("/api/admin/invites/sync-brevo") or {}

    pull_params = {p.get("name") for p in (pull.get("post") or {}).get("parameters") or []}
    sync_params = {p.get("name") for p in (sync.get("post") or {}).get("parameters") or []}

    ok = True
    if "list_id" not in pull_params:
        print("MISSING: list_id on POST /api/admin/invites/pull-brevo — backend not deployed yet.")
        ok = False
    else:
        print("OK: pull-brevo accepts list_id")

    if "list_id" not in sync_params:
        print("MISSING: list_id on POST /api/admin/invites/sync-brevo — backend not deployed yet.")
        ok = False
    else:
        print("OK: sync-brevo accepts list_id")

    if ok:
        print(f"Brevo admin backend ready at {api_url}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
