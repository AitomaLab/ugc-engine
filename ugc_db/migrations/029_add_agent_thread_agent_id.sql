-- Track which Anthropic agent_id each session was created under.
-- Sessions on Anthropic's side are bound to an agent_id at creation time —
-- once tied, they keep using that agent's tool list + system prompt forever.
-- When we re-create the agent (e.g. to add a new tool like `memory`), old
-- sessions silently keep using the stale agent definition. Storing the
-- agent_id alongside the session_id lets us detect the mismatch on resume
-- and force a fresh session against the current agent.

ALTER TABLE public.agent_threads
    ADD COLUMN IF NOT EXISTS anthropic_agent_id text;

COMMENT ON COLUMN public.agent_threads.anthropic_agent_id IS
    'Agent ID this session was created under. Used to invalidate stored sessions when the underlying agent is re-created (tool list or system prompt change).';
