"""Mirror remote / ephemeral media URLs into Supabase Storage for durable assets."""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Awaitable, Callable, Optional

_INLINE_RETRIES = 5
_BACKGROUND_RETRIES = 12
_BACKGROUND_DELAY_SECONDS = 30.0
_BACKGROUND_TASKS: set[asyncio.Task] = set()

PRODUCT_IMAGES_BUCKET = "product-images"
GENERATED_VIDEOS_BUCKET = "generated-videos"

# Known provider CDNs whose URLs expire — keep in sync with frontend AssetGallery.
EPHEMERAL_HOSTS = (
    "d2p7pge43lyniu.cloudfront.net",
    "tempfile.aiquickdraw.com",
    "fal.media",
    "fal.run",
)


class PersistMediaError(RuntimeError):
    """Raised when a provider URL could not be mirrored to Supabase."""


def is_ephemeral_url(url: str) -> bool:
    if not url:
        return False
    return any(host in url for host in EPHEMERAL_HOSTS)


def is_supabase_storage_url(url: str, bucket: str | None = None) -> bool:
    """True when url already points at our Supabase public storage (any bucket)."""
    if not url or not url.startswith("http"):
        return False
    supabase_base = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    if supabase_base and not url.startswith(supabase_base):
        return False
    if "/storage/v1/object/public/" in url or "/storage/v1/render/image/public/" in url:
        if bucket:
            return f"/storage/v1/object/public/{bucket}/" in url or (
                f"/storage/v1/render/image/public/{bucket}/" in url
            )
        return True
    return False


def needs_persistence(url: str) -> bool:
    """True when url is a remote http(s) asset that is not already in Supabase."""
    if not url or not url.startswith("http"):
        return False
    return not is_supabase_storage_url(url)


def _canonical_public_url(url: str) -> str:
    """Prefer object/public URLs over render/transform URLs for DB storage."""
    if "/storage/v1/render/image/public/" in url:
        return url.replace("/storage/v1/render/image/public/", "/storage/v1/object/public/")
    return url


def _supabase_client():
    from supabase import create_client

    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not service_key:
        raise PersistMediaError("missing SUPABASE_URL or service key")
    return create_client(supabase_url, service_key)


def _httpx_verify(url: str) -> bool:
    # Kie tempfile CDN uses a self-signed cert that httpx rejects by default.
    return "tempfile.aiquickdraw.com" not in url


async def _download_bytes(url: str, *, timeout: float = 300.0) -> bytes:
    import httpx

    last_err: Exception | None = None
    for attempt in range(_INLINE_RETRIES):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                verify=_httpx_verify(url),
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                if not resp.content:
                    raise PersistMediaError(f"empty response body from {url[:96]}")
                return resp.content
        except Exception as e:
            last_err = e
            if attempt < _INLINE_RETRIES - 1:
                await asyncio.sleep(2.0 * (attempt + 1))
    raise PersistMediaError(f"download failed ({url[:96]}): {last_err}")


def download_url_to_file(
    url: str,
    dest: "Path | str",
    *,
    timeout: float = 300.0,
    max_retries: int = _INLINE_RETRIES,
) -> "Path":
    """Sync download for ffmpeg/concat paths (httpx, Kie CDN SSL bypass, retries)."""
    import time
    from pathlib import Path

    import httpx

    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                verify=_httpx_verify(url),
            ) as client:
                resp = client.get(url)
                resp.raise_for_status()
                if not resp.content:
                    raise PersistMediaError(f"empty response body from {url[:96]}")
                out.write_bytes(resp.content)
                return out
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(2.0 * (attempt + 1))
    raise PersistMediaError(f"download failed ({url[:96]}): {last_err}")


