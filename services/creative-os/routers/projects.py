"""
Creative OS — Projects Router

Proxies project data from the core API.
Enriches project list with recent asset previews.
"""
import asyncio
import os
import time
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from openai import AsyncOpenAI
from auth import get_current_user
from core_api_client import CoreAPIClient


class GenerateNameRequest(BaseModel):
    prompt: str

router = APIRouter(prefix="/projects", tags=["projects"])


# ── In-process TTL cache for user-level lookups ──────────────────────────
# Products and influencers change infrequently relative to read traffic but
# are pulled on almost every project endpoint. A 30s TTL bounded by the
# user's auth token absorbs the typical UI burst (project list → open project
# → poll) into a single upstream call while staying fresh enough that newly
# added influencers/products appear within half a minute.
_CACHE_TTL_SECONDS = 30
_user_cache: dict[tuple[str, str], tuple[float, object]] = {}


def _cache_key(token: str, kind: str) -> tuple[str, str]:
    # Token suffix is enough to dedupe across users without storing the full secret as a hash.
    return (token[-32:] if token else "", kind)


async def _cached(token: str, kind: str, loader):
    key = _cache_key(token, kind)
    now = time.time()
    cached = _user_cache.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]
    value = await loader()
    _user_cache[key] = (now, value)
    # Best-effort size cap to avoid unbounded growth in long-lived processes.
    if len(_user_cache) > 5000:
        for k in list(_user_cache.keys())[:1000]:
            _user_cache.pop(k, None)
    return value


async def _cached_list_products(client: CoreAPIClient) -> list:
    try:
        return await _cached(client.token, "products", client.list_products) or []
    except Exception:
        return []


async def _build_influencer_map(client: CoreAPIClient) -> dict:
    """Build an {id: name} lookup from the user's influencers. TTL-cached across
    requests so back-to-back project endpoints in a single page load don't each
    re-pull the influencer list."""
    async def _loader():
        try:
            influencers = await client.list_influencers()
            return {inf["id"]: inf.get("name", "") for inf in influencers}
        except Exception:
            return {}
    return await _cached(client.token, "influencer_map", _loader)


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


async def _fetch_project_images(
    client: CoreAPIClient,
    influencer_map: dict | None = None,
    products: list | None = None,
) -> list:
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

    # 1. Get product IDs for this project (fast — single core API call).
    # The caller can pass a pre-fetched products list to avoid a duplicate
    # round-trip when this helper is invoked alongside _fetch_project_videos.
    if products is None:
        products = await _cached_list_products(client)
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


async def _heal_assets_for_client(
    client: CoreAPIClient,
    images: list | None = None,
    videos: list | None = None,
) -> tuple[list, list]:
    """Best-effort: mirror any non-Supabase asset URLs and update DB rows."""
    from utils.persist_media import heal_asset_rows

    imgs = list(images or [])
    vids = list(videos or [])

    async def _update_shot(shot_id: str, data: dict):
        await client.update_shot(shot_id, data)

    async def _update_job(job_id: str, data: dict):
        await client.update_job(job_id, data)

    return await heal_asset_rows(
        imgs,
        vids,
        update_shot_fn=_update_shot,
        update_job_fn=_update_job,
    )


async def _fetch_project_videos(
    client: CoreAPIClient,
    influencer_map: dict | None = None,
    products: list | None = None,
) -> list:
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

    # Build product map {id: name}. Reuse caller-supplied list when given.
    try:
        if products is None:
            products = await _cached_list_products(client)
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

        # 2. Video preview thumbnails — prefer an image thumbnail, fall back
        #    to the first-frame reference image sent into the generation.
        def _pick_video_thumb(vid: dict) -> Optional[str]:
            for key in ("preview_url", "reference_image_url", "thumbnail_url"):
                url = vid.get(key)
                if url and not str(url).lower().endswith(('.mp4', '.webm', '.mov')):
                    return url
            return None

        for vid in videos:
            if len(previews) >= 4:
                break
            if vid.get("status") != "success":
                continue
            url = _pick_video_thumb(vid)
            if url:
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


