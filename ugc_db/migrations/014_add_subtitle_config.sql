-- 014_add_subtitle_config.sql
-- Adds user-configurable subtitle preferences to video_jobs.
-- Safe to run multiple times (IF NOT EXISTS throughout).

ALTER TABLE public.video_jobs
  ADD COLUMN IF NOT EXISTS subtitles_enabled  BOOLEAN  DEFAULT true,
  ADD COLUMN IF NOT EXISTS subtitle_style     TEXT     DEFAULT 'hormozi',
  ADD COLUMN IF NOT EXISTS subtitle_placement TEXT     DEFAULT 'middle';

-- Add comments for documentation
COMMENT ON COLUMN public.video_jobs.subtitles_enabled  IS 'Whether to burn subtitles onto the final video. Defaults to true.';
COMMENT ON COLUMN public.video_jobs.subtitle_style     IS 'Subtitle visual style: hormozi | mrbeast | plain. Defaults to hormozi.';
COMMENT ON COLUMN public.video_jobs.subtitle_placement IS 'Vertical placement of subtitles: top | middle | bottom. Defaults to middle.';
