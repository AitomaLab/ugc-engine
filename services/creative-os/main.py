"""
Aitoma Studio Creative OS — Microservice

Isolated FastAPI service running on port 8001.
Communicates with the core UGC backend (port 8000) exclusively via HTTP.
Never touches the database directly.
"""
import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Ensure service directory is on the path for local imports
sys.path.insert(0, str(Path(__file__).parent))

# Load env
from env_loader import load_env
load_env(Path(__file__))

print(f"[Creative OS] CORE_API_URL = {os.getenv('CORE_API_URL', 'NOT SET')}")

# ── App ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Aitoma Studio Creative OS",
    description="Project-based creative workspace microservice",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

# ── CORS ────────────────────────────────────────────────────────────────
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────
from routers.projects import router as projects_router
from routers.generate_image import router as image_router
from routers.generate_video import router as video_router
from routers.animate import router as animate_router
from routers.agent import router as agent_router

app.include_router(projects_router, prefix="/creative-os")
app.include_router(image_router, prefix="/creative-os")
app.include_router(video_router, prefix="/creative-os")
app.include_router(animate_router, prefix="/creative-os")
app.include_router(agent_router, prefix="/creative-os")


# ── Upload Endpoint (server-side, bypasses RLS) ────────────────────────
from fastapi import Depends
from auth import get_current_user


@app.post("/creative-os/upload/image")
async def upload_image_base64(request: dict, user: dict = Depends(get_current_user)):
    """Upload a base64 image to Supabase Storage.

    Body: { "data": "data:image/png;base64,iVBOR..." }
    Returns: { "url": "https://...supabase.co/.../filename.png" }
    """
    import base64
    import uuid

    data_url = request.get("data", "")
    if not data_url or "base64," not in data_url:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid base64 data URL")

    # Parse data URL
    header, b64_data = data_url.split("base64,", 1)
    content_type = header.split(":")[1].split(";")[0] if ":" in header else "image/png"
    ext = content_type.split("/")[-1].replace("jpeg", "jpg")

    image_bytes = base64.b64decode(b64_data)
    filename = f"upload_{uuid.uuid4().hex[:12]}.{ext}"

    # Upload via service key (no RLS issues)
    try:
        from ugc_db.db_manager import get_supabase
        sb = get_supabase()
        sb.storage.from_("user-uploads").upload(
            filename, image_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        url = sb.storage.from_("user-uploads").get_public_url(filename)
        print(f"[Upload] OK: {filename} ({len(image_bytes)} bytes) → {url[:80]}...")
        return {"url": url}
    except Exception as e:
        print(f"[Upload] FAILED: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)[:200]}")


from fastapi import File, HTTPException, UploadFile


@app.post("/creative-os/upload/file")
async def upload_file_multipart(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),  # noqa: ARG001  (auth gate)
):
    """Upload an image or video to Supabase Storage via multipart form data.

    Used by the Agent panel attach button. Returns {url, type, name, size}
    where type is 'image' | 'video' so the frontend can render the right
    preview and tag the agent ref correctly.
    """
    import uuid

    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type.startswith("image/"):
        kind = "image"
    elif content_type.startswith("video/"):
        kind = "video"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Only images and videos are allowed.",
        )

    contents = await file.read()
    max_bytes = 100 * 1024 * 1024  # 100 MB
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large (max 100 MB).")

    # Build a safe filename: kind/upload_<uuid>.<ext>
    orig_name = file.filename or ""
    ext = ""
    if "." in orig_name:
        ext = orig_name.rsplit(".", 1)[-1].lower()
    if not ext:
        ext = content_type.split("/")[-1].replace("jpeg", "jpg")
    filename = f"agent_uploads/upload_{uuid.uuid4().hex[:12]}.{ext}"

    try:
        from ugc_db.db_manager import get_supabase
        sb = get_supabase()
        sb.storage.from_("user-uploads").upload(
            filename, contents,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        url = sb.storage.from_("user-uploads").get_public_url(filename)
        print(f"[Upload] {kind} {filename} ({len(contents)} bytes) → {url[:80]}…")
        return {"url": url, "type": kind, "name": orig_name or filename, "size": len(contents)}
    except Exception as e:
        from fastapi import HTTPException
        print(f"[Upload] FAILED: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)[:200]}")


# ── Health Check ────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "creative-os",
        "version": "1.0.0",
        "core_api_url": os.getenv("CORE_API_URL", "NOT SET"),
    }


@app.get("/creative-os/config")
async def get_config():
    """Return frontend-safe configuration (no secrets)."""
    from services.model_router import IMAGE_MODES, VIDEO_MODES, DIRECTOR_STYLES, UGC_STYLES

    return {
        "image_modes": [
            {"id": k, "label": v["description"]}
            for k, v in IMAGE_MODES.items()
        ],
        "video_modes": [
            {"id": k, "label": v["description"], "clip_lengths": v["clip_lengths"]}
            for k, v in VIDEO_MODES.items()
        ],
        "animation_styles": {
            "director": [
                {"id": s, "label": s.replace("_", " ").title()}
                for s in sorted(DIRECTOR_STYLES)
            ],
            "ugc": [
                {"id": s, "label": s.replace("_", " ").title()}
                for s in sorted(UGC_STYLES)
            ],
        },
    }


# ── Run ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        reload_dirs=[str(Path(__file__).parent)],
    )
