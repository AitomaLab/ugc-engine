-- Managed Agents — persistent cross-project memory store per user
-- Backs the custom `memory` tool exposed to the creative-director agent.
-- One row per (user, path). The agent stores preferences, brand constraints,
-- style defaults, named-entity facts — anything durable the user teaches it.
-- Scoped by user_id (NOT project_id) so memory follows the user across every
-- project and session.

CREATE TABLE IF NOT EXISTS public.agent_memories (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    path       text NOT NULL,
    content    text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- one file per (user, normalized path)
CREATE UNIQUE INDEX IF NOT EXISTS agent_memories_user_path_key
    ON public.agent_memories(user_id, path);

-- cheap directory listings by prefix match
CREATE INDEX IF NOT EXISTS agent_memories_user_path_prefix
    ON public.agent_memories(user_id, path text_pattern_ops);

ALTER TABLE public.agent_memories ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_memories_owner_select ON public.agent_memories;
CREATE POLICY agent_memories_owner_select ON public.agent_memories
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS agent_memories_owner_insert ON public.agent_memories;
CREATE POLICY agent_memories_owner_insert ON public.agent_memories
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS agent_memories_owner_update ON public.agent_memories;
CREATE POLICY agent_memories_owner_update ON public.agent_memories
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS agent_memories_owner_delete ON public.agent_memories;
CREATE POLICY agent_memories_owner_delete ON public.agent_memories
    FOR DELETE USING (auth.uid() = user_id);

COMMENT ON TABLE public.agent_memories IS 'Persistent cross-project memory files for the Aitoma agent. Scoped per user, not per project. Paths are normalized under /memories/.';
COMMENT ON COLUMN public.agent_memories.path IS 'Normalized memory path, must start with /memories/. No traversal, no empty segments.';
