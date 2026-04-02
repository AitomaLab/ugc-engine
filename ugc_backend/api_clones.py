"""
ugc_backend/api_clones.py

AI Clone API Router — CRUD for clone profiles and looks,
plus AI look generation via Flux Kontext Pro (Kie.ai).

This router has NO dependency on the standard video generation pipeline.
"""
import os
import time
import json
import requests as _req
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ugc_db.db_manager import get_supabase
from ugc_backend.auth import get_optional_user

router = APIRouter(prefix="/api/clones", tags=["AI Clones"])

KIE_API_URL = os.getenv("KIE_API_URL", "https://api.kie.ai")
KIE_HEADERS = {
    "Authorization": f"Bearer {os.getenv('KIE_API_KEY', '')}",
    "Content-Type": "application/json",
}


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic request models
# ─────────────────────────────────────────────────────────────────────────────

class CloneCreate(BaseModel):
    name: str = "My AI Clone"
    elevenlabs_voice_id: str
    gender: str = "male"

class CloneUpdate(BaseModel):
    name: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    gender: Optional[str] = None

class LookCreate(BaseModel):
    clone_id: str
    label: str = "Look"
    image_url: str
    is_base: bool = False

class GenerateLookRequest(BaseModel):
    clone_id: str
    base_look_id: str       # look_id of the base photo to transform
    prompt: str             # e.g. "standing in a modern office, wearing a blazer"
    label: str = "AI Generated Look"


