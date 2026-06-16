-- 036_analytics_studio_connections.sql
-- Persist which analytics_tracked_accounts rows correspond to OAuth-linked
-- profiles managed through Ayrshare (/connections). The UI "Studio accounts"
-- filter prefers this authoritative flag plus a periodic sync endpoint that
-- mirrors live Ayrshare state into Postgres.

ALTER TABLE public.analytics_tracked_accounts
    ADD COLUMN IF NOT EXISTS linked_via_connections BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_ata_linked_connections
    ON public.analytics_tracked_accounts (user_id, linked_via_connections)
    WHERE linked_via_connections = TRUE;
