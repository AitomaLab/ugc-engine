-- Migration 041: provider_job_id for durable asset job recovery
--
-- Run in the Supabase SQL Editor. Idempotent (IF NOT EXISTS everywhere).
--
-- Context:
--   Image/video completion writeback runs as an in-process asyncio task
--   (WaveSpeed/KIE) or a blocking SDK call (fal.ai) inside creative-os.
--   If the process restarts mid-generation, the provider finishes but the
--   row is stranded in "processing" forever. Persisting the provider job
--   ID at submit time lets the jobs-status recovery sweep re-query the
--   provider and finalize the row.
--
-- Format (prefix encodes which API to query):
--   wavespeed:<prediction_id>
--   kie:<task_id>
--   fal:<model_id>:<request_id>

ALTER TABLE public.product_shots
    ADD COLUMN IF NOT EXISTS provider_job_id TEXT;

ALTER TABLE public.video_jobs
    ADD COLUMN IF NOT EXISTS provider_job_id TEXT;

COMMENT ON COLUMN public.product_shots.provider_job_id IS
    'Provider job reference persisted at submit time (wavespeed:<id> | kie:<taskId> | fal:<model>:<requestId>). Used by the jobs-status recovery sweep to finalize rows orphaned by a creative-os restart.';

COMMENT ON COLUMN public.video_jobs.provider_job_id IS
    'Provider job reference persisted at submit time (wavespeed:<id> | kie:<taskId> | fal:<model>:<requestId>). Used by the jobs-status recovery sweep to finalize rows orphaned by a creative-os restart.';
