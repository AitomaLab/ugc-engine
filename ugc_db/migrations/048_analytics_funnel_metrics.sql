-- Deeper funnel metrics for the Analytics dashboard.
--
-- Ayrshare exposes impressions / reach / click-through on selected platforms
-- (Instagram Business, Facebook Pages, YouTube). These columns are nullable
-- because BrightData scrapes for external accounts can't fill them in — the
-- dashboard renders a "—" placeholder when null.
ALTER TABLE public.analytics_posts
    ADD COLUMN IF NOT EXISTS impressions     BIGINT,
    ADD COLUMN IF NOT EXISTS reach            BIGINT,
    ADD COLUMN IF NOT EXISTS clicks           BIGINT,
    ADD COLUMN IF NOT EXISTS ctr              NUMERIC(6,4); -- click-through rate, 0.0000–1.0000
