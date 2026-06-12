-- 042_invite_codes.sql
-- Gated beta: one single-use invite code per waitlist email. A user can only
-- sign up by supplying the code generated for their exact email address. No
-- multi-use or referral sharing at this stage.
--
-- NOTE: The canonical invite_codes migration + before-user-created auth hook
-- are maintained separately and run manually in the Supabase SQL Editor. This
-- file is an additive, IF-NOT-EXISTS fallback that documents the minimal shape
-- the backend admin router relies on; it is a no-op if the table already exists.

CREATE TABLE IF NOT EXISTS public.invite_codes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT,
    code          TEXT NOT NULL UNIQUE,
    label         TEXT,
    -- Flipped true (with used_at) by the before-user-created auth hook once consumed.
    is_used       BOOLEAN NOT NULL DEFAULT FALSE,
    used_at       TIMESTAMPTZ,
    -- True once the code has been written to the Brevo contact's INVITE_CODE.
    brevo_synced  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One code per email (case-insensitive) + fast filtering of the sync backlog.
CREATE UNIQUE INDEX IF NOT EXISTS invite_codes_email_lower_idx
    ON public.invite_codes (LOWER(email))
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS invite_codes_brevo_synced_idx
    ON public.invite_codes (brevo_synced);
