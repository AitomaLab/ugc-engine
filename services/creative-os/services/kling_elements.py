"""
Creative OS — Kling element-id cache.

WaveSpeed's Kling 3.0 i2v/t2v requires `element_list[].element_id` —
pre-registered string IDs, not inline image URLs. Each registration
costs $0.01. This module is the single entrypoint for "give me an
element_id for this image", and handles the caching so we don't
re-pay on repeat generations.

Cache layers (checked in order):
  1. products.kling_element_id / .kling_element_image_hash
  2. influencers.kling_element_id / .kling_element_image_hash
  3. kling_element_cache table (image_hash PK)

If the stored image_hash doesn't match the current image URL hash,
we re-register and overwrite — so swapping a product image transparently
gets a fresh element. Already-generated clips reference the element_id
captured at generation time and continue to play.

This module is **sync-first** (uses `requests`) so it can be called
from sync contexts like generate_scenes.generate_video_with_retry
which itself runs inside `asyncio.to_thread`. Async callers should
wrap `ensure_element_id_sync` in `asyncio.to_thread`.

See migrations/002_kling_element_ids.sql.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Optional, Sequence

import requests

from services.wavespeed_client import WaveSpeedError, kling_register_element


def _supabase_base() -> str:
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")
    return url.rstrip("/")


def _service_headers() -> dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not key:
        raise RuntimeError("No Supabase key available (SUPABASE_SERVICE_KEY / SUPABASE_ANON_KEY)")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def hash_image_url(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def _extract_element_id(result: dict) -> str:
    """Pull element_id from a completed Kling element-register prediction.

    WaveSpeed returns the structured payload under data; the element_id can
    appear at the top level, in outputs, or nested. Try the known shapes.
    """
    if not isinstance(result, dict):
        raise WaveSpeedError("kling element registration returned non-dict result", transient=False)
    if isinstance(result.get("element_id"), str) and result["element_id"]:
        return result["element_id"]
    outputs = result.get("outputs") or []
    if outputs:
        first = outputs[0]
        if isinstance(first, str) and first:
            return first
        if isinstance(first, dict):
            for key in ("element_id", "id", "url"):
                val = first.get(key)
                if isinstance(val, str) and val:
                    return val
    inner = result.get("data")
    if isinstance(inner, dict) and inner is not result:
        return _extract_element_id(inner)
    raise WaveSpeedError(
        f"kling element registration: element_id missing in result keys={list(result.keys())}",
        transient=False,
    )


# ── Sync Supabase helpers (use `requests`) ──────────────────────────────

def _fetch_row_sync(table: str, row_id: str) -> Optional[dict]:
    try:
        resp = requests.get(
            f"{_supabase_base()}/rest/v1/{table}",
            headers=_service_headers(),
            params={"id": f"eq.{row_id}", "select": "id,kling_element_id,kling_element_image_hash"},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"      [Kling Elements] supabase fetch error ({table}={row_id}): {exc}")
        return None
    if resp.status_code >= 400:
        return None
    rows = resp.json() or []
    return rows[0] if rows else None


def _patch_row_sync(table: str, row_id: str, patch: dict) -> None:
    resp = requests.patch(
        f"{_supabase_base()}/rest/v1/{table}?id=eq.{row_id}",
        headers=_service_headers(),
        json=patch,
        timeout=15,
    )
    resp.raise_for_status()


def _cache_lookup_sync(image_hash: str) -> Optional[str]:
    try:
        resp = requests.get(
            f"{_supabase_base()}/rest/v1/kling_element_cache",
            headers=_service_headers(),
            params={"image_hash": f"eq.{image_hash}", "select": "element_id"},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"      [Kling Elements] cache lookup error: {exc}")
        return None
    if resp.status_code >= 400:
        return None
    rows = resp.json() or []
    return rows[0]["element_id"] if rows else None


def _cache_upsert_sync(image_hash: str, element_id: str, *, name: str, source_url: str) -> None:
    try:
        resp = requests.post(
            f"{_supabase_base()}/rest/v1/kling_element_cache",
            headers={**_service_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json={
                "image_hash": image_hash,
                "element_id": element_id,
                "element_name": name[:20],
                "source_url": source_url,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"      [Kling Elements] cache upsert error: {exc}")
        return
    if resp.status_code >= 400:
        # Cache write failure is non-fatal — log and continue.
        print(f"      [Kling Elements] cache upsert failed status={resp.status_code} body={resp.text[:200]}")


# ── Public API ──────────────────────────────────────────────────────────

def ensure_element_id_sync(
    *,
    name: str,
    description: str,
    image_url: str,
    refer_urls: Optional[Sequence[str]] = None,
    product_id: Optional[str] = None,
    influencer_id: Optional[str] = None,
) -> str:
    """Return a Kling element_id for `image_url`, registering if needed.

    Lookup order:
      - if product_id given: products.kling_element_id (image_hash must match)
      - elif influencer_id given: influencers.kling_element_id
      - else (or on miss): kling_element_cache by image_hash
      - else: register a fresh element, persist, return.

    Raises WaveSpeedError on hard failure. Callers should treat any
    exception as a signal to fall through to the legacy KIE path —
    no clip generation depends on this cache.
    """
    if not image_url:
        raise WaveSpeedError("ensure_element_id: image_url required", transient=False)

    image_hash = hash_image_url(image_url)

    owner_table: Optional[str] = None
    owner_id: Optional[str] = None
    if product_id:
        owner_table, owner_id = "products", product_id
    elif influencer_id:
        owner_table, owner_id = "influencers", influencer_id

    if owner_table and owner_id:
        row = _fetch_row_sync(owner_table, owner_id)
        if row and row.get("kling_element_id") and row.get("kling_element_image_hash") == image_hash:
            print(f"      [Kling Elements] cache hit ({owner_table}={owner_id}) element_id={row['kling_element_id']}")
            return row["kling_element_id"]

    cached = _cache_lookup_sync(image_hash)
    if cached:
        print(f"      [Kling Elements] cache hit (kling_element_cache) element_id={cached}")
        if owner_table and owner_id:
            try:
                _patch_row_sync(owner_table, owner_id, {
                    "kling_element_id": cached,
                    "kling_element_image_hash": image_hash,
                })
            except Exception as exc:
                print(f"      [Kling Elements] backfill {owner_table}.{owner_id} failed: {exc}")
        return cached

    # Miss — register fresh.
    print(f"      [Kling Elements] cache miss — registering name={name[:20]!r} image={image_url[:80]}…")
    result = kling_register_element(
        name=name,
        description=description,
        image=image_url,
        refer_list=list(refer_urls or []),
    )
    element_id = _extract_element_id(result)
    print(f"      [Kling Elements] registered element_id={element_id}")

    _cache_upsert_sync(image_hash, element_id, name=name, source_url=image_url)
    if owner_table and owner_id:
        try:
            _patch_row_sync(owner_table, owner_id, {
                "kling_element_id": element_id,
                "kling_element_image_hash": image_hash,
            })
        except Exception as exc:
            print(f"      [Kling Elements] persist {owner_table}.{owner_id} failed: {exc}")

    return element_id


async def ensure_element_id(
    *,
    name: str,
    description: str,
    image_url: str,
    refer_urls: Optional[Sequence[str]] = None,
    product_id: Optional[str] = None,
    influencer_id: Optional[str] = None,
) -> str:
    """Async wrapper around `ensure_element_id_sync`. Use from FastAPI handlers."""
    return await asyncio.to_thread(
        ensure_element_id_sync,
        name=name,
        description=description,
        image_url=image_url,
        refer_urls=list(refer_urls) if refer_urls else None,
        product_id=product_id,
        influencer_id=influencer_id,
    )
