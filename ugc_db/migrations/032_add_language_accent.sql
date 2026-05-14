-- Migration 032: Add language_accent column to video_jobs.
--
-- Stores the user's chosen Spanish accent subtype ("spain" | "latam") so the
-- Veo prompt builders can produce Castilian vs Latin American Spanish. NULL
-- when the video is not Spanish or no preference was specified (in which case
-- prompts/__init__.py:spanish_accent_line falls back to LATAM).
--
-- Safe to re-run.

ALTER TABLE public.video_jobs
    ADD COLUMN IF NOT EXISTS language_accent TEXT;