def _pick_video_thumb(vid: dict) -> Optional[str]:
    """Return a preview URL for a video job. Prefers image thumbnails, falls back
    to the raw video URL (rendered as <video preload=metadata> on the frontend)
    so video-only projects still show a card preview."""
    for key in ("preview_url", "reference_image_url", "thumbnail_url"):
        url = vid.get(key)
        if url and not str(url).lower().endswith(('.mp4', '.webm', '.mov')):
            return url
    return vid.get("final_video_url")


async def _bulk_project_previews(
    client: CoreAPIClient,
    projects: list[dict],
) -> dict[str, dict]:
    """Build {project_id: {recent_previews, asset_counts}} for all projects using
    at most 3 network calls total, regardless of project count.

    Prior implementation fanned out 2N round-trips (list_jobs + product_shots per
    project); this version fetches everything once and buckets per-project in
    Python, cutting the dashboard list endpoint from ~10s to under 1s.
    """
    from pathlib import Path
    from env_loader import load_env
    load_env(Path(__file__))

    project_ids = [p["id"] for p in projects if p.get("id")]
    out: dict[str, dict] = {
        pid: {"recent_previews": [], "asset_counts": {"images": 0, "videos": 0}}
        for pid in project_ids
    }
    if not project_ids:
        return out

    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    # Issue the three bulk queries concurrently. We need `list_products` so we
    # can map shots-linked-by-product-id back to their owning project (legacy
    # shots don't always have project_id populated on the row itself).
    async def _fetch_all_jobs():
        try:
            # Must bypass default-project fallback so jobs from non-default
            # projects (e.g. "Modelo En Acción") are included in the bulk pull.
            cross_project = CoreAPIClient(token=client.token, skip_project_scope=True)
            return await cross_project.list_jobs(limit=200)
        except Exception:
            return []

    async def _fetch_all_products() -> list[dict]:
        """Single bulk fetch of products for all projects via Supabase REST —
        replaces a 19-round-trip per-project fan-out through the core API.
        We only need (id, project_id) to route shots-by-product back to
        projects; the `product_id IN (...)` shot query below uses these keys.
        """
        if not (supabase_url and anon_key):
            return []
        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {client.token}",
            "Content-Type": "application/json",
        }
        import httpx as _httpx
        try:
            async with _httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.get(
                    f"{supabase_url}/rest/v1/products",
                    headers=headers,
                    params={
                        "select": "id,project_id",
                        "project_id": f"in.({','.join(project_ids)})",
                        "limit": "1000",
                    },
                )
                if resp.status_code != 200:
                    return []
                return resp.json() or []
        except Exception:
            return []

    async def _fetch_all_shots() -> list:
        # Single bulk query: every shot that matters for the cards has project_id
        # set on the row directly (backfilled by migration 023 and enforced for
        # all new shots). The prior dual-query (also filtering by product_id IN
        # (...)) returned heavily overlapping rows and doubled Supabase load
        # for no incremental coverage.
        if not (supabase_url and anon_key):
            return []
        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {client.token}",
            "Content-Type": "application/json",
        }
        import httpx as _httpx
        try:
            async with _httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.get(
                    f"{supabase_url}/rest/v1/product_shots",
                    headers=headers,
                    params={
                        "project_id": f"in.({','.join(project_ids)})",
                        "order": "created_at.desc",
                        "limit": "500",
                    },
                )
                if resp.status_code != 200:
                    return []
                return resp.json() or []
        except Exception:
            return []

    jobs, products, shots = await asyncio.gather(
        _fetch_all_jobs(),
        _fetch_all_products(),
        _fetch_all_shots(),
    )
    product_to_project: dict[str, str] = {
        p["id"]: p.get("project_id")
        for p in (products or [])
        if p.get("id") and p.get("project_id") in out
    }

    # Bucket shots by project_id (already sorted newest-first).
    for shot in shots:
        pid = shot.get("project_id")
        if pid not in out:
            # Fall back to routing via the shot's product_id.
            pid = product_to_project.get(shot.get("product_id") or "")
            if pid not in out:
                continue
        bucket = out[pid]
        url = shot.get("image_url")
        if url and len(bucket["recent_previews"]) < 4:
            bucket["recent_previews"].append({"url": url, "type": "image"})
        bucket["asset_counts"]["images"] += 1

    # Bucket jobs by project_id. Only count successful videos; use video
    # thumbs to fill remaining preview slots.
    for job in jobs:
        pid = job.get("project_id")
        if pid not in out:
            continue
        if job.get("status") != "success":
            continue
        bucket = out[pid]
        bucket["asset_counts"]["videos"] += 1
        if len(bucket["recent_previews"]) < 4:
            thumb = _pick_video_thumb(job)
            if thumb:
                bucket["recent_previews"].append({"url": thumb, "type": "video"})

    return out


