-- 065_onboarding_responses.sql
-- ICP onboarding questionnaire answers collected during first-time user flow.
-- Additive only. Safe to run multiple times.

CREATE TABLE IF NOT EXISTS public.onboarding_responses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    email           TEXT,
    role            TEXT NOT NULL,
    team_size       TEXT NOT NULL,
    challenge       TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    monthly_volume  TEXT NOT NULL,
    ui_language     TEXT,
    completed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS onboarding_responses_completed_at_idx
    ON public.onboarding_responses (completed_at DESC);
