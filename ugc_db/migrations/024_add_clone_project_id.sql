-- Add project_id to clone_video_jobs so clone videos are scoped to projects
-- (matching the same pattern as video_jobs which already has project_id)

ALTER TABLE clone_video_jobs ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;

-- Index for fast project-scoped lookups
CREATE INDEX IF NOT EXISTS idx_clone_video_jobs_project_id ON clone_video_jobs(project_id);

COMMENT ON COLUMN clone_video_jobs.project_id IS 'Project this clone video belongs to. Enables per-project scoping in Creative OS.';