@router.get("/")
async def list_projects(user: dict = Depends(get_current_user)):
    """List all projects with recent asset previews."""
    client = CoreAPIClient(token=user["token"])
    projects = await client.list_projects()

    # Single bulk fetch instead of per-project fan-out (N=9 previously meant
    # ~18 round-trips; now it's ~3 regardless of project count).
    preview_map = await _bulk_project_previews(client, projects)

    for project in projects:
        result = preview_map.get(project["id"])
        if not result:
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


@router.get("/recent-images")
async def list_recent_images(limit: int = 20, user: dict = Depends(get_current_user)):
    """Recent images across all the user's projects, ordered by created_at desc.

    Parallel-fetches projects + products (needed to catch shots linked only via
    product_id) then issues two batched product_shots queries in parallel. Total
    round-trips are bounded and concurrent — see plan `calm-foraging-elephant.md`.
    """
    from pathlib import Path
    from env_loader import load_env
    load_env(Path(__file__))

    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not supabase_url or not anon_key:
        return []

    limit = max(1, min(int(limit or 20), 100))
    client = CoreAPIClient(token=user["token"])

    try:
        projects = await client.list_projects()
    except Exception:
        projects = []
    project_ids = [p["id"] for p in (projects or []) if p.get("id")]
    if not project_ids:
        return []

    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {user['token']}",
        "Content-Type": "application/json",
    }
    import httpx as _httpx

    # Bulk fetch products for ALL projects in one round-trip (was: N parallel
    # scoped /api/products calls — 19 projects → ~4s). We only need id, name,
    # project_id to route shots-by-product back to their owning project.
    async with _httpx.AsyncClient(timeout=15.0) as http:
        prod_resp = await http.get(
            f"{supabase_url}/rest/v1/products",
            headers=headers,
            params={
                "select": "id,name,project_id",
                "project_id": f"in.({','.join(project_ids)})",
                "limit": "1000",
            },
        )
    product_ids: list[str] = []
    product_name_by_id: dict[str, str] = {}
    if prod_resp.status_code == 200:
        for p in prod_resp.json() or []:
            pid = p.get("id")
            if pid:
                product_ids.append(pid)
                product_name_by_id[pid] = p.get("name", "")

    async with _httpx.AsyncClient(timeout=15.0) as http:
        fetches = [
            http.get(
                f"{supabase_url}/rest/v1/product_shots",
                headers=headers,
                params={
                    "project_id": f"in.({','.join(project_ids)})",
                    "order": "created_at.desc",
                    "limit": str(limit),
                },
            )
        ]
        if product_ids:
            fetches.append(http.get(
                f"{supabase_url}/rest/v1/product_shots",
                headers=headers,
                params={
                    "product_id": f"in.({','.join(product_ids)})",
                    "order": "created_at.desc",
                    "limit": str(limit),
                },
            ))
        results = await asyncio.gather(*fetches, return_exceptions=True)

    seen: set[str] = set()
    shots: list[dict] = []
    for resp in results:
        if isinstance(resp, Exception) or resp.status_code != 200:
            continue
        for s in resp.json() or []:
            sid = s.get("id")
            if not sid or sid in seen:
                continue
            if not (s.get("image_url") or s.get("result_url")):
                continue
            seen.add(sid)
            pid = s.get("product_id")
            if pid and pid in product_name_by_id and not s.get("product_name"):
                s["product_name"] = product_name_by_id[pid]
            shots.append(s)

    shots.sort(key=lambda s: s.get("created_at") or "", reverse=True)
    return shots[:limit]


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


