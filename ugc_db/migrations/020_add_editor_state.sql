-- 020_add_editor_state.sql
-- Adds columns needed for the Remotion Editor integration.
-- Safe to run multiple times (IF NOT EXISTS throughout).
-- ADDITIVE ONLY — no existing columns are modified or removed.

-- Store the Whisper transcription so the Editor can load captions without re-running Whisper
ALTER TABLE public.video_jobs
  ADD COLUMN IF NOT EXISTS transcription JSONB DEFAULT NULL;

-- Store video dimensions for the Editor state builder
ALTER TABLE public.video_jobs
  ADD COLUMN IF NOT EXISTS video_duration_seconds FLOAT DEFAULT NULL;

ALTER TABLE public.video_jobs
  ADD COLUMN IF NOT EXISTS video_width INTEGER DEFAULT 1080;

ALTER TABLE public.video_jobs
  ADD COLUMN IF NOT EXISTS video_height INTEGER DEFAULT 1920;

-- Store the Editor state so users can resume editing a video
ALTER TABLE public.video_jobs
  ADD COLUMN IF NOT EXISTS editor_state JSONB DEFAULT NULL;

-- Comments for documentation
COMMENT ON COLUMN public.video_jobs.transcription IS
  'Whisper word-level transcription: {"text": "...", "words": [{"word": "...", "start": 0.0, "end": 0.32}]}';

COMMENT ON COLUMN public.video_jobs.video_duration_seconds IS
  'Duration of the final video in seconds, used to build the Editor state.';

COMMENT ON COLUMN public.video_jobs.video_width IS
  'Width of the final video in pixels. Defaults to 1080.';

COMMENT ON COLUMN public.video_jobs.video_height IS
  'Height of the final video in pixels. Defaults to 1920.';

COMMENT ON COLUMN public.video_jobs.editor_state IS
  'Saved Remotion Editor UndoableState JSON for resuming edits.';
