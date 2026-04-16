"""
Creative OS — Projects Router

Proxies project data from the core API.
Enriches project list with recent asset previews.
"""
import asyncio
import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from openai import AsyncOpenAI
from auth import get_current_user
from core_api_client import CoreAPIClient


class GenerateNameRequest(BaseModel):
    prompt: str

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Internal helpers for fetching project-scoped images & videos ─────────

async def _build_influencer_map(client: CoreAPIClient) -> dict:
    """Build an {id: name} lookup from the user's influencers. Cached per request."""
    try:
        influencers = await client.list_influencers()
        return {inf["id"]: inf.get("name", "") for inf in influencers}
    except Exception:
        return {}


def _mode_label_from_model_api(model_api: str) -> str:
    """Map model_api string to a human-readable mode label."""
    if not model_api:
        return ""
    lower = model_api.lower()
    if any(k in lower for k in ("kling", "kie", "wavespeed")):
        return "UGC"
    if any(k in lower for k in ("veo", "cinematic")):
        return "Cinematic"
    return ""


def _mode_label_from_shot_type(shot_type: str) -> str:
    """Map shot_type to a human-readable mode label."""
    if not shot_type:
        return ""
    st = shot_type.lower()
    if st in ("ugc",):
        return "UGC"
    if st in ("cinematic",):
        return "Cinematic"
    if st in ("iphone_look", "iphone"):
        return "iPhone"
    if st in ("luxury",):
        return "Luxury"
    return shot_type.replace("_", " ").title()


async def _fetch_project_images(client: CoreAPIClient, influencer_map: dict | None = None) -> list:
    """Fetch all generated images (product shots) for the current project scope.
    Uses 2 fast queries: 1) get product IDs, 2) batch-fetch all shots in one Supabase call.
    Also includes standalone shots (no product_id) that have project_id set directly.

    Enriches each shot with:
    - product_name (from products list)
    - influencer_name (resolved from analysis_json.influencer_id)
    - mode (mapped from shot_type)
    """
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    if not client.project_id:
        return []

    from env_loader import load_env
    load_env(Path(__file__))
    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    # 1. Get product IDs for this project (fast — single core API call)
    products = await client.list_products()
    product_ids = [p["id"] for p in products] if products else []

    # Build influencer map if not passed
    if influencer_map is None:
        influencer_map = await _build_influencer_map(client)

    # 2. Batch-fetch shots via Supabase — single query with IN filter
    all_shots = []
    if supabase_url and anon_key:
        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {client.token}",
            "Content-Type": "application/json",
        }
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as http:
            fetches = []
            # Shots linked via product_id
            if product_ids:
                ids_str = ",".join(product_ids)
                fetches.append(http.get(
                    f"{supabase_url}/rest/v1/product_shots",
                    headers=headers,
                    params={"product_id": f"in.({ids_str})", "order": "created_at.desc"},
                ))
            # Standalone shots linked via project_id directly
            fetches.append(http.get(
                f"{supabase_url}/rest/v1/product_shots",
                headers=headers,
                params={"project_id": f"eq.{client.project_id}", "order": "created_at.desc"},
            ))
            results = await asyncio.gather(*fetches, return_exceptions=True)

            seen_ids = set()
            for resp in results:
                if isinstance(resp, Exception) or resp.status_code != 200:
                    continue
                for shot in resp.json():
                    sid = shot.get("id")
                    if sid and sid not in seen_ids:
                        seen_ids.add(sid)
                        # Enrich with product name
                        pid = shot.get("product_id")
                        if pid and products:
                            match = next((p for p in products if p["id"] == pid), None)
                            if match:
                                shot["product_name"] = match.get("name", "")
                        # Enrich with influencer name
                        # Check analysis_json.influencer_id first, then top-level influencer_id
                        analysis = shot.get("analysis_json") or {}
                        inf_id = analysis.get("influencer_id") or shot.get("influencer_id")
                        if inf_id and inf_id in influencer_map:
                            shot["influencer_name"] = influencer_map[inf_id]
                        # Enrich with mode — analysis_json.mode is the true source
                        # (shot_type may be "iphone_look" even for luxury mode)
                        real_mode = analysis.get("mode") or shot.get("shot_type", "")
                        mode = _mode_label_from_shot_type(real_mode)
                        if mode:
                            shot["mode"] = mode
                        all_shots.append(shot)
    else:
        # Fallback: N parallel calls via core API
        shot_results = await asyncio.gather(
            *(client.list_product_shots(p["id"]) for p in products),
            return_exceptions=True,
        )
        for product, shots in zip(products, shot_results):
            if isinstance(shots, Exception):
                continue
            for shot in shots:
                shot["product_name"] = product.get("name", "")
                # Enrich influencer + mode in fallback path too
                analysis = shot.get("analysis_json") or {}
                inf_id = analysis.get("influencer_id") or shot.get("influencer_id")
                if inf_id and inf_id in influencer_map:
                    shot["influencer_name"] = influencer_map[inf_id]
                real_mode = analysis.get("mode") or shot.get("shot_type", "")
                mode = _mode_label_from_shot_type(real_mode)
                if mode:
                    shot["mode"] = mode
            all_shots.extend(shots)

    all_shots.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return all_shots


