-- Competitor manager (Slice 3) — the workspace's named competitors.
--
-- Per-user, RLS-scoped. Competitor SCRAPES never touch analytics_posts
-- (that table is the user's own analytics); competitor posts land in
-- brand_research as observations with full provenance. This table is only
-- the list of who to watch.

CREATE TABLE IF NOT EXISTS public.brand_competitors (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    platform   text NOT NULL CHECK (platform IN ('instagram', 'tiktok', 'youtube', 'facebook')),
    handle     text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS brand_competitors_unique
    ON public.brand_competitors(user_id, platform, lower(handle));

ALTER TABLE public.brand_competitors ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS brand_competitors_owner_all ON public.brand_competitors;
CREATE POLICY brand_competitors_owner_all ON public.brand_competitors
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

COMMENT ON TABLE public.brand_competitors IS 'Named competitor accounts per user (max enforced in code). Scrape results go to brand_research, never analytics_posts.';
