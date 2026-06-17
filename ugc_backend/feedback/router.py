"""Feedback collection — beta tester submissions + admin review."""

from __future__ import annotations

import os
import traceback
import uuid
from typing import Literal, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from ugc_backend.auth import get_current_user, get_optional_user
from ugc_db.db_manager import get_supabase

load_dotenv(".env.saas")

router = APIRouter(tags=["feedback"])

_FEEDBACK_BUCKET = "feedback-images"
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_VALID_STATUSES = frozenset({"open", "complete", "archived"})


def _require_admin(user: dict) -> None:
    """Raise 403 unless the caller is the configured admin email."""
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    caller = (user.get("email") or "").strip().lower()
    if not admin_email or caller != admin_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


def _storage_key_from_public_url(image_url: str) -> Optional[str]:
    """Extract object key from a Supabase public storage URL."""
    try:
        path = urlparse(image_url).path
        marker = f"/object/public/{_FEEDBACK_BUCKET}/"
        idx = path.find(marker)
        if idx == -1:
            return None
        return path[idx + len(marker) :]
    except Exception:
        return None


class FeedbackStatusUpdate(BaseModel):
    status: Literal["open", "complete", "archived"]


@router.post("/submit")
async def submit_feedback(
    name: str = Form(...),
    message: str = Form(...),
    image: UploadFile | None = File(None),
    user: dict | None = Depends(get_optional_user),
) -> dict:
    name_clean = (name or "").strip()
    message_clean = (message or "").strip()
    if not name_clean or not message_clean:
        raise HTTPException(status_code=400, detail="Name and message are required.")

    image_url: Optional[str] = None
    try:
        if image and image.filename:
            contents = await image.read()
            if len(contents) > _MAX_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="Image too large (max 10 MB).")

            content_type = (image.content_type or "").lower()
            if not content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail=f"Expected image upload, got {content_type!r}")

            ext = "jpg"
            if "png" in content_type:
                ext = "png"
            elif "webp" in content_type:
                ext = "webp"
            elif "gif" in content_type:
                ext = "gif"
            elif "jpeg" in content_type or "jpg" in content_type:
                ext = "jpg"

            key = f"{uuid.uuid4()}.{ext}"
            sb = get_supabase()
            sb.storage.from_(_FEEDBACK_BUCKET).upload(
                key,
                contents,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            image_url = sb.storage.from_(_FEEDBACK_BUCKET).get_public_url(key)

        row = {
            "name": name_clean,
            "message": message_clean,
            "image_url": image_url,
        }
        if user:
            row["user_id"] = user.get("id")
            row["email"] = user.get("email")

        sb = get_supabase()
        sb.table("feedback").insert(row).execute()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[feedback] submit failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Could not submit feedback.")


@router.get("/list")
def list_feedback(
    status: Optional[str] = None,
    user: dict = Depends(get_current_user),
) -> list:
    _require_admin(user)
    sb = get_supabase()
    status_filter = (status or "").strip().lower()
    if status_filter and status_filter not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status filter.")

    out: list = []
    page = 1000
    start = 0
    while True:
        q = sb.table("feedback").select("*").order("created_at", desc=True)
        if status_filter:
            q = q.eq("status", status_filter)
        rows = q.range(start, start + page - 1).execute().data or []
        out.extend(rows)
        if len(rows) < page:
            break
        start += page
    return out


@router.patch("/{feedback_id}/status")
def update_feedback_status(
    feedback_id: str,
    body: FeedbackStatusUpdate,
    user: dict = Depends(get_current_user),
) -> dict:
    _require_admin(user)
    if body.status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status.")
    sb = get_supabase()
    sb.table("feedback").update({"status": body.status}).eq("id", feedback_id).execute()
    return {"ok": True}


@router.delete("/{feedback_id}")
def delete_feedback(
    feedback_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    _require_admin(user)
    sb = get_supabase()
    existing = sb.table("feedback").select("image_url").eq("id", feedback_id).execute()
    image_url = None
    if existing.data:
        image_url = existing.data[0].get("image_url")

    sb.table("feedback").delete().eq("id", feedback_id).execute()

    if image_url:
        key = _storage_key_from_public_url(image_url)
        if key:
            try:
                sb.storage.from_(_FEEDBACK_BUCKET).remove([key])
            except Exception as e:
                print(f"[feedback] storage delete skipped for {key}: {e}")

    return {"ok": True}
