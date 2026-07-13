"""One-shot per-user memory bootstrap for the self-improvement loop.

When a user links their first social account, this module seeds the two
memory files the reflection loop maintains:

- ``/memories/creative_guidelines.md`` — a stub the first reflection run
  replaces (the ``BOOTSTRAP_MARKER`` tells ``should_run_reflection`` to
  ignore the debounce for stubs).
- ``/memories/account_profile.md`` — account identity built from the
  tracked-account metadata. The live agent may edit it later via its
  memory tool, so bootstrap never overwrites an existing row.

Called best-effort from ``studio_service.sync_studio_connections_for_user``
after tracked accounts are materialized; every failure is swallowed by the
caller so the connection flow can never break on memory writes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from . import db as analytics_db

logger = logging.getLogger(__name__)

BOOTSTRAP_MARKER = "<!-- bootstrap:v1 -->"

GUIDELINES_PATH = "/memories/creative_guidelines.md"
ACCOUNT_PROFILE_PATH = "/memories/account_profile.md"

_MODEL_ROUTING_REFERENCE = """## Model Routing Reference

- `nano banana pro` — images
- `kling 3.0` — cinematic videos (no speech)
- `veo3.1` — UGC videos with speech
- `seedance 2.0` — app-promo / motion-graphics videos
- `infinitalk + elevenlabs` — AI clone videos"""


def build_guidelines_template(now: datetime) -> str:
    """Blank per-account rulebook. Pure — unit-testable without I/O."""
    date = now.date().isoformat()
    return f"""# Creative Guidelines
Last updated: {date} (bootstrap)
{BOOTSTRAP_MARKER}

No confirmed rules yet — guidelines will be populated after the first
analytics reflection cycle.

## Confirmed Rules

(none yet)

## Hypotheses

(none yet)

{_MODEL_ROUTING_REFERENCE}
"""


def build_account_profile(accounts: list[dict], now: datetime) -> str:
    """Account identity file from tracked-account metadata. Pure."""
    date = now.date().isoformat()
    lines = [
        "# Account Profile",
        f"Created: {date}. You (the agent) may refine this file via the",
        "memory tool as you learn more about the account.",
        "",
        "## Connected accounts",
        "",
    ]
    active = [a for a in accounts if a.get("is_active") is not False]
    if not active:
        lines.append("- (no linked accounts yet)")
    for acct in active:
        plat = (acct.get("platform") or "unknown").strip().lower()
        nick = (acct.get("username") or "unknown").strip().lower().lstrip("@")
        followers = int(acct.get("follower_count") or acct.get("followers") or 0)
        freq = acct.get("scrape_frequency") or "daily"
        follower_txt = f"{followers:,} followers" if followers else "followers unknown"
        lines.append(f"- {plat} @{nick} — {follower_txt}, scraped {freq}")
    lines.append("")
    return "\n".join(lines)


def bootstrap_user_memories(user_id: str) -> dict[str, bool]:
    """Create the two memory files when absent. Never overwrites.

    Returns which files were created this call, e.g.
    ``{"creative_guidelines": True, "account_profile": False}``.
    """
    created = {"creative_guidelines": False, "account_profile": False}
    if not user_id:
        return created

    now = datetime.now()
    try:
        accounts = analytics_db.list_tracked_accounts(user_id)
    except Exception as exc:
        logger.warning(
            "[analytics] bootstrap account lookup failed for %s: %s",
            user_id,
            exc,
        )
        accounts = []

    for key, path, builder in (
        ("creative_guidelines", GUIDELINES_PATH, lambda: build_guidelines_template(now)),
        ("account_profile", ACCOUNT_PROFILE_PATH, lambda: build_account_profile(accounts, now)),
    ):
        try:
            existing: Optional[dict] = analytics_db.get_agent_memory(user_id, path)
            if existing:
                continue
            analytics_db.upsert_agent_memory(user_id, path, builder())
            created[key] = True
            logger.info("[analytics] bootstrapped %s for user %s", path, user_id)
        except Exception as exc:
            logger.warning(
                "[analytics] bootstrap of %s failed for %s: %s", path, user_id, exc
            )

    return created