async def _upload_bytes(
    body: bytes,
    *,
    bucket: str,
    filename: str,
    content_type: str,
) -> str:
    last_err: Exception | None = None
    for attempt in range(_INLINE_RETRIES):
        try:
            sb = _supabase_client()
            sb.storage.from_(bucket).upload(
                filename,
                body,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            public_url = sb.storage.from_(bucket).get_public_url(filename)
            print(f"[persist_media] mirrored to {bucket}/{filename}")
            return public_url
        except Exception as e:
            last_err = e
            if attempt < _INLINE_RETRIES - 1:
                await asyncio.sleep(2.0 * (attempt + 1))
    raise PersistMediaError(f"upload failed for {bucket}/{filename}: {last_err}")


def _track_background_task(coro) -> None:
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


async def _retry_persist_video_loop(
    provider_url: str,
    *,
    storage_filename: str,
    on_persisted: Callable[[str], Awaitable[None]],
) -> None:
    for attempt in range(_BACKGROUND_RETRIES):
        delay = _BACKGROUND_DELAY_SECONDS if attempt > 0 else 5.0
        await asyncio.sleep(delay)
        try:
            stored = await persist_video_url(
                provider_url,
                filename=storage_filename,
                require_persistent=True,
            )
            if is_supabase_storage_url(stored):
                await on_persisted(stored)
                print(f"[persist_media] background video persist succeeded ({storage_filename})")
                return
        except Exception as e:
            print(
                f"[persist_media] background video retry {attempt + 1}/{_BACKGROUND_RETRIES} "
                f"({provider_url[:80]}): {e}"
            )
    print(f"[persist_media] background video persist exhausted for {provider_url[:96]}")


async def _retry_persist_image_loop(
    provider_url: str,
    *,
    bucket: str,
    path_prefix: str,
    shot_id: Optional[str],
    on_persisted: Callable[[str], Awaitable[None]],
) -> None:
    for attempt in range(_BACKGROUND_RETRIES):
        delay = _BACKGROUND_DELAY_SECONDS if attempt > 0 else 5.0
        await asyncio.sleep(delay)
        try:
            stored = await persist_image_url(
                provider_url,
                bucket=bucket,
                path_prefix=path_prefix,
                shot_id=shot_id,
                require_persistent=True,
            )
            if is_supabase_storage_url(stored):
                await on_persisted(stored)
                print(f"[persist_media] background image persist succeeded ({path_prefix})")
                return
        except Exception as e:
            print(
                f"[persist_media] background image retry {attempt + 1}/{_BACKGROUND_RETRIES} "
                f"({provider_url[:80]}): {e}"
            )
    print(f"[persist_media] background image persist exhausted for {provider_url[:96]}")


def schedule_video_persist_retry(
    provider_url: str,
    *,
    storage_filename: str,
    on_persisted: Callable[[str], Awaitable[None]],
) -> None:
    """Retry mirroring in the background — generation already succeeded."""
    if not provider_url or is_supabase_storage_url(provider_url):
        return
    _track_background_task(
        _retry_persist_video_loop(
            provider_url,
            storage_filename=storage_filename,
            on_persisted=on_persisted,
        )
    )


def schedule_image_persist_retry(
    provider_url: str,
    *,
    bucket: str = PRODUCT_IMAGES_BUCKET,
    path_prefix: str = "project_shots",
    shot_id: Optional[str] = None,
    on_persisted: Callable[[str], Awaitable[None]],
) -> None:
    """Retry mirroring in the background — generation already succeeded."""
    if not provider_url or is_supabase_storage_url(provider_url):
        return
    _track_background_task(
        _retry_persist_image_loop(
            provider_url,
            bucket=bucket,
            path_prefix=path_prefix,
            shot_id=shot_id,
            on_persisted=on_persisted,
        )
    )


async def finalize_video_url(
    provider_url: str,
    *,
    storage_filename: str,
    on_persisted: Optional[Callable[[str], Awaitable[None]]] = None,
) -> str:
    """Return a Supabase URL when possible; never fail generation on storage hiccups.

    Inline persist is attempted first. On failure the provider URL is returned
    so the user can preview immediately, and background retries keep trying to
    mirror into Supabase until success or retries are exhausted.
    """
    if not provider_url or not provider_url.startswith("http"):
        return provider_url or ""

    if is_supabase_storage_url(provider_url):
        return _canonical_public_url(provider_url)

    try:
        return await persist_video_url(
            provider_url,
            filename=storage_filename,
            require_persistent=True,
        )
    except PersistMediaError as e:
        print(f"[persist_media] inline video persist deferred, using provider URL: {e}")
        if on_persisted:
            schedule_video_persist_retry(
                provider_url,
                storage_filename=storage_filename,
                on_persisted=on_persisted,
            )
        return provider_url


async def finalize_image_url(
    provider_url: str,
    *,
    bucket: str = PRODUCT_IMAGES_BUCKET,
    path_prefix: str = "project_shots",
    shot_id: Optional[str] = None,
    on_persisted: Optional[Callable[[str], Awaitable[None]]] = None,
) -> str:
    """Return a Supabase URL when possible; never fail generation on storage hiccups."""
    if not provider_url or not provider_url.startswith("http"):
        return provider_url or ""

    if is_supabase_storage_url(provider_url):
        return _canonical_public_url(provider_url)

    try:
        return await persist_image_url(
            provider_url,
            bucket=bucket,
            path_prefix=path_prefix,
            shot_id=shot_id,
            require_persistent=True,
        )
    except PersistMediaError as e:
        print(f"[persist_media] inline image persist deferred, using provider URL: {e}")
        if on_persisted:
            schedule_image_persist_retry(
                provider_url,
                bucket=bucket,
                path_prefix=path_prefix,
                shot_id=shot_id,
                on_persisted=on_persisted,
            )
        return provider_url


async def persist_image_url(
    url: str,
    *,
    bucket: str = PRODUCT_IMAGES_BUCKET,
    path_prefix: str = "project_shots",
    shot_id: Optional[str] = None,
    require_persistent: bool = True,
) -> str:
    """Download a remote image and upload to Supabase. Returns a durable public URL."""
    if not url or not url.startswith("http"):
        return url or ""

    if is_supabase_storage_url(url):
        return _canonical_public_url(url)

    try:
        raw = await _download_bytes(url, timeout=120.0)
        from services.image_normalize import normalize_image_bytes

        try:
            body = normalize_image_bytes(raw)
            content_type = "image/png"
        except Exception as e:
            print(f"[persist_media] normalize failed, using raw bytes: {e}")
            body = raw
            content_type = "image/jpeg"

        name = shot_id or uuid.uuid4().hex[:16]
        filename = f"{path_prefix}/{name}.png"
        return await _upload_bytes(body, bucket=bucket, filename=filename, content_type=content_type)
    except Exception as e:
        print(f"[persist_media] image persist failed ({url[:96]}): {e}")
        if require_persistent:
            raise PersistMediaError(str(e)) from e
        return url


async def persist_video_url(
    url: str,
    *,
    bucket: str = GENERATED_VIDEOS_BUCKET,
    path_prefix: str = "videos",
    filename: Optional[str] = None,
    require_persistent: bool = True,
) -> str:
    """Download a remote video and upload to Supabase. Returns a durable public URL."""
    if not url or not url.startswith("http"):
        return url or ""

    if is_supabase_storage_url(url):
        return _canonical_public_url(url)

    try:
        body = await _download_bytes(url, timeout=300.0)
        storage_name = filename or f"{path_prefix}/{uuid.uuid4().hex[:16]}.mp4"
        return await _upload_bytes(
            body,
            bucket=bucket,
            filename=storage_name,
            content_type="video/mp4",
        )
    except Exception as e:
        print(f"[persist_media] video persist failed ({url[:96]}): {e}")
        if require_persistent:
            raise PersistMediaError(str(e)) from e
        return url


async def heal_image_row(
    row: dict,
    *,
    url_key: str = "image_url",
    path_prefix: str = "project_shots",
    update_fn: Optional[Callable] = None,
) -> dict:
    """Best-effort: mirror a non-Supabase image URL and update the row."""
    url = row.get(url_key) or row.get("result_url")
    if not url or is_supabase_storage_url(url):
        return row
    try:
        stored = await persist_image_url(
            url,
            shot_id=row.get("id"),
            path_prefix=path_prefix,
            require_persistent=False,
        )
        if stored != url and is_supabase_storage_url(stored):
            row[url_key] = stored
            if update_fn:
                await update_fn(row["id"], {url_key: stored})
    except Exception as e:
        print(f"[persist_media] heal image {row.get('id')} skipped: {e}")
    return row


async def heal_video_row(
    row: dict,
    *,
    update_fn: Optional[Callable] = None,
) -> dict:
    """Best-effort: mirror non-Supabase video URLs on a completed job."""
    if row.get("status") != "success":
        return row

    updates: dict = {}
    for field, path_prefix in (
        ("final_video_url", "videos"),
        ("video_url", "videos"),
    ):
        url = row.get(field)
        if not url or is_supabase_storage_url(url):
            continue
        try:
            stored = await persist_video_url(
                url,
                path_prefix=path_prefix,
                filename=f"{path_prefix}/heal_{row.get('id', uuid.uuid4().hex[:8])}_{field}.mp4",
                require_persistent=False,
            )
            if stored != url and is_supabase_storage_url(stored):
                updates[field] = stored
                row[field] = stored
        except Exception as e:
            print(f"[persist_media] heal video {row.get('id')} {field} skipped: {e}")

    preview = row.get("preview_url")
    if preview and not is_supabase_storage_url(preview):
        if str(preview).lower().endswith((".mp4", ".webm", ".mov")):
            try:
                stored = await persist_video_url(
                    preview,
                    path_prefix="previews",
                    filename=f"previews/heal_{row.get('id', uuid.uuid4().hex[:8])}_preview.mp4",
                    require_persistent=False,
                )
                if stored != preview and is_supabase_storage_url(stored):
                    updates["preview_url"] = stored
                    row["preview_url"] = stored
            except Exception as e:
                print(f"[persist_media] heal preview {row.get('id')} skipped: {e}")
        elif needs_persistence(preview):
            try:
                stored = await persist_image_url(
                    preview,
                    path_prefix="previews",
                    require_persistent=False,
                )
                if stored != preview and is_supabase_storage_url(stored):
                    updates["preview_url"] = stored
                    row["preview_url"] = stored
            except Exception as e:
                print(f"[persist_media] heal preview image {row.get('id')} skipped: {e}")

    if updates and update_fn:
        await update_fn(row["id"], updates)
    return row


async def heal_asset_rows(
    images: list[dict],
    videos: list[dict],
    *,
    update_shot_fn: Optional[Callable] = None,
    update_job_fn: Optional[Callable] = None,
    max_concurrent: int = 4,
) -> tuple[list[dict], list[dict]]:
    """Heal ephemeral/non-Supabase URLs when listing assets (best-effort)."""
    sem = asyncio.Semaphore(max_concurrent)

    async def _heal_image(row: dict) -> dict:
        async with sem:
            return await heal_image_row(row, update_fn=update_shot_fn)

    async def _heal_video(row: dict) -> dict:
        async with sem:
            return await heal_video_row(row, update_fn=update_job_fn)

    if images:
        images = await asyncio.gather(*(_heal_image(r) for r in images))
    if videos:
        videos = await asyncio.gather(*(_heal_video(r) for r in videos))
    return list(images), list(videos)
