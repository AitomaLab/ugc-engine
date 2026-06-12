"""FastAPI router for the hidden Admin console (gated beta invites).

Mounted in ``ugc_backend/main.py`` with::

    from ugc_backend.admin.router import router as admin_router
    app.include_router(admin_router, prefix="/api/admin")

Responsibilities:
  • Pull the Brevo waitlist into the ``invite_codes`` table (generating a
    unique ``BETA-XXXXXX`` code per contact email).
  • Manually mint codes for VCs / press / individuals.
  • List all codes.
  • Sync unsynced codes back to Brevo (writing ``INVITE_CODE`` on the
    contact, creating the contact first if it doesn't exist yet). Note this is
    a distinct attribute from ``REFERRAL_CODE`` (used by the sharing/queue
    mechanic).

Every endpoint requires an authenticated user via ``get_current_user`` AND
that the caller's email matches ``ADMIN_EMAIL`` (403 otherwise). Database
writes use the service-role client (``get_supabase``) so they bypass RLS.

This is a single-use invite system: each email gets exactly one code and there
is no multi-use or referral sharing.
"""

from __future__ import annotations

import os
import random
import string
import time
from typing import List, Optional
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ugc_backend.auth import get_current_user
from ugc_db.db_manager import get_supabase

load_dotenv(".env.saas")

router = APIRouter(tags=["admin"])

_BREVO_BASE = "https://api.brevo.com/v3"
_CODE_ALPHABET = string.ascii_uppercase + string.digits
_BREVO_PAGE_SIZE = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin(user: dict) -> None:
    """Raise 403 unless the caller is the configured admin email."""
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    caller = (user.get("email") or "").strip().lower()
    if not admin_email or caller != admin_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


def _brevo_key() -> str:
    key = os.getenv("BREVO_API_KEY")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BREVO_API_KEY is not configured on the server.",
        )
    return key


def _brevo_headers() -> dict:
    return {
        "api-key": _brevo_key(),
        "accept": "application/json",
        "Content-Type": "application/json",
    }


def _gen_code() -> str:
    """Generate a code like ``BETA-K7X2MQ``."""
    return "BETA-" + "".join(random.choices(_CODE_ALPHABET, k=6))


def _gen_unique_code(existing: set[str]) -> str:
    """Generate a code guaranteed not to collide with ``existing`` (mutates it)."""
    code = _gen_code()
    while code in existing:
        code = _gen_code()
    existing.add(code)
    return code


def _norm_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def _load_existing(sb) -> tuple[set[str], set[str]]:
    """Return (existing_emails_lowercased, existing_codes) from invite_codes.

    Paginates with ``range()`` because PostgREST caps a plain ``select`` at
    1000 rows — without this the dedup set is incomplete once the waitlist
    (2,600+ rows) has been imported, and inserts hit the unique constraint.
    """
    emails: set[str] = set()
    codes: set[str] = set()
    page = 1000
    start = 0
    while True:
        rows = (
            sb.table("invite_codes")
            .select("email, code")
            .range(start, start + page - 1)
            .execute()
            .data
            or []
        )
        for r in rows:
            if r.get("email"):
                emails.add(_norm_email(r.get("email")))
            if r.get("code"):
                codes.add(r["code"])
        if len(rows) < page:
            break
        start += page
    return emails, codes


def _insert_in_chunks(sb, rows: List[dict], chunk: int = 500) -> int:
    """Insert rows, skipping any that collide on the unique email constraint.

    Uses ``ON CONFLICT (email) DO NOTHING`` so a stray duplicate (e.g. a row
    added between the dedup read and this write) can't abort the whole batch.
    Returns the number of rows actually inserted.
    """
    inserted = 0
    for i in range(0, len(rows), chunk):
        res = (
            sb.table("invite_codes")
            .upsert(rows[i : i + chunk], on_conflict="email", ignore_duplicates=True)
            .execute()
        )
        inserted += len(res.data or [])
    return inserted


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    emails: List[str] = Field(default_factory=list)
    label: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/invites/pull-brevo")