# ─────────────────────────────────────────────────────────────────────────────
# Clone CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
def list_clones(user: dict = Depends(get_optional_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    result = (
        sb.table("user_ai_clones")
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@router.post("")
def create_clone(data: CloneCreate, user: dict = Depends(get_optional_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    row = {
        "user_id": user["id"],
        "name": data.name,
        "elevenlabs_voice_id": data.elevenlabs_voice_id,
        "gender": data.gender,
    }
    result = sb.table("user_ai_clones").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create clone")
    return result.data[0]


@router.patch("/{clone_id}")
def update_clone(clone_id: str, data: CloneUpdate, user: dict = Depends(get_optional_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = (
        sb.table("user_ai_clones")
        .update(updates)
        .eq("id", clone_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Clone not found")
    return result.data[0]


@router.delete("/{clone_id}")
def delete_clone(clone_id: str, user: dict = Depends(get_optional_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    sb.table("user_ai_clones").delete().eq("id", clone_id).eq("user_id", user["id"]).execute()
    return {"status": "deleted"}


# ─────────────────────────────────────────────────────────────────────────────
# Look CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{clone_id}/looks")
def list_looks(clone_id: str, user: dict = Depends(get_optional_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    result = (
        sb.table("user_ai_clone_looks")
        .select("*")
        .eq("clone_id", clone_id)
        .eq("user_id", user["id"])
        .order("created_at")
        .execute()
    )
    return result.data or []


@router.post("/looks")
def add_look(data: LookCreate, user: dict = Depends(get_optional_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    row = {
        "clone_id": data.clone_id,
        "user_id": user["id"],
        "label": data.label,
        "image_url": data.image_url,
        "is_base": data.is_base,
    }
    result = sb.table("user_ai_clone_looks").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to add look")
    return result.data[0]


@router.delete("/looks/{look_id}")
def delete_look(look_id: str, user: dict = Depends(get_optional_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    sb.table("user_ai_clone_looks").delete().eq("id", look_id).eq("user_id", user["id"]).execute()
    return {"status": "deleted"}


# ─────────────────────────────────────────────────────────────────────────────
# AI Look Generation — Flux-2 Pro Image-to-Image via Kie.ai (Async)
# ─────────────────────────────────────────────────────────────────────────────

import threading
import logging

logger = logging.getLogger(__name__)


def _poll_kie_and_update_look(task_id: str, look_id: str):
    """Background thread: polls Kie.ai until the image is ready, then updates the DB row."""
    sb = get_supabase()
    for i in range(60):  # up to 5 minutes (60 × 5s)
        time.sleep(5)
        try:
            poll = _req.get(
                f"{KIE_API_URL}/api/v1/jobs/recordInfo",
                headers=KIE_HEADERS,
                params={"taskId": task_id},
                timeout=30,
            )
            poll_data = poll.json()
        except Exception as exc:
            logger.warning(f"Look {look_id}: poll error on attempt {i}: {exc}")
            continue

        if poll_data.get("code") != 200:
            continue

        d = poll_data.get("data", {})
        state = d.get("state", "processing").lower()

        if state == "success":
            # Kie.ai returns results in "resultJson" (JSON string) or "response"
            response_obj = d.get("resultJson") or d.get("response") or {}
            if isinstance(response_obj, str):
                try:
                    response_obj = json.loads(response_obj)
                except Exception:
                    response_obj = {}
            image_url = (
                response_obj.get("imageUrl")
                or response_obj.get("image_url")
                or (response_obj.get("resultUrls") or [None])[0]
            )
            if image_url:
                sb.table("user_ai_clone_looks").update({"image_url": image_url}).eq("id", look_id).execute()
                logger.info(f"Look {look_id}: image ready → {image_url[:80]}")
                return
        elif state == "fail":
            # Mark as failed by setting a special URL the frontend can detect
            sb.table("user_ai_clone_looks").update({"image_url": "error"}).eq("id", look_id).execute()
            logger.error(f"Look {look_id}: Kie.ai generation failed: {d.get('failMsg')}")
            return

    # Timed out — mark as error
    sb.table("user_ai_clone_looks").update({"image_url": "error"}).eq("id", look_id).execute()
    logger.error(f"Look {look_id}: timed out after 5 minutes")


@router.post("/looks/generate")
def generate_look(data: GenerateLookRequest, user: dict = Depends(get_optional_user)):
    """
    Submits a Flux-2 Pro Image-to-Image job to Kie.ai, inserts a pending look
    row (image_url=null), and starts a background thread to poll for completion.

    Returns immediately so the UI can show a loading placeholder.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    sb = get_supabase()

    # Fetch the base look to get its image URL
    look_result = (
        sb.table("user_ai_clone_looks")
        .select("*")
        .eq("id", data.base_look_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not look_result.data:
        raise HTTPException(status_code=404, detail="Base look not found")
    base_image_url = look_result.data[0]["image_url"]

    # Build the Flux-2 Pro Image-to-Image payload
    full_prompt = (
        f"Keep the person's face, skin tone, and facial features exactly identical. "
        f"Change only the outfit and background: {data.prompt}. "
        f"Photorealistic portrait, 9:16 vertical format, soft natural lighting, "
        f"sharp focus on face, bokeh background."
    )

    payload = {
        "model": "flux-2/pro-image-to-image",
        "input": {
            "prompt": full_prompt,
            "input_urls": [base_image_url],
            "aspect_ratio": "9:16",
            "resolution": "2K",
            "output_format": "jpeg",
        },
    }

    # Submit the job to Kie.ai
    try:
        resp = _req.post(
            f"{KIE_API_URL}/api/v1/jobs/createTask",
            headers=KIE_HEADERS,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Kie.ai submission failed: {e}")

    api_result = resp.json()
    if api_result.get("code") != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Kie.ai error: {api_result.get('msg', str(api_result))}"
        )

    task_id = api_result["data"]["taskId"]

    # Insert a pending look row (image_url=None means still generating)
    row = {
        "clone_id": data.clone_id,
        "user_id": user["id"],
        "label": data.label,
        "image_url": "pending",
        "is_base": False,
    }
    result = sb.table("user_ai_clone_looks").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create look record")

    new_look = result.data[0]

    # Start background polling thread
    thread = threading.Thread(
        target=_poll_kie_and_update_look,
        args=(task_id, new_look["id"]),
        daemon=True,
    )
    thread.start()

    # Return immediately with the pending look
    return new_look


@router.get("/looks/{look_id}")
def get_look_status(look_id: str, user: dict = Depends(get_optional_user)):
    """Returns a single look row — the frontend polls this to detect when image_url is populated."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    result = (
        sb.table("user_ai_clone_looks")
        .select("*")
        .eq("id", look_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Look not found")
    return result.data[0]

