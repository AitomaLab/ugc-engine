-- Track last status transition on analytics_video_breakdowns for stale-job detection.
ALTER TABLE analytics_video_breakdowns
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

UPDATE analytics_video_breakdowns
SET updated_at = COALESCE(completed_at, created_at, NOW())
WHERE updated_at IS NULL;

COMMENT ON COLUMN analytics_video_breakdowns.updated_at IS
    'Last write to this row — used to detect orphaned pending/running jobs';
