#!/usr/bin/env python3
"""Backfill ephemeral asset URLs to Supabase Storage.

Finds product_shots and video_jobs whose image_url / final_video_url still
point at known expiring provider CDNs and mirrors them to Supabase when the
source is still reachable.

Usage:
    cd services/creative-os
    python scripts/backfill_ephemeral_assets.py [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CREATIVE_OS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CREATIVE_OS))

from env_loader import load_env

load_env(CREATIVE_OS)


async def _run(*, dry_run: bool, limit: int | None) -> None:
    from supabase import create_client
    from utils.persist_media import (
        EPHEMERAL_HOSTS,
        is_supabase_storage_url,
        persist_image_url,
        persist_video_url,
    )

    sb = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
    )

    def _is_ephemeral(url: str | None) -> bool:
        if not url or is_supabase_storage_url(url):
            return False
        return any(host in url for host in EPHEMERAL_HOSTS)

    shots = (
        sb.table("product_shots")
        .select("id,image_url,result_url")
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    jobs = (
        sb.table("video_jobs")
        .select("id,final_video_url,video_url,preview_url,status")
        .eq("status", "success")
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )

    shot_targets = [
        s for s in shots
        if _is_ephemeral(s.get("image_url")) or _is_ephemeral(s.get("result_url"))
    ]
    job_targets = [
        j for j in jobs
        if _is_ephemeral(j.get("final_video_url"))
        or _is_ephemeral(j.get("video_url"))
        or _is_ephemeral(j.get("preview_url"))
    ]

    if limit:
        shot_targets = shot_targets[:limit]
        job_targets = job_targets[:limit]

    print(f"Found {len(shot_targets)} image rows and {len(job_targets)} video rows to heal")

    healed_images = 0
    for shot in shot_targets:
        sid = shot["id"]
        url = shot.get("image_url") or shot.get("result_url")
        print(f"[image] {sid} ← {url[:80]}...")
        if dry_run:
            continue
        try:
            stored = await persist_image_url(url, shot_id=sid, require_persistent=False)
            if stored != url and is_supabase_storage_url(stored):
                sb.table("product_shots").update({"image_url": stored}).eq("id", sid).execute()
                healed_images += 1
                print(f"  ✓ {stored[:80]}...")
            else:
                print("  ✗ source unavailable or already healed")
        except Exception as e:
            print(f"  ✗ {e}")

    healed_videos = 0
    for job in job_targets:
        jid = job["id"]
        url = job.get("final_video_url") or job.get("video_url")
        if not url:
            continue
        print(f"[video] {jid} ← {url[:80]}...")
        if dry_run:
            continue
        try:
            stored = await persist_video_url(
                url,
                filename=f"videos/backfill_{jid[:8]}.mp4",
                require_persistent=False,
            )
            updates = {}
            if stored != url and is_supabase_storage_url(stored):
                updates["final_video_url"] = stored
            preview = job.get("preview_url")
            if preview and _is_ephemeral(preview):
                if str(preview).lower().endswith((".mp4", ".webm", ".mov")):
                    pstored = await persist_video_url(
                        preview,
                        filename=f"previews/backfill_{jid[:8]}_preview.mp4",
                        require_persistent=False,
                    )
                else:
                    pstored = await persist_image_url(preview, require_persistent=False)
                if pstored != preview and is_supabase_storage_url(pstored):
                    updates["preview_url"] = pstored
            if updates:
                sb.table("video_jobs").update(updates).eq("id", jid).execute()
                healed_videos += 1
                print(f"  ✓ {updates}")
            else:
                print("  ✗ source unavailable or already healed")
        except Exception as e:
            print(f"  ✗ {e}")

    print(f"Done. Healed {healed_images} images, {healed_videos} videos.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill ephemeral asset URLs to Supabase")
    parser.add_argument("--dry-run", action="store_true", help="List targets without uploading")
    parser.add_argument("--limit", type=int, default=None, help="Max rows per table")
    args = parser.parse_args()
    asyncio.run(_run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
