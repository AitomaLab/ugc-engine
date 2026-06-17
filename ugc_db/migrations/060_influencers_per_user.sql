-- Migration 060: Influencers per user account (not per project)
--
-- Run in Supabase SQL Editor (idempotent). Safe to re-run after diagnostics show 0 dup groups.
--
-- 1) Re-point FKs from duplicate rows to the keeper row per (user_id, name)
-- 2) Delete duplicate influencer rows across projects for the same user
-- 3) Replace per-project unique index with per-user unique index

-- 1) Build keeper / dupe mapping
WITH ranked AS (
    SELECT
        id,
        user_id,
        lower(btrim(name)) AS norm_name,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, lower(btrim(name))
            ORDER BY
                (image_url IS NOT NULL AND btrim(image_url) <> '') DESC,
                created_at ASC NULLS LAST,
                id ASC
        ) AS rn
    FROM public.influencers
    WHERE user_id IS NOT NULL
      AND btrim(name) <> ''
),
dupes AS (
    SELECT r.id AS dupe_id, k.id AS keeper_id
    FROM ranked r
    JOIN ranked k
      ON k.user_id = r.user_id
     AND k.norm_name = r.norm_name
     AND k.rn = 1
    WHERE r.rn > 1
)
UPDATE public.video_jobs j
SET influencer_id = d.keeper_id
FROM dupes d
WHERE j.influencer_id = d.dupe_id;

WITH ranked AS (
    SELECT
        id,
        user_id,
        lower(btrim(name)) AS norm_name,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, lower(btrim(name))
            ORDER BY
                (image_url IS NOT NULL AND btrim(image_url) <> '') DESC,
                created_at ASC NULLS LAST,
                id ASC
        ) AS rn
    FROM public.influencers
    WHERE user_id IS NOT NULL
      AND btrim(name) <> ''
),
dupes AS (
    SELECT r.id AS dupe_id, k.id AS keeper_id
    FROM ranked r
    JOIN ranked k
      ON k.user_id = r.user_id
     AND k.norm_name = r.norm_name
     AND k.rn = 1
    WHERE r.rn > 1
)
UPDATE public.scripts s
SET influencer_id = d.keeper_id
FROM dupes d
WHERE s.influencer_id = d.dupe_id;

-- 2) Remove cross-project duplicate names per user
WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, lower(btrim(name))
            ORDER BY
                (image_url IS NOT NULL AND btrim(image_url) <> '') DESC,
                created_at ASC NULLS LAST,
                id ASC
        ) AS rn
    FROM public.influencers
    WHERE user_id IS NOT NULL
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

-- 3) Per-user unique name index (replaces per-project index from 054)
DROP INDEX IF EXISTS idx_influencers_project_name_unique;

CREATE UNIQUE INDEX IF NOT EXISTS idx_influencers_user_name_unique
    ON public.influencers (user_id, lower(btrim(name)))
    WHERE user_id IS NOT NULL AND btrim(name) <> '';

COMMENT ON INDEX idx_influencers_user_name_unique IS
    'One influencer name per user account (templates + custom share the same roster).';