@router.get("/{project_id}/full")
async def get_project_full(project_id: str, user: dict = Depends(get_current_user)):
    """One-shot endpoint that returns project metadata + all image + video assets.

    Builds the products and influencers lookup maps exactly once and shares them
    across both asset fetchers — collapses what was 3 frontend requests (each
    rebuilding the same maps) into a single request with 2-3 underlying
    Supabase calls.

    Response shape: { project: {...}, images: [...], videos: [...] }
    """
    client = CoreAPIClient(token=user["token"], project_id=project_id)

    # Build shared lookups once — these were previously fetched twice
    # (once for images, once for videos).
    influencer_map_task = _build_influencer_map(client)
    products_task = _cached_list_products(client)
    influencer_map, products = await asyncio.gather(
        influencer_map_task,
        products_task,
        return_exceptions=True,
    )
    if isinstance(influencer_map, Exception):
        influencer_map = {}
    if isinstance(products, Exception):
        products = []

    project, images, videos = await asyncio.gather(
        client.get_project(project_id),
        _fetch_project_images(client, influencer_map=influencer_map, products=products),
        _fetch_project_videos(client, influencer_map=influencer_map, products=products),
    )

    images, videos = await _heal_assets_for_client(client, images, videos)

    if not project:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Project not found")

    completed_videos = [v for v in videos if v.get("status") == "success"]
    project["asset_counts"] = {
        "images": len(images),
        "videos": len(completed_videos),
    }

    return {"project": project, "images": images, "videos": videos}


@router.post("/{project_id}/jobs-status")
async def project_jobs_status(
    project_id: str,
    data: dict,
    user: dict = Depends(get_current_user),
):
    """Lightweight polling endpoint: given a list of in-flight image/job IDs,
    return only their current status + progress + preview URLs.

    Body: { "image_ids": [...], "video_ids": [...] }
    Response: {
        "images": [{id, status, status_message, progress, preview_url, image_url}, ...],
        "videos": [{id, status, status_message, progress, preview_url, final_video_url}, ...],
    }

    Replaces the prior pattern of re-fetching the entire project payload every
    5 seconds. One Supabase REST query per asset type, only the columns the UI
    needs, no enrichment / no products / no influencer lookup.
    """
    from pathlib import Path
    from env_loader import load_env
    load_env(Path(__file__))

    image_ids = [str(i) for i in (data.get("image_ids") or []) if i]
    video_ids = [str(i) for i in (data.get("video_ids") or []) if i]
    if not image_ids and not video_ids:
        return {"images": [], "videos": []}

    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not (supabase_url and anon_key):
        return {"images": [], "videos": []}

    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {user['token']}",
        "Content-Type": "application/json",
    }

    import httpx as _httpx
    async with _httpx.AsyncClient(timeout=10.0) as http:
        fetches = []
        if image_ids:
            fetches.append(http.get(
                f"{supabase_url}/rest/v1/product_shots",
                headers=headers,
                params={
                    "id": f"in.({','.join(image_ids)})",
                    "select": "id,status,status_message,progress,preview_url,image_url,created_at",
                },
            ))
        else:
            fetches.append(None)
        video_fetches = []
        if video_ids:
            video_fetches = [
                http.get(
                    f"{supabase_url}/rest/v1/video_jobs",
                    headers=headers,
                    params={
                        "id": f"in.({','.join(video_ids)})",
                        "select": "id,status,status_message,progress,preview_url,preview_type,final_video_url,thumbnail_url,created_at",
                    },
                ),
                http.get(
                    f"{supabase_url}/rest/v1/clone_video_jobs",
                    headers=headers,
                    params={
                        "id": f"in.({','.join(video_ids)})",
                        "select": _CLONE_JOB_SELECT,
                    },
                ),
            ]
        results = await asyncio.gather(
            *[f for f in fetches if f is not None],
            *(video_fetches or [asyncio.sleep(0)]),
            return_exceptions=True,
        )

    out: dict = {"images": [], "videos": []}
    idx = 0
    if image_ids:
        r = results[idx]; idx += 1
        if not isinstance(r, Exception) and r.status_code == 200:
            out["images"] = r.json() or []
    if video_ids:
        regular_rows: list = []
        clone_rows: list = []
        r_regular = results[idx]
        r_clone = results[idx + 1] if idx + 1 < len(results) else None
        if not isinstance(r_regular, Exception) and r_regular.status_code == 200:
            regular_rows = r_regular.json() or []
        if r_clone is not None and not isinstance(r_clone, Exception) and r_clone.status_code == 200:
            clone_rows = [_normalize_clone_status_row(r) for r in (r_clone.json() or [])]
        seen_ids = {str(r.get("id")) for r in regular_rows if r.get("id")}
        out["videos"] = regular_rows + [r for r in clone_rows if str(r.get("id")) not in seen_ids]

    # Reconcile orphaned shots: a generation writes its result back from an
    # in-process background task. If the worker/process is restarted (deploy,
    # code reload, crash) while that task is mid-flight, the shot is stranded
    # in "processing" forever and the UI spins indefinitely even though the
    # provider finished. After a generous grace period (well beyond any real
    # render time) flip such shots to "failed" so the card resolves and the
    # user can retry instead of staring at an eternal spinner.
    await _reconcile_stale_image_shots(http_headers=headers, supabase_url=supabase_url, rows=out["images"])
    regular_videos = [r for r in out["videos"] if r.get("_source") != "clone"]
    clone_videos = [r for r in out["videos"] if r.get("_source") == "clone"]
    await _reconcile_stale_video_jobs(http_headers=headers, supabase_url=supabase_url, rows=regular_videos)
    await _reconcile_stale_clone_jobs(http_headers=headers, supabase_url=supabase_url, rows=clone_videos)
    out["videos"] = regular_videos + clone_videos
    return out


