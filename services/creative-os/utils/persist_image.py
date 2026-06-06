"""Backward-compatible re-exports — see persist_media.py for implementation."""

from utils.persist_media import (  # noqa: F401
    EPHEMERAL_HOSTS,
    PRODUCT_IMAGES_BUCKET,
    PersistMediaError,
    finalize_image_url,
    finalize_video_url,
    is_ephemeral_url,
    is_supabase_storage_url,
    needs_persistence,
    persist_image_url,
    persist_video_url,
    schedule_image_persist_retry,
    schedule_video_persist_retry,
)
