-- Add music_enabled column to video_jobs and clone_video_jobs tables
-- Defaults to true (music is enabled by default)

ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS music_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE clone_video_jobs ADD COLUMN IF NOT EXISTS music_enabled BOOLEAN DEFAULT TRUE;