# Images never legitimately take this long; past it the writeback task is dead.
_STALE_IMAGE_SECONDS = 8 * 60
# Video renders (Kie polls, multi-chunk edits) can run longer — generous grace.
_STALE_VIDEO_SECONDS = 25 * 60

_CLONE_JOB_SELECT = (
    "id,status,status_message,progress,preview_url,preview_type,final_video_url,created_at"
)


def _normalize_clone_status_row(row: dict) -> dict:
    """Map clone_video_jobs shape to the video_jobs fields the gallery expects."""
    out = dict(row)
    out["_source"] = "clone"
    if (out.get("status") or "").lower() == "complete":
        out["status"] = "success"
        out["progress"] = 100
    return out


def _is_stale_processing_row(row: dict, *, media_keys: str | list[str], grace_seconds: int) -> bool:
    from datetime import datetime, timezone

    if not isinstance(row, dict):
        return False
    status = (row.get("status") or "").lower()
    if not ("processing" in status or "pending" in status or "generating" in status):
        return False
    keys = [media_keys] if isinstance(media_keys, str) else media_keys
    if any(row.get(k) for k in keys):
        return False
    created = row.get("created_at")
    if not created:
        return False
    try:
        now = datetime.now(timezone.utc)
        ts = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return (now - ts).total_seconds() >= grace_seconds


async def _reconcile_stale_image_shots(*, http_headers: dict, supabase_url: str, rows: list) -> None:
    """Delete image shots stuck in processing — ghost cards must not linger."""
    stale_ids: list[str] = []
    for row in list(rows):
        if _is_stale_processing_row(row, media_keys="image_url", grace_seconds=_STALE_IMAGE_SECONDS):
            stale_ids.append(str(row["id"]))
            rows.remove(row)

    if not stale_ids:
        return

    import httpx as _httpx
    del_headers = {**http_headers, "Prefer": "return=minimal"}
    try:
        async with _httpx.AsyncClient(timeout=10.0) as http:
            await asyncio.gather(
                *(
                    http.delete(
                        f"{supabase_url}/rest/v1/product_shots",
                        headers=del_headers,
                        params={"id": f"eq.{sid}"},
                    )
                    for sid in stale_ids
                ),
                return_exceptions=True,
            )
    except Exception as e:
        print(f"[jobs-status] stale shot delete failed: {e}")


