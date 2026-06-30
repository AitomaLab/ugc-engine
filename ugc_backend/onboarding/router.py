"""Onboarding ICP responses — user submissions + admin review."""

from __future__ import annotations

import os
import traceback
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ugc_backend.auth import get_current_user
from ugc_db.db_manager import get_supabase

load_dotenv(".env.saas")

router = APIRouter(tags=["onboarding"])


def _require_admin(user: dict) -> None:
    """Raise 403 unless the caller is the configured admin email."""
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    caller = (user.get("email") or "").strip().lower()
    if not admin_email or caller != admin_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


class OnboardingSubmitBody(BaseModel):
    name: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    team_size: str = Field(..., min_length=1)
    challenge: str = Field(..., min_length=1)
    content_type: str = Field(..., min_length=1)
    monthly_volume: str = Field(..., min_length=1)
    ui_language: Optional[str] = None


@router.post("/submit")
def submit_onboarding(
    body: OnboardingSubmitBody,
    user: dict = Depends(get_current_user),
) -> dict:
    name_clean = (body.name or "").strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="Name is required.")

    row = {
        "user_id": user.get("id"),
        "name": name_clean,
        "email": user.get("email"),
        "role": body.role.strip(),
        "team_size": body.team_size.strip(),
        "challenge": body.challenge.strip(),
        "content_type": body.content_type.strip(),
        "monthly_volume": body.monthly_volume.strip(),
        "ui_language": (body.ui_language or "").strip() or None,
    }

    try:
        sb = get_supabase()
        sb.table("onboarding_responses").upsert(row, on_conflict="user_id").execute()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[onboarding] submit failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Could not submit onboarding responses.")


@router.get("/list")
def list_onboarding(
    user: dict = Depends(get_current_user),
) -> list:
    _require_admin(user)
    sb = get_supabase()
    out: list = []
    page = 1000
    start = 0
    while True:
        rows = (
            sb.table("onboarding_responses")
            .select("*")
            .order("completed_at", desc=True)
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
