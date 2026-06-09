-- Migration 033: CTO Agent conversation logging
-- Captures every Q&A pair sent to the virtual CTO chat hosted in
-- services/cto-agent so we can review what VC analysts asked and where
-- the agent's answers may need tuning.

CREATE TABLE IF NOT EXISTS cto_agent_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    visitor_label TEXT,
    user_agent TEXT,
    ip_hash TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cto_conversations_session
    ON cto_agent_conversations(session_id);

CREATE INDEX IF NOT EXISTS idx_cto_conversations_created
    ON cto_agent_conversations(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cto_conversations_visitor
    ON cto_agent_conversations(visitor_label);

CREATE TABLE IF NOT EXISTS cto_agent_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL
        REFERENCES cto_agent_conversations(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    tokens_in INT,
    tokens_out INT,
    latency_ms INT,
    flagged BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_cto_messages_conversation
    ON cto_agent_messages(conversation_id);

CREATE INDEX IF NOT EXISTS idx_cto_messages_created
    ON cto_agent_messages(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cto_messages_flagged
    ON cto_agent_messages(flagged) WHERE flagged = TRUE;

-- Service-role inserts only; no client-side access required.
-- RLS denies all by default; service key bypasses RLS.
ALTER TABLE cto_agent_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE cto_agent_messages ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE cto_agent_conversations IS
    'One row per chat session with the virtual CTO agent (services/cto-agent).';
COMMENT ON TABLE cto_agent_messages IS
    'Individual messages within a CTO agent conversation. `flagged` is used during review for answers that need persona tuning.';