async def _reconcile_stale_video_jobs(*, http_headers: dict, supabase_url: str, rows: list) -> None:
    """Delete video jobs stuck in processing — ghost cards must not linger."""
    stale_ids: list[str] = []
    for row in list(rows):
        if _is_stale_processing_row(row, media_keys=["final_video_url", "video_url"], grace_seconds=_STALE_VIDEO_SECONDS):
            stale_ids.append(str(row["id"]))
            rows.remove(row)

    if not stale_ids:
        return

    import httpx as _httpx
    del_headers = {**http_headers, "Prefer": "return=minimal"}
    try:
        async with _httpx.AsyncClient(timeout=10.0) as http:
            await asyncio.gather(
                *(
                    http.delete(
                        f"{supabase_url}/rest/v1/video_jobs",
                        headers=del_headers,
                        params={"id": f"eq.{sid}"},
                    )
                    for sid in stale_ids
                ),
                return_exceptions=True,
            )
    except Exception as e:
        print(f"[jobs-status] stale video delete failed: {e}")


async def _reconcile_stale_clone_jobs(*, http_headers: dict, supabase_url: str, rows: list) -> None:
    """Mark clone jobs stuck in processing as failed so ghost cards resolve."""
    stale_ids: list[str] = []
    for row in list(rows):
        if _is_stale_processing_row(
            row, media_keys=["final_video_url", "video_url"], grace_seconds=_STALE_VIDEO_SECONDS
        ):
            stale_ids.append(str(row["id"]))
            row["status"] = "failed"
            row["error_message"] = row.get("error_message") or "Generation timed out — please try again."
            rows.remove(row)

    if not stale_ids:
        return

    import httpx as _httpx
    patch_headers = {**http_headers, "Prefer": "return=minimal"}
    payload = {
        "status": "failed",
        "error_message": "Generation timed out — please try again.",
    }
    try:
        async with _httpx.AsyncClient(timeout=10.0) as http:
            await asyncio.gather(
                *(
                    http.patch(
                        f"{supabase_url}/rest/v1/clone_video_jobs",
                        headers=patch_headers,
                        params={"id": f"eq.{sid}"},
                        json=payload,
                    )
                    for sid in stale_ids
                ),
                return_exceptions=True,
            )
    except Exception as e:
        print(f"[jobs-status] stale clone job patch failed: {e}")


