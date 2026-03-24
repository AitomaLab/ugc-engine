-- 012_add_social_scheduling.sql
-- Adds tables for Ayrshare social media scheduling integration.
-- Safe to run multiple times (IF NOT EXISTS / IF EXISTS throughout).

-- Drop the old placeholder social_posts table (only contained mock data
-- from the unused BlotatoPoster Celery tasks — never served by any endpoint).
DROP TABLE IF EXISTS social_posts;

-- ─────────────────────────────────────────────────────────────────────────────
-- ayrshare_profiles: maps UGC Engine users → Ayrshare Profile Keys
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ayrshare_profiles (
    user_id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    ayrshare_profile_key TEXT NOT NULL UNIQUE,
    connected_accounts   JSONB DEFAULT '{}',
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE ayrshare_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ayrshare_profiles_user_policy ON ayrshare_profiles;
CREATE POLICY ayrshare_profiles_user_policy ON ayrshare_profiles
    FOR ALL USING (user_id = auth.uid());

-- ─────────────────────────────────────────────────────────────────────────────
-- social_posts: persistent record for every scheduled / posted / failed post
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS social_posts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    video_job_id      UUID REFERENCES video_jobs(id) ON DELETE CASCADE,
    ayrshare_post_id  TEXT,
    status            TEXT NOT NULL DEFAULT 'scheduled',
    platform          TEXT NOT NULL,
    caption           TEXT,
    hashtags          TEXT[],
    scheduled_at      TIMESTAMPTZ NOT NULL,
    posted_at         TIMESTAMPTZ,
    error_message     TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE social_posts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS social_posts_user_policy ON social_posts;
CREATE POLICY social_posts_user_policy ON social_posts
    FOR ALL USING (user_id = auth.uid());

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_social_posts_user_id      ON social_posts (user_id);
CREATE INDEX IF NOT EXISTS idx_social_posts_status        ON social_posts (status);
CREATE INDEX IF NOT EXISTS idx_social_posts_scheduled_at  ON social_posts (scheduled_at);
