-- Add progressive scene preview columns to video_jobs and clone_video_jobs
-- These allow the frontend to show intermediate results while a video is generating

ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS preview_url TEXT;
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS preview_type TEXT DEFAULT 'image';
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS status_message TEXT;

ALTER TABLE clone_video_jobs ADD COLUMN IF NOT EXISTS preview_url TEXT;
ALTER TABLE clone_video_jobs ADD COLUMN IF NOT EXISTS preview_type TEXT DEFAULT 'image';
ALTER TABLE clone_video_jobs ADD COLUMN IF NOT EXISTS status_message TEXT;
