-- Add status_message column to clone_video_jobs
-- Shows granular step progress (e.g. "Lip sync: scene 2/4...")
ALTER TABLE clone_video_jobs
ADD COLUMN IF NOT EXISTS status_message TEXT;
