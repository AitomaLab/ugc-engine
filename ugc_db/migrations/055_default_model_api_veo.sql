-- Migration 055: Default video_jobs.model_api to veo-3.1-fast (purge seedance-1.5)
--
-- Run in Supabase SQL Editor (idempotent). Safe to re-run.
--
-- seedance-1.5-pro is never used. The legacy column default
-- ('seedance-1.5-pro') silently routed any job whose INSERT omitted model_api
-- to bytedance/seedance-1.5-pro on kie.ai. Flip the default to veo-3.1-fast and
-- backfill in-flight jobs so existing pending/processing work re-routes to Veo.

-- 1) Flip the column default so an omitted model_api can never become seedance-1.5
ALTER TABLE public.video_jobs
    ALTER COLUMN model_api SET DEFAULT 'veo-3.1-fast';

-- 2) Backfill stuck/in-flight rows that still carry the legacy value or NULL
UPDATE public.video_jobs
SET model_api = 'veo-3.1-fast'
WHERE (model_api IS NULL OR model_api = 'seedance-1.5-pro')
  AND status IN ('pending', 'processing');
