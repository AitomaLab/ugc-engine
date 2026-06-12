-- 034_analytics_added_at_and_storage.sql
-- Analytics module follow-up to 033:
--   * Adds `added_at` so the Publish → Analytics period pills filter by "when
--     the user added the post to their tracking", not by when the post was
--     originally published on the social platform.
--   * Adds `storage_video_url` so we can mirror BrightData video CDN URLs
--     (which expire + block CORS) into Supabase Storage and use the stable
--     URL for both inline playback and Gemini video downloads.
--
-- Idempotent / safe to re-run. Backfills `added_at` from the existing
-- `scraped_at` value so older rows keep a sensible "tracked-at" timestamp.

-- ── 1. Columns ────────────────────────────────────────────────────────────
ALTER TABLE analytics_posts
    ADD COLUMN IF NOT EXISTS added_at         TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE analytics_posts
    ADD COLUMN IF NOT EXISTS storage_video_url TEXT;

-- ── 2. Backfill `added_at` for pre-existing rows ──────────────────────────
UPDATE analytics_posts
   SET added_at = COALESCE(added_at, scraped_at, NOW())
 WHERE added_at IS NULL;

-- ── 3. Index for the period-filter query path ─────────────────────────────
CREATE INDEX IF NOT EXISTS idx_analytics_posts_added_at
    ON analytics_posts (added_at DESC);
