-- Managed Agents — persistent chat thread per (user, project)
-- One row per (user, project) holds the Anthropic session id + the full
-- chat history as a JSONB array of turn objects. RLS ensures users can
-- only see/modify their own threads.

CREATE TABLE IF NOT EXISTS public.agent_threads (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id           uuid NOT NULL,
    anthropic_session_id text,
    title                text,
    turns                jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);

-- one active thread per (user, project)
CREATE UNIQUE INDEX IF NOT EXISTS agent_threads_user_project_key
    ON public.agent_threads(user_id, project_id);

ALTER TABLE public.agent_threads ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_threads_owner_select ON public.agent_threads;
CREATE POLICY agent_threads_owner_select ON public.agent_threads
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS agent_threads_owner_insert ON public.agent_threads;
CREATE POLICY agent_threads_owner_insert ON public.agent_threads
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS agent_threads_owner_update ON public.agent_threads;
CREATE POLICY agent_threads_owner_update ON public.agent_threads
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS agent_threads_owner_delete ON public.agent_threads;
CREATE POLICY agent_threads_owner_delete ON public.agent_threads
    FOR DELETE USING (auth.uid() = user_id);

COMMENT ON TABLE public.agent_threads IS 'Persistent Aitoma creative-director agent chat threads. One row per (user, project).';
COMMENT ON COLUMN public.agent_threads.turns IS 'JSONB array of turn objects: {role, text, artifacts?, ts}.';
COMMENT ON COLUMN public.agent_threads.anthropic_session_id IS 'Cached Anthropic Managed Agents session id so multi-turn chats reuse one session.';
