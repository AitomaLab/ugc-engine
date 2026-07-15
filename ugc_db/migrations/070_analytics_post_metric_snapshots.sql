-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 070: analytics_post_metric_snapshots
--
-- Per-post metric history so we can compute engagement RECEIVED in a window
-- (current metrics − snapshot N days ago), in addition to the existing
-- publish-date view. analytics_posts holds only the latest cumulative values;
-- this table appends a daily snapshot of those values.
--
-- Captured once per post per UTC day (deduped in app code). Ayrshare-
-- independent — it reads existing analytics_posts rows only.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS analytics_post_metric_snapshots (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    analytics_post_id  UUID NOT NULL REFERENCES analytics_posts(id) ON DELETE CASCADE,
    views              BIGINT,
    likes              BIGINT,
    comments           BIGINT,
    shares             BIGINT,
    saves              BIGINT,
    total_engagement   BIGINT,
    captured_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    captured_date      DATE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')::date,
    UNIQUE (analytics_post_id, captured_date)
);

ALTER TABLE analytics_post_metric_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS apms_user_policy ON analytics_post_metric_snapshots;
CREATE POLICY apms_user_policy ON analytics_post_metric_snapshots
    FOR ALL USING (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS idx_apms_post_captured
    ON analytics_post_metric_snapshots (analytics_post_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_apms_user_captured
    ON analytics_post_metric_snapshots (user_id, captured_at DESC);