async def _fetch_project_videos(client: CoreAPIClient, influencer_map: dict | None = None) -> list:
    """Fetch all videos (completed + processing) for the current project scope.

    Enriches each job with:
    - product_name (resolved from product_id)
    - influencer_name (resolved from influencer_id)
    - mode (mapped from model_api)
    """
    jobs = await client.list_jobs(limit=200)

    # Build lookup maps if not passed
    if influencer_map is None:
        influencer_map = await _build_influencer_map(client)

    # Build product map {id: name}
    try:
        products = await client.list_products()
        product_map = {p["id"]: p.get("name", "") for p in products} if products else {}
    except Exception:
        product_map = {}

    filtered = []
    for j in jobs:
        if (j.get("status") == "success" and j.get("final_video_url")) \
                or j.get("status") in ("processing", "generating", "pending"):
            # Enrich with product name
            pid = j.get("product_id")
            if pid and pid in product_map:
                j["product_name"] = product_map[pid]
            # Enrich with influencer name
            inf_id = j.get("influencer_id")
            if inf_id and inf_id in influencer_map:
                j["influencer_name"] = influencer_map[inf_id]
            # Enrich with mode label
            model_api = j.get("model_api", "")
            mode = _mode_label_from_model_api(model_api)
            if mode:
                j["mode"] = mode
            filtered.append(j)
    return filtered


async def _get_project_previews(client: CoreAPIClient, project_id: str) -> dict:
    """Fetch recent asset previews and counts for a single project.
    Uses the exact same logic as the project detail page tabs.
    """
    scoped = CoreAPIClient(token=client.token, project_id=project_id)

    try:
        images, videos = await asyncio.gather(
            _fetch_project_images(scoped),
            _fetch_project_videos(scoped),
            return_exceptions=True,
        )

        if isinstance(images, Exception):
            images = []
        if isinstance(videos, Exception):
            videos = []

        # Build preview thumbnails (images first, then video thumbnails)
        previews = []

        # 1. Generated images (product shots)
        for img in images:
            url = img.get("image_url") or img.get("result_url")
            if url and len(previews) < 4:
                previews.append({"url": url, "type": "image"})

        # 2. Video preview thumbnails (only actual image previews, not .mp4)
        for vid in videos:
            if len(previews) >= 4:
                break
            url = vid.get("preview_url")
            if url and not url.endswith(('.mp4', '.webm', '.mov')):
                previews.append({"url": url, "type": "video"})

        # Counts match what the detail page shows
        completed_videos = [v for v in videos if v.get("status") == "success"]

        return {
            "recent_previews": previews[:4],
            "asset_counts": {
                "images": len(images),
                "videos": len(completed_videos),
            },
        }
    except Exception as e:
        print(f"[Projects] Preview fetch failed for {project_id}: {e}")
        return {
            "recent_previews": [],
            "asset_counts": {"images": 0, "videos": 0},
        }


@router.get("/")
async def list_projects(user: dict = Depends(get_current_user)):
    """List all projects with recent asset previews."""
    client = CoreAPIClient(token=user["token"])
    projects = await client.list_projects()

    # Enrich each project with previews (concurrently)
    preview_results = await asyncio.gather(
        *[_get_project_previews(client, p["id"]) for p in projects],
        return_exceptions=True,
    )

    for project, result in zip(projects, preview_results):
        if isinstance(result, Exception):
            project["recent_previews"] = []
            project["asset_counts"] = {"images": 0, "videos": 0}
        else:
            project["recent_previews"] = result["recent_previews"]
            project["asset_counts"] = result["asset_counts"]

    return projects


@router.post("/")
async def create_project(data: dict, user: dict = Depends(get_current_user)):
    """Create a new project."""
    name = data.get("name", "").strip()
    if not name:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Project name is required")
    client = CoreAPIClient(token=user["token"])
    return await client.create_project(name)


