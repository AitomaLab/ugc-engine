-- Migration 031: Add project_id indexes for product_shots and video_jobs.
--
-- The /projects list and /projects/{id} detail endpoints filter both tables by
-- project_id via large IN (...) queries. Without these indexes Postgres falls
-- back to seq scans on large tenant tables, dominating end-to-end latency on
-- the dashboard and project-open paths.
--
-- Composite (project_id, created_at desc) lets the planner satisfy both the
-- equality/IN filter and the existing ORDER BY in one index scan.
--
-- Note: the Supabase SQL Editor wraps statements in a transaction, which
-- conflicts with CREATE INDEX CONCURRENTLY. The plain CREATE INDEX form
-- below takes a brief ACCESS EXCLUSIVE lock during creation — fine at our
-- current data size. If you later need zero-downtime index builds, run the
-- CONCURRENTLY variant from psql (outside any transaction).
-- Safe to re-run thanks to IF NOT EXISTS.

CREATE INDEX IF NOT EXISTS idx_product_shots_project_id_created_at
    ON public.product_shots (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_video_jobs_project_id_created_at
    ON public.video_jobs (project_id, created_at DESC);

-- Also helps `/projects` list (filters projects by user_id, orders by updated_at desc).
-- 026 already has idx_projects_user_updated_at; nothing to add there.
