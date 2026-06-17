-- 061_feedback.sql
-- Beta tester feedback collected via the global feedback bubble.
-- Additive only. Safe to run multiple times.

CREATE TABLE IF NOT EXISTS public.feedback (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID,                 -- nullable; the submitting user's id if available
    name         TEXT NOT NULL,
    email        TEXT,                 -- captured from session if available
    message      TEXT NOT NULL,
    image_url    TEXT,                 -- public URL of the attached image, if any
    status       TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'complete' | 'archived'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS feedback_status_idx ON public.feedback (status);
CREATE INDEX IF NOT EXISTS feedback_created_at_idx ON public.feedback (created_at DESC);
