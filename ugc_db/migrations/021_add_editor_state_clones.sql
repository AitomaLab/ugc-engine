-- Add editor columns to clone_video_jobs for Remotion Editor support
-- Mirrors the columns added to video_jobs in 020_add_editor_state.sql

ALTER TABLE clone_video_jobs
    ADD COLUMN IF NOT EXISTS editor_state JSONB DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS video_duration_seconds FLOAT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS video_width INT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS video_height INT DEFAULT NULL;

COMMENT ON COLUMN clone_video_jobs.editor_state IS 'Remotion Editor UndoableState JSON';