def pull_brevo(user: dict = Depends(get_current_user)) -> dict:
    """Import every Brevo contact as a new invite code (skipping known emails)."""
    _require_admin(user)
    sb = get_supabase()

    existing_emails, existing_codes = _load_existing(sb)

    imported = 0
    skipped = 0
    new_rows: List[dict] = []

    headers = _brevo_headers()
    offset = 0
    with httpx.Client(timeout=30, trust_env=False) as client:
        while True:
            resp = client.get(
                f"{_BREVO_BASE}/contacts",
                headers=headers,
                params={"limit": _BREVO_PAGE_SIZE, "offset": offset},
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Brevo contacts fetch failed ({resp.status_code}): {resp.text[:300]}",
                )
            contacts = (resp.json() or {}).get("contacts", []) or []
            for c in contacts:
                email = _norm_email(c.get("email"))
                if not email or email in existing_emails:
                    skipped += 1
                    continue
                existing_emails.add(email)
                new_rows.append(
                    {
                        "email": email,
                        "code": _gen_unique_code(existing_codes),
                        "label": "Brevo Waitlist",
                    }
                )
                imported += 1
            if len(contacts) < _BREVO_PAGE_SIZE:
                break
            offset += _BREVO_PAGE_SIZE
            # Defensive cap so a misbehaving API can't loop forever.
            if offset > 500_000:
                break

    if new_rows:
        inserted = _insert_in_chunks(sb, new_rows)
        # Reconcile counts if any row slipped through as a duplicate.
        if inserted < imported:
            skipped += imported - inserted
            imported = inserted

    return {"imported": imported, "skipped": skipped}


@router.post("/invites/generate")
def generate_invites(
    body: GenerateRequest, user: dict = Depends(get_current_user)
) -> dict:
    """Mint codes for a pasted list of emails (skipping ones already present)."""
    _require_admin(user)
    sb = get_supabase()

    existing_emails, existing_codes = _load_existing(sb)
    label = (body.label or "").strip() or "Manual"

    created = 0
    skipped = 0
    seen_in_request: set[str] = set()
    new_rows: List[dict] = []
    for raw in body.emails:
        email = _norm_email(raw)
        if not email or "@" not in email:
            skipped += 1
            continue
        if email in existing_emails or email in seen_in_request:
            skipped += 1
            continue
        seen_in_request.add(email)
        new_rows.append(
            {
                "email": email,
                "code": _gen_unique_code(existing_codes),
                "label": label,
            }
        )
        created += 1

    if new_rows:
        inserted = _insert_in_chunks(sb, new_rows)
        # Reconcile counts if any row slipped through as a duplicate.
        if inserted < created:
            skipped += created - inserted
            created = inserted

    return {"created": created, "skipped": skipped}


@router.get("/invites")
def list_invites(user: dict = Depends(get_current_user)) -> list:
    """Return all invite codes, newest first (paginated past PostgREST's 1000 cap)."""
    _require_admin(user)
    sb = get_supabase()
    out: list = []
    page = 1000
    start = 0
    while True:
        rows = (
            sb.table("invite_codes")
            .select("*")
            .order("created_at", desc=True)
            .range(start, start + page - 1)
            .execute()
            .data
            or []
        )
        out.extend(rows)
        if len(rows) < page:
            break
        start += page
    return out


@router.post("/invites/sync-brevo")
def sync_brevo(user: dict = Depends(get_current_user)) -> dict:
    """Write each unsynced code into its Brevo contact's INVITE_CODE attribute."""
    _require_admin(user)
    sb = get_supabase()

    # Read the full unsynced backlog up front (paginated) so we have a stable
    # snapshot before we start flipping brevo_synced; PostgREST caps at 1000.
    # Only waitlist contacts are pushed — manually minted codes (VCs / press /
    # individuals) must never be written back to Brevo.
    rows: list = []
    page = 1000
    start = 0
    while True:
        batch = (
            sb.table("invite_codes")
            .select("id, email, code")
            .eq("brevo_synced", False)
            .eq("label", "Brevo Waitlist")
            .order("created_at", desc=False)
            .range(start, start + page - 1)
            .execute()
            .data
            or []
        )
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page

    headers = _brevo_headers()
    synced = 0
    failed = 0
    with httpx.Client(timeout=30, trust_env=False) as client:
        for r in rows:
            email = _norm_email(r.get("email"))
            code = r.get("code")
            if not email or not code:
                failed += 1
                continue
            try:
                encoded = quote(email, safe="")
                patch = client.patch(
                    f"{_BREVO_BASE}/contacts/{encoded}",
                    headers=headers,
                    json={"attributes": {"INVITE_CODE": code}},
                )
                ok = patch.status_code in (200, 204)
                if patch.status_code == 404:
                    created = client.post(
                        f"{_BREVO_BASE}/contacts",
                        headers=headers,
                        json={"email": email, "attributes": {"INVITE_CODE": code}},
                    )
                    ok = created.status_code in (200, 201, 204)
                if ok:
                    sb.table("invite_codes").update({"brevo_synced": True}).eq(
                        "id", r["id"]
                    ).execute()
                    synced += 1
                else:
                    failed += 1
            except Exception:  # noqa: BLE001 — record + continue
                failed += 1
            # Respect Brevo rate limits.
            time.sleep(0.1)

    return {"synced": synced, "failed": failed}
