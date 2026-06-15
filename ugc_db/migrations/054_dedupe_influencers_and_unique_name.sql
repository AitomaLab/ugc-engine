-- Migration 054: Dedupe influencers per project + block duplicate names per project
--
-- Run in Supabase SQL Editor (idempotent). Safe to re-run after diagnostics show 0 dup groups.
--
-- Keeps the best row per (user_id, project_id, normalized name):
--   prefer rows with image_url, then oldest created_at.
-- Does NOT touch the admin template project rows beyond normal dedupe rules.

-- 1) Remove within-project duplicate names (race-condition leftovers)
WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, project_id, lower(btrim(name))
            ORDER BY
                (image_url IS NOT NULL AND btrim(image_url) <> '') DESC,
                created_at ASC NULLS LAST,
                id ASC
        ) AS rn
    FROM public.influencers
    WHERE user_id IS NOT NULL
      AND project_id IS NOT NULL
      AND btrim(name) <> ''
),
deleted AS (
    DELETE FROM public.influencers i
    USING ranked r
    WHERE i.id = r.id
      AND r.rn > 1
    RETURNING i.id
)
SELECT COUNT(*) AS duplicate_rows_removed FROM deleted;

-- 2) Backfill orphan project_id from user's default project when possible
UPDATE public.influencers i
SET project_id = p.id
FROM public.projects p
WHERE i.project_id IS NULL
  AND i.user_id IS NOT NULL
  AND p.user_id = i.user_id
  AND p.is_default = true;

-- 3) Replace legacy case-sensitive unique constraint with case-insensitive index
ALTER TABLE public.influencers
    DROP CONSTRAINT IF EXISTS influencers_project_name_key;

ALTER TABLE public.influencers
    DROP CONSTRAINT IF EXISTS influencers_name_project_key;

DROP INDEX IF EXISTS idx_influencers_project_name_unique;
CREATE UNIQUE INDEX idx_influencers_project_name_unique
    ON public.influencers (project_id, lower(btrim(name)))
    WHERE project_id IS NOT NULL AND btrim(name) <> '';

COMMENT ON INDEX idx_influencers_project_name_unique IS
    'Prevents duplicate influencer names within the same project (seed race + manual dupes).';
