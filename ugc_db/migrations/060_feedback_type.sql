-- 060_feedback_type.sql
-- Distinguish general feedback from feature requests.
-- Additive only. Safe to run multiple times.

ALTER TABLE public.feedback
    ADD COLUMN IF NOT EXISTS type TEXT NOT NULL DEFAULT 'feedback';

ALTER TABLE public.feedback
    DROP CONSTRAINT IF EXISTS feedback_type_check;

ALTER TABLE public.feedback
    ADD CONSTRAINT feedback_type_check CHECK (type IN ('feedback', 'feature'));

CREATE INDEX IF NOT EXISTS feedback_type_idx ON public.feedback (type);
