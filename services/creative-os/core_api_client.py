"""
Creative OS — Core API Client

HTTP proxy to the core UGC backend (port 8000).
All requests are forwarded with the user's JWT so the core
backend can scope data by user and project.
"""
import os
import httpx
from typing import Optional
from pathlib import Path

from env_loader import load_env
load_env(Path(__file__))

CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8000")


class CoreAPIClient:
    """Async HTTP client for proxying requests to the core UGC backend."""

    def __init__(self, token: str, project_id: Optional[str] = None):
        self.token = token
        self.project_id = project_id
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if project_id:
            self._headers["X-Project-Id"] = project_id

    async def _request(self, method: str, path: str, _retries: int = 3, **kwargs) -> dict:
        import asyncio as _aio

        last_exc = None
        for attempt in range(1, _retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.request(
                        method,
                        f"{CORE_API_URL}{path}",
                        headers=self._headers,
                        **kwargs,
                    )
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError) as e:
                last_exc = e
                if attempt < _retries:
                    wait = 2 ** (attempt - 1)
                    print(f"[CoreAPI] {method} {path} — transient error ({e}), retry {attempt}/{_retries} in {wait}s")
                    await _aio.sleep(wait)
                else:
                    print(f"[CoreAPI] {method} {path} — failed after {_retries} attempts: {e}")
                    raise

    # ── Projects ──────────────────────────────────────────────────────
    async def list_projects(self) -> list:
        return await self._request("GET", "/api/projects")

    async def get_project(self, project_id: str) -> dict:
        projects = await self.list_projects()
        for p in projects:
            if p["id"] == project_id:
                return p
        return {}

    async def create_project(self, name: str) -> dict:
        return await self._request("POST", "/api/projects", json={"name": name})

    async def rename_project(self, project_id: str, name: str) -> dict:
        return await self._request("PUT", f"/api/projects/{project_id}", json={"name": name})

    async def delete_project(self, project_id: str) -> dict:
        return await self._request("DELETE", f"/api/projects/{project_id}")

    # ── Influencers ───────────────────────────────────────────────────
    async def list_influencers(self) -> list:
        return await self._request("GET", "/influencers")

    async def get_influencer(self, influencer_id: str) -> dict:
        try:
            return await self._request("GET", f"/influencers/{influencer_id}")
        except Exception:
            return {}

    # ── Products ──────────────────────────────────────────────────────
    async def list_products(self) -> list:
        return await self._request("GET", "/api/products")

    async def get_product(self, product_id: str) -> dict:
        try:
            return await self._request("GET", f"/api/products/{product_id}")
        except Exception:
            return {}

    # ── Product Shots (images) ────────────────────────────────────────
    async def list_product_shots(self, product_id: str) -> list:
        return await self._request("GET", f"/api/products/{product_id}/shots")

    async def generate_product_shot(self, product_id: str, shot_type: str = "hero", variations: int = 1, prompt: str = None, influencer_image_url: str = None) -> list:
        payload = {"shot_type": shot_type, "variations": variations}
        if prompt:
            payload["prompt"] = prompt
        if influencer_image_url:
            payload["influencer_image_url"] = influencer_image_url
        return await self._request(
            "POST",
            f"/api/products/{product_id}/shots",
            json=payload,
        )

    async def animate_shot(self, shot_id: str) -> dict:
        return await self._request("POST", f"/api/shots/{shot_id}/animate")

    async def delete_shot(self, shot_id: str) -> dict:
        return await self._request("DELETE", f"/api/shots/{shot_id}")

    async def update_shot(self, shot_id: str, data: dict) -> dict:
        """Update a product_shot record directly via Supabase REST.

        The core API has no PUT /api/shots/{id} endpoint, so we update
        the product_shots table directly using the Supabase service key.
        """
        import os
        from supabase import create_client

        sb = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
        )
        result = sb.table("product_shots").update(data).eq("id", shot_id).execute()
        return result.data[0] if result.data else {}

    async def create_standalone_shot(self, data: dict) -> dict:
        """Create a product_shot record via Supabase REST (no product_id required).

        Used for influencer-only, upload-only, and prompt-only image generation
        where there's no product to scope the shot under.
        """
        import os
        from pathlib import Path
        from env_loader import load_env
        load_env(Path(__file__))

        supabase_url = os.getenv("SUPABASE_URL")
        anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

        if not supabase_url or not anon_key:
            raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY for standalone shot")

        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {self._headers.get('Authorization', '').replace('Bearer ', '')}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{supabase_url}/rest/v1/product_shots",
                headers=headers,
                json=data,
            )
            resp.raise_for_status()
            rows = resp.json()
            return rows[0] if rows else data

    async def list_project_shots(self, project_id: str) -> list:
        """Fetch all shots for a project via Supabase REST (including standalone ones)."""
        import os
        from pathlib import Path
        from env_loader import load_env
        load_env(Path(__file__))

        supabase_url = os.getenv("SUPABASE_URL")
        anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

        if not supabase_url or not anon_key:
            return []

        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{supabase_url}/rest/v1/product_shots",
                headers=headers,
                params={"project_id": f"eq.{project_id}", "order": "created_at.desc"},
            )
            if resp.status_code != 200:
                print(f"[CoreAPI] project shots fetch error {resp.status_code}: {resp.text}")
                return []
            return resp.json()

    async def delete_job(self, job_id: str) -> dict:
        return await self._request("DELETE", f"/jobs/{job_id}")

    # ── Jobs ──────────────────────────────────────────────────────────
    async def list_jobs(self, status: Optional[str] = None, limit: int = 50) -> list:
        params = {"limit": limit, "include_clones": True}
        if status:
            params["status"] = status
        return await self._request("GET", "/jobs", params=params)

    async def get_job_status(self, job_id: str) -> dict:
        return await self._request("GET", f"/jobs/{job_id}/status")

    async def create_job(self, payload: dict, skip_dispatch: bool = True) -> dict:
        """Create a job record. skip_dispatch=True prevents the core worker from also running."""
        return await self._request("POST", "/jobs", json=payload, params={"skip_dispatch": str(skip_dispatch).lower()})

    async def create_video_job_record(self, data: dict) -> dict:
        """Create a minimal video_jobs record for tracking Creative OS generations.
        
        Uses the core API's job creation endpoint with required fields filled in.
        """
        job_payload = {
            "influencer_id": data.get("influencer_id", "00000000-0000-0000-0000-000000000000"),
            "product_id": data.get("product_id"),
            "product_type": "physical",
            "model_api": data.get("model_api", "kling-3.0"),
            "length": data.get("length", 5),
            "campaign_name": data.get("campaign_name", "Creative OS"),
            "video_language": data.get("language", "en"),
            "subtitles_enabled": data.get("captions", True),
            "music_enabled": data.get("background_music", True),
        }
        return await self._request("POST", "/jobs", json=job_payload)

    # ── Stats ─────────────────────────────────────────────────────────
    async def get_stats(self) -> dict:
        return await self._request("GET", "/stats")

    # ── Wallet ────────────────────────────────────────────────────────
    async def get_wallet(self) -> dict:
        return await self._request("GET", "/api/wallet")

    # ── Credit Costs ──────────────────────────────────────────────────
    async def get_credit_costs(self) -> dict:
        return await self._request("GET", "/api/credits/costs")

    # ── Script Generation ─────────────────────────────────────────────
    async def generate_script(
        self,
        product_id: str,
        duration: int = 15,
        influencer_id: str = None,
        product_type: str = "physical",
        output_format: str = "legacy",
        video_language: str = "en",
        model_api: str = "veo-3.1-fast",
        context: str = None,
    ) -> dict:
        payload = {
            "product_id": product_id,
            "duration": duration,
            "product_type": product_type,
            "output_format": output_format,
            "video_language": video_language,
            "model_api": model_api,
        }
        if influencer_id:
            payload["influencer_id"] = influencer_id
        if context:
            payload["context"] = context
        # Script generation uses a 3-call prompt chain — may take 30-60s
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                "POST",
                f"{CORE_API_URL}/api/scripts/generate",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Product Analysis ──────────────────────────────────────────────
    async def analyze_product(self, product_id: str) -> dict:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                "POST",
                f"{CORE_API_URL}/analyze-product/{product_id}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Cost Estimation ───────────────────────────────────────────────
    async def estimate_cost(self, script_text: str, duration: int, model: str, music_enabled: bool = True) -> dict:
        return await self._request("POST", "/estimate", json={
            "script_text": script_text,
            "duration": duration,
            "model": model,
            "music_enabled": music_enabled,
        })

    # ── Scripts ───────────────────────────────────────────────────────
    async def list_scripts(self, product_id: Optional[str] = None) -> list:
        params = {}
        if product_id:
            params["product_id"] = product_id
        return await self._request("GET", "/api/scripts", params=params)

    async def generate_scripts(
        self,
        product_id: str,
        duration: int = 15,
        product_type: str = "physical",
        influencer_id: Optional[str] = None,
        context: Optional[str] = None,
        video_language: str = "en",
        model_api: str = "veo-3.1-fast",
    ) -> dict:
        payload = {
            "product_id": product_id,
            "duration": duration,
            "product_type": product_type,
            "output_format": "json",
            "video_language": video_language,
            "model_api": model_api,
        }
        if influencer_id:
            payload["influencer_id"] = influencer_id
        if context:
            payload["context"] = context
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.request(
                "POST",
                f"{CORE_API_URL}/api/scripts/generate",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Influencers (write) ───────────────────────────────────────────
    async def create_influencer(self, data: dict) -> dict:
        return await self._request("POST", "/influencers", json=data)

    # ── Products (write) ──────────────────────────────────────────────
    async def create_product(self, data: dict) -> dict:
        return await self._request("POST", "/api/products", json=data)

    async def analyze_product_image(self, product_id: str) -> dict:
        return await self._request(
            "POST", "/api/products/analyze",
            json={"product_id": product_id},
        )

    async def analyze_digital_product(self, product_id: str) -> dict:
        return await self._request("POST", f"/api/products/{product_id}/analyze-digital")

    # ── Full UGC video pipeline ───────────────────────────────────────
    async def create_ugc_video_job(self, data: dict) -> dict:
        """POST /jobs — full 15s/30s UGC video.

        Note: skip_dispatch=False so the worker actually runs the pipeline
        (different from create_job which is used by Creative OS to create
        tracking-only records).
        """
        return await self._request(
            "POST", "/jobs",
            json=data,
            params={"skip_dispatch": "false"},
        )

    async def create_bulk_ugc_jobs(self, data: dict) -> list:
        return await self._request("POST", "/jobs/bulk", json=data)

    # ── AI Clone videos ───────────────────────────────────────────────
    async def create_clone_job(self, data: dict) -> dict:
        return await self._request("POST", "/api/clone-jobs", json=data)

    # ── Scheduling / posting ──────────────────────────────────────────
    async def schedule_posts(self, posts: list) -> dict:
        return await self._request("POST", "/api/schedule/bulk", json={"posts": posts})

    async def cancel_scheduled_post(self, post_id: str) -> dict:
        return await self._request("DELETE", f"/api/schedule/{post_id}")

    async def generate_caption(self, video_job_id: str, platform: str = "instagram") -> dict:
        return await self._request(
            "POST", "/api/schedule/generate-caption",
            json={"video_job_id": video_job_id, "platform": platform},
        )

    async def get_schedule_range(self, start_date: str, end_date: str) -> list:
        return await self._request(
            "GET", "/api/schedule",
            params={"start_date": start_date, "end_date": end_date},
        )

    # ── Editor / Remotion ─────────────────────────────────────────────
    async def get_editor_state(self, job_id: str) -> dict:
        return await self._request("GET", f"/api/editor/state/{job_id}")

    async def save_editor_state(self, job_id: str, state: dict) -> dict:
        return await self._request("POST", f"/api/editor/state/{job_id}", json=state)

    async def trigger_editor_render(self, job_id: str, editor_state: dict, codec: str = "h264") -> dict:
        return await self._request(
            "POST", "/api/editor/render",
            json={"job_id": job_id, "editor_state": editor_state, "codec": codec},
        )

    async def get_editor_render_progress(self, render_id: str) -> dict:
        return await self._request("GET", f"/api/editor/render/{render_id}/progress")

    async def caption_video(self, job_id: str, style: str = "hormozi", placement: str = "middle") -> dict:
        """Trigger server-side Whisper captioning — same pipeline as the editor's 'Caption video' button."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                "POST",
                f"{CORE_API_URL}/api/editor/caption-video/{job_id}",
                headers=self._headers,
                json={"style": style, "placement": placement},
            )
            resp.raise_for_status()
            return resp.json()

    # ── Clone jobs ────────────────────────────────────────────────────
    async def list_clone_jobs(self) -> list:
        return await self._request("GET", "/api/clone-jobs")

    async def get_clone_job(self, job_id: str) -> dict:
        return await self._request("GET", f"/api/clone-jobs/{job_id}")

    # ── Scheduled posts ───────────────────────────────────────────────
    async def list_scheduled_posts(self) -> list:
        """Returns scheduled posts in a 90-day window (-30d to +60d).

        The core endpoint requires explicit start/end dates; this defaults
        to a window that covers everything the user typically cares about.
        """
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=30)).isoformat()
        end = (now + timedelta(days=60)).isoformat()
        return await self._request(
            "GET", "/api/schedule",
            params={"start_date": start, "end_date": end},
        )

    async def list_social_connections(self) -> dict:
        return await self._request("GET", "/api/connections")
