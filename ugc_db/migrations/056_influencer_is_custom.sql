-- Migration 056: Add is_custom flag to influencers
--
-- Run in Supabase SQL Editor (idempotent). Safe to re-run.
--
-- Custom (user-created) influencers should belong to the USER and appear in
-- every one of their projects + the @mention/MODELS picker. Template clones
-- (auto-seeded per project from the admin template roster) stay project-scoped.
-- There was no column distinguishing the two; this adds it.
--
-- Newly created influencers are flagged is_custom=true in the API
-- (api_create_influencer). Existing rows are backfilled by
-- scripts/backfill_is_custom.py (uses the admin template name set).

ALTER TABLE public.influencers
    ADD COLUMN IF NOT EXISTS is_custom BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_influencers_user_custom
    ON public.influencers (user_id, is_custom);

COMMENT ON COLUMN public.influencers.is_custom IS
    'true = user-created influencer (visible across all of the user''s projects); false = per-project template clone.';