@router.delete("/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    """Delete a project by ID."""
    client = CoreAPIClient(token=user["token"], project_id=project_id)
    return await client.delete_project(project_id)

@router.get("/{project_id}/assets/images")
async def list_project_images(project_id: str, user: dict = Depends(get_current_user)):
    """List all image assets (product shots) for a project."""
    client = CoreAPIClient(token=user["token"], project_id=project_id)
    images = await _fetch_project_images(client)
    images, _ = await _heal_assets_for_client(client, images=images, videos=[])
    return images


@router.get("/{project_id}/assets/videos")
async def list_project_videos(project_id: str, user: dict = Depends(get_current_user)):
    """List all video assets (jobs) for a project."""
    client = CoreAPIClient(token=user["token"], project_id=project_id)
    videos = await _fetch_project_videos(client)
    _, videos = await _heal_assets_for_client(client, images=[], videos=videos)
    return videos


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


@router.post("/video-thumbnails")
async def generate_video_thumbnails(data: dict, user: dict = Depends(get_current_user)):
    """Generate thumbnail images for videos that don't have image previews.

    Body: { "jobs": [{"id": "...", "video_url": "..."}] }
    Returns: { "thumbnails": {"job_id": "thumb_url", ...} }

    Uses FFmpeg to extract the first frame, uploads to Supabase Storage,
    and updates the video_jobs.thumbnail_url field for caching. Subsequent
    calls for the same job_id will return the cached thumbnail instantly.
    """
    from pathlib import Path
    from env_loader import load_env
    load_env(Path(__file__))

    jobs = data.get("jobs", [])
    if not jobs:
        return {"thumbnails": {}}

    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    # First, check which jobs already have thumbnail_url cached in the DB
    thumbnails: dict[str, str] = {}
    jobs_needing_gen: list[dict] = []

    if supabase_url and anon_key:
        import httpx
        job_ids = [j["id"] for j in jobs if j.get("id")]
        if job_ids:
            headers = {
                "apikey": anon_key,
                "Authorization": f"Bearer {user['token']}",
                "Content-Type": "application/json",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as http:
                    resp = await http.get(
                        f"{supabase_url}/rest/v1/video_jobs",
                        headers=headers,
                        params={
                            "id": f"in.({','.join(job_ids)})",
                            "select": "id,thumbnail_url",
                        },
                    )
                    if resp.status_code == 200:
                        for row in resp.json() or []:
                            if row.get("thumbnail_url"):
                                thumbnails[row["id"]] = row["thumbnail_url"]
            except Exception as e:
                print(f"[Thumbnails] DB check failed: {e}")

    # Filter to only jobs that need generation
    for job in jobs:
        jid = job.get("id", "")
        if jid not in thumbnails and job.get("video_url"):
            jobs_needing_gen.append(job)

    if not jobs_needing_gen:
        return {"thumbnails": thumbnails}

    # Generate thumbnails concurrently (max 3 at a time)
    from utils.thumbnail import generate_thumbnail
    sem = asyncio.Semaphore(3)

    async def _gen(job: dict):
        async with sem:
            jid = job["id"]
            url = job["video_url"]
            thumb = await generate_thumbnail(url, jid)
            if thumb:
                thumbnails[jid] = thumb
                # Cache in DB for future requests
                if supabase_url and anon_key:
                    try:
                        import httpx
                        # Use service role key if available for reliable writes
                        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                        auth_token = service_key if service_key else user["token"]
                        async with httpx.AsyncClient(timeout=10.0) as http:
                            await http.patch(
                                f"{supabase_url}/rest/v1/video_jobs?id=eq.{jid}",
                                headers={
                                    "apikey": anon_key,
                                    "Authorization": f"Bearer {auth_token}",
                                    "Content-Type": "application/json",
                                    "Prefer": "return=minimal",
                                },
                                json={"thumbnail_url": thumb},
                            )
                    except Exception as e:
                        print(f"[Thumbnails] DB cache write failed for {jid}: {e}")

    await asyncio.gather(*[_gen(j) for j in jobs_needing_gen], return_exceptions=True)
    return {"thumbnails": thumbnails}


# ── AI Caption Generation (for images and generic assets) ──────────────────

class CaptionGenerateRequest(BaseModel):
    asset_type: str = "image"
    asset_label: str = ""
    asset_url: str = ""
    platform: str = "instagram"


@router.post("/generate-caption")
async def generate_caption(
    data: CaptionGenerateRequest,
    user: dict = Depends(get_current_user),
):
    """Generate 3 AI caption suggestions for an asset (image or video)."""
    from pathlib import Path
    from env_loader import load_env
    load_env(Path(__file__))

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"captions": [
            f"Check out this amazing content! 🔥 #ugc #ai",
            f"You need to see this! ✨ #viral #creative",
            f"POV: This is your new obsession 👀 #trending",
        ]}

    platform = data.platform.capitalize()
    asset_desc = data.asset_label or "creative content"

    prompt = f"""Generate exactly 3 distinct, engaging social media captions for {platform}.

Context:
- Asset type: {data.asset_type}
- Description: {asset_desc}
- This is a {data.asset_type} post

Requirements:
- Each caption should have a different angle (e.g. storytelling, CTA, question)
- Include relevant emojis
- Keep under 200 characters for TikTok, 2200 for Instagram, 500 for YouTube
- Include 3-5 relevant hashtags at the end
- Sound natural and authentic, not salesy

Return ONLY a JSON array of 3 strings, nothing else."""

    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        import json
        raw = response.choices[0].message.content or ""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        captions = json.loads(raw)
        if not isinstance(captions, list):
            captions = [raw]
        return {"captions": captions[:3]}
    except Exception as e:
        print(f"[CaptionGen] Failed: {e}")
        return {"captions": [
            f"Check out this amazing content! 🔥 #ugc #ai",
            f"You need to see this! ✨ #viral #creative",
            f"POV: This is your new obsession 👀 #trending",
        ]}
