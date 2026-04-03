-- 019_add_language_preferences.sql
-- Adds UI language preference to profiles and video language to jobs.
-- Safe to run multiple times (IF NOT EXISTS).
-- ALREADY EXECUTED by user.

-- 1. Add UI language preference to user profiles
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS ui_language TEXT DEFAULT 'en';

COMMENT ON COLUMN public.profiles.ui_language IS 'User preferred UI language: en | es. Defaults to en.';

-- 2. Add video generation language to video_jobs
ALTER TABLE public.video_jobs
  ADD COLUMN IF NOT EXISTS video_language TEXT DEFAULT 'en';

COMMENT ON COLUMN public.video_jobs.video_language IS 'Target language for video generation (script, TTS, subtitles): en | es. Defaults to en.';

-- 3. Add video generation language to clone_video_jobs
ALTER TABLE public.clone_video_jobs
  ADD COLUMN IF NOT EXISTS video_language TEXT DEFAULT 'en';

COMMENT ON COLUMN public.clone_video_jobs.video_language IS 'Target language for clone video generation: en | es. Defaults to en.';
