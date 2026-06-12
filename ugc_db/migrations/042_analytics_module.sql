-- 033_analytics_module.sql
-- Analytics module: scraped social-post performance + Gemini-powered video
-- breakdowns. Self-contained namespace — does not alter any existing tables.
--
-- All tables RLS-scoped to auth.uid(). Safe to re-run (IF NOT EXISTS / IF
-- EXISTS throughout).

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. analytics_tracked_accounts
--    Social handles the user has asked us to monitor over time.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics_tracked_accounts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    platform         TEXT NOT NULL CHECK (platform IN ('tiktok','instagram','youtube','facebook')),
    username         TEXT NOT NULL,
    display_name     TEXT,
    avatar_url       TEXT,
    followers        INTEGER,
    total_posts      INTEGER,
    is_active        BOOLEAN DEFAULT TRUE,
    last_scraped_at  TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, platform, username)
);

ALTER TABLE analytics_tracked_accounts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ata_user_policy ON analytics_tracked_accounts;
CREATE POLICY ata_user_policy ON analytics_tracked_accounts
    FOR ALL USING (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS idx_ata_user ON analytics_tracked_accounts (user_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. analytics_posts
--    Unified record for posts we track — both internally-published (linked to
--    social_posts) and externally-pasted URLs. total_engagement is a STORED
--    generated column; never written to from app code.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics_posts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    source            TEXT NOT NULL CHECK (source IN ('internal','external')),
    social_post_id    UUID REFERENCES social_posts(id) ON DELETE SET NULL,
    video_job_id      UUID REFERENCES video_jobs(id) ON DELETE SET NULL,
    platform          TEXT NOT NULL,
    username          TEXT NOT NULL,
    post_url          TEXT NOT NULL,
    external_post_id  TEXT,
    caption           TEXT,
    hashtags          TEXT[],
    media_type        TEXT,
    media_urls        JSONB DEFAULT '[]'::jsonb,
    thumbnail_url     TEXT,
    duration_seconds  NUMERIC,
    posted_at         TIMESTAMPTZ,
    views             BIGINT,
    likes             BIGINT,
    comments          BIGINT,
    shares            BIGINT,
    saves             BIGINT,
    total_engagement  BIGINT GENERATED ALWAYS AS (
        COALESCE(likes, 0)
      + COALESCE(comments, 0)
      + COALESCE(shares, 0)
      + COALESCE(saves, 0)
    ) STORED,
    raw_payload       JSONB,
    scraped_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, platform, post_url)
);

ALTER TABLE analytics_posts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ap_user_policy ON analytics_posts;
CREATE POLICY ap_user_policy ON analytics_posts
    FOR ALL USING (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS idx_analytics_posts_user        ON analytics_posts (user_id);
CREATE INDEX IF NOT EXISTS idx_analytics_posts_posted_at   ON analytics_posts (posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_posts_engagement  ON analytics_posts (total_engagement DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_posts_platform    ON analytics_posts (platform);
CREATE INDEX IF NOT EXISTS idx_analytics_posts_source      ON analytics_posts (source);


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. analytics_scrape_jobs
--    Audit + cost trail for BrightData runs.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics_scrape_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    kind                TEXT NOT NULL CHECK (kind IN ('post','account','batch')),
    input               TEXT NOT NULL,
    platform            TEXT,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','running','completed','failed')),
    posts_found         INTEGER,
    brightdata_calls    INTEGER DEFAULT 0,
    estimated_cost_usd  NUMERIC(10, 4),
    snapshot_id         TEXT,
    error_message       TEXT,
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

ALTER TABLE analytics_scrape_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS asj_user_policy ON analytics_scrape_jobs;
CREATE POLICY asj_user_policy ON analytics_scrape_jobs
    FOR ALL USING (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS idx_asj_user   ON analytics_scrape_jobs (user_id);
CREATE INDEX IF NOT EXISTS idx_asj_status ON analytics_scrape_jobs (status);


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. analytics_video_breakdowns
--    Per-video AI breakdown (Gemini, via KIE / FAL / direct). One breakdown
--    per analytics_post OR per internal video_job. Enforced via partial unique
--    indexes so the column can stay NULL on the other side.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics_video_breakdowns (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    analytics_post_id   UUID REFERENCES analytics_posts(id) ON DELETE CASCADE,
    video_job_id        UUID REFERENCES video_jobs(id) ON DELETE CASCADE,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','running','completed','failed')),
    model               TEXT,
    provider            TEXT,
    summary             TEXT,
    hook                JSONB,
    scenes              JSONB,
    audio               JSONB,
    visual_details      JSONB,
    key_moments         JSONB,
    takeaways           JSONB,
    raw_markdown        TEXT,
    cost_usd            NUMERIC(10, 4),
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    CHECK (
        (analytics_post_id IS NOT NULL AND video_job_id IS NULL)
     OR (analytics_post_id IS NULL AND video_job_id IS NOT NULL)
    )
);

ALTER TABLE analytics_video_breakdowns ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS avb_user_policy ON analytics_video_breakdowns;
CREATE POLICY avb_user_policy ON analytics_video_breakdowns
    FOR ALL USING (user_id = auth.uid());

CREATE UNIQUE INDEX IF NOT EXISTS uq_avb_analytics_post
    ON analytics_video_breakdowns (analytics_post_id)
    WHERE analytics_post_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_avb_video_job
    ON analytics_video_breakdowns (video_job_id)
    WHERE video_job_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_avb_user   ON analytics_video_breakdowns (user_id);
CREATE INDEX IF NOT EXISTS idx_avb_status ON analytics_video_breakdowns (status);
