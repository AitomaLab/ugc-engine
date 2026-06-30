-- 067_invite_codes_list_id.sql
-- Tie invite codes to a Brevo list tab (3 = Waitlist, 10 = Beta Testers) so manual
-- admin-generated codes appear under the correct list in /admin.

ALTER TABLE public.invite_codes
    ADD COLUMN IF NOT EXISTS list_id INTEGER;

UPDATE public.invite_codes
SET list_id = 3
WHERE list_id IS NULL AND label = 'Brevo Waitlist';

UPDATE public.invite_codes
SET list_id = 10
WHERE list_id IS NULL AND label = 'Beta Testers';

-- Manual / custom admin codes default to Waitlist (list 3).
UPDATE public.invite_codes
SET list_id = 3
WHERE list_id IS NULL
  AND label IS NOT NULL
  AND label NOT IN ('Brevo Waitlist', 'Beta Testers')
  AND label NOT LIKE 'Brevo List %';

CREATE INDEX IF NOT EXISTS invite_codes_list_id_idx
    ON public.invite_codes (list_id);
