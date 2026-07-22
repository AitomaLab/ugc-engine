-- Brand Studio persistence — move per-user brand state + studio session off
-- ephemeral container disk into Supabase.
--
-- Why: services/creative-os/railway.toml mounts no volume, so
-- data/brands/{user}/brand-state.json and studio-session.json were wiped on
-- every redeploy. One row per user; brand_state and studio_session are the
-- exact JSON payloads the Brand Studio page reads/writes today.
--
-- Writes go through the service-role client (brand_studio.py helpers), same
-- pattern as the analytics agent-memory writes. RLS protects direct
-- client-side access.

CREATE TABLE IF NOT EXISTS public.brand_profiles (
    user_id        uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    brand_state    jsonb,
    studio_session jsonb,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.brand_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS brand_profiles_owner_select ON public.brand_profiles;
CREATE POLICY brand_profiles_owner_select ON public.brand_profiles
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS brand_profiles_owner_insert ON public.brand_profiles;
CREATE POLICY brand_profiles_owner_insert ON public.brand_profiles
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS brand_profiles_owner_update ON public.brand_profiles;
CREATE POLICY brand_profiles_owner_update ON public.brand_profiles
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS brand_profiles_owner_delete ON public.brand_profiles;
CREATE POLICY brand_profiles_owner_delete ON public.brand_profiles
    FOR DELETE USING (auth.uid() = user_id);

COMMENT ON TABLE public.brand_profiles IS 'Brand Studio per-user persistence: brand identity state + working session. Replaces ephemeral on-disk JSON under services/creative-os/data/brands/.';
COMMENT ON COLUMN public.brand_profiles.brand_state IS 'Payload previously stored in brand-state.json (scraped/edited brand identity).';
COMMENT ON COLUMN public.brand_profiles.studio_session IS 'Payload previously stored in studio-session.json (working canvas/session).';
