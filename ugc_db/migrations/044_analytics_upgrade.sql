-- 035_analytics_upgrade.sql
-- Analytics module v2: scrape configuration, account health, settings.
--
-- Additive only — does not drop, rename, or modify any column already in use.
-- Safe to re-run (IF NOT EXISTS / IF EXISTS throughout). Built on top of
-- migration 033 (base schema) and 034 (added_at + storage_video_url).

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. analytics_tracked_accounts — scrape config + health metrics
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.analytics_tracked_accounts
    ADD COLUMN IF NOT EXISTS scrape_frequency TEXT DEFAULT 'daily'
        CHECK (scrape_frequency IN ('manual','hourly','6h','12h','daily','weekly'));

ALTER TABLE public.analytics_tracked_accounts
    ADD COLUMN IF NOT EXISTS top_n_retention INTEGER DEFAULT 10
        CHECK (top_n_retention >= 1 AND top_n_retention <= 200);

ALTER TABLE public.analytics_tracked_accounts
    ADD COLUMN IF NOT EXISTS health_score INTEGER
        CHECK (health_score IS NULL OR (health_score >= 0 AND health_score <= 100));

-- Migration 033 already created `followers INTEGER`. The v2 spec calls for
-- `follower_count`; we keep both for backwards-compat and backfill the new
-- column from the old one so downstream code can standardise on
-- `follower_count` going forward.
ALTER TABLE public.analytics_tracked_accounts
    ADD COLUMN IF NOT EXISTS follower_count INTEGER;

UPDATE public.analytics_tracked_accounts
   SET follower_count = followers
 WHERE follower_count IS NULL AND followers IS NOT NULL;

-- last_scraped_at already exists from 033 — repeated here only to keep the
-- spec self-contained. The IF NOT EXISTS guard makes this a no-op.
ALTER TABLE public.analytics_tracked_accounts
    ADD COLUMN IF NOT EXISTS last_scraped_at TIMESTAMPTZ;


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. analytics_posts — convenience flag for the "Studio vs External" delta
--    on the account detail modal. Computed from existing `social_post_id` so
--    we never have to keep it in sync from app code.
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.analytics_posts
    ADD COLUMN IF NOT EXISTS is_studio_published BOOLEAN
        GENERATED ALWAYS AS (social_post_id IS NOT NULL) STORED;

CREATE INDEX IF NOT EXISTS idx_analytics_posts_is_studio_published
    ON public.analytics_posts (is_studio_published);


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. analytics_settings — per-tenant defaults + cost alerts
--    (BrightData API token stays env-managed for security — surfaced via UI
--    as a read-only "configured" status, never round-tripped through the DB.)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.analytics_settings (
    user_id                   UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    default_scrape_frequency  TEXT DEFAULT 'daily'
                              CHECK (default_scrape_frequency IN ('manual','hourly','6h','12h','daily','weekly')),
    default_top_n             INTEGER DEFAULT 10
                              CHECK (default_top_n >= 1 AND default_top_n <= 200),
    monthly_budget_limit_usd  NUMERIC(10, 2) DEFAULT 10.00,
    alert_threshold_usd       NUMERIC(10, 2) DEFAULT 0.05,
    updated_at                TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.analytics_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS asettings_user_policy ON public.analytics_settings;
CREATE POLICY asettings_user_policy ON public.analytics_settings
    FOR ALL USING (auth.uid() = user_id);