@router.post("/generate-name")
async def generate_project_name(
    request: GenerateNameRequest,
    user: dict = Depends(get_current_user),
):
    """
    Generate a concise 2-4 word project name from a user's prompt.
    Uses GPT-4o-mini for speed and cost efficiency.
    Falls back to 'New Project' on any error.
    """
    prompt = request.prompt.strip()
    if not prompt:
        return {"name": "New Project"}

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[Projects] OPENAI_API_KEY not set, using fallback name")
            return {"name": "New Project"}

        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a naming assistant. The user will describe a creative video or content project. "
                        "Extract a concise, memorable 2-4 word project name. "
                        "Rules: no quotes, no punctuation, no articles (a/an/the), title case. "
                        "Examples: 'Summer Campaign', 'Product Launch Reel', 'Luxury Skincare Spot'."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=20,
            temperature=0.7,
        )
        raw = response.choices[0].message.content or ""
        name = raw.strip().strip('"').strip("'").strip()
        return {"name": name or "New Project"}

    except Exception as e:
        print(f"[Projects] Name generation failed: {e}")
        return {"name": "New Project"}


@router.put("/{project_id}")
async def rename_project(project_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Rename a project."""
    name = data.get("name", "").strip()
    if not name:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Project name is required")
    client = CoreAPIClient(token=user["token"])
    return await client.rename_project(project_id, name)


@router.get("/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    """Get a single project with its assets summary."""
    client = CoreAPIClient(token=user["token"], project_id=project_id)

    # Fetch project, images, videos in parallel
    project, images, videos = await asyncio.gather(
        client.get_project(project_id),
        _fetch_project_images(client),
        _fetch_project_videos(client),
    )

    if not project:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Project not found")

    completed_videos = [v for v in videos if v.get("status") == "success"]

    project["asset_counts"] = {
        "images": len(images),
        "videos": len(completed_videos),
    }

    return project


@router.get("/{project_id}/assets/images")
async def list_project_images(project_id: str, user: dict = Depends(get_current_user)):
    """List all image assets (product shots) for a project."""
    client = CoreAPIClient(token=user["token"], project_id=project_id)
    return await _fetch_project_images(client)


@router.get("/{project_id}/assets/videos")
async def list_project_videos(project_id: str, user: dict = Depends(get_current_user)):
    """List all video assets (jobs) for a project."""
    client = CoreAPIClient(token=user["token"], project_id=project_id)
    return await _fetch_project_videos(client)


@router.delete("/{project_id}/assets/images/{shot_id}")
async def delete_project_image(project_id: str, shot_id: str, user: dict = Depends(get_current_user)):
    """Delete a single image (product shot) from a project."""
    client = CoreAPIClient(token=user["token"], project_id=project_id)
    return await client.delete_shot(shot_id)


@router.delete("/{project_id}/assets/videos/{job_id}")
async def delete_project_video(project_id: str, job_id: str, user: dict = Depends(get_current_user)):
    """Delete a single video (job) from a project."""
    client = CoreAPIClient(token=user["token"], project_id=project_id)
    return await client.delete_job(job_id)


@router.post("/{project_id}/assets/bulk-delete")
async def bulk_delete_assets(project_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Bulk delete images and/or videos from a project.
    
    Body: { "image_ids": [...], "video_ids": [...] }
    """
    client = CoreAPIClient(token=user["token"], project_id=project_id)
    image_ids = data.get("image_ids", [])
    video_ids = data.get("video_ids", [])

    results = await asyncio.gather(
        *(client.delete_shot(sid) for sid in image_ids),
        *(client.delete_job(vid) for vid in video_ids),
        return_exceptions=True,
    )

    deleted = sum(1 for r in results if not isinstance(r, Exception))
    failed = sum(1 for r in results if isinstance(r, Exception))
    return {"deleted": deleted, "failed": failed, "total": len(image_ids) + len(video_ids)}


@router.patch("/{project_id}/assets/images/{shot_id}")
async def rename_project_image(project_id: str, shot_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Rename an image (product shot) — updates product_name in product_shots."""
    name = (data.get("name") or "").strip()
    if not name:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="name is required")
    client = CoreAPIClient(token=user["token"], project_id=project_id)
    return await client.update_shot(shot_id, {"product_name": name})


@router.patch("/{project_id}/assets/videos/{job_id}")
async def rename_project_video(project_id: str, job_id: str, data: dict, user: dict = Depends(get_current_user)):
    """Rename a video (job) — updates campaign_name in video_jobs."""
    name = (data.get("name") or "").strip()
    if not name:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="name is required")
    # Update directly via Supabase REST (core API has no PATCH /jobs/:id)
    import os
    from supabase import create_client
    sb = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
    )
    result = sb.table("video_jobs").update({"campaign_name": name}).eq("id", job_id).execute()
    return result.data[0] if result.data else {"id": job_id, "campaign_name": name}
