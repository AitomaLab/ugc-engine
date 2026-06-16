-- 041_analytics_strategy_report.sql
-- Analytics AI Strategy Report: per-account "Do More / Do Less" markdown report.
--
-- Additive only — does not drop, rename, or modify any column already in use.
-- Safe to re-run (IF NOT EXISTS throughout). Builds on migration 035.

-- Persisted AI strategy report surfaced in the Account Detail modal. Stored
-- directly on the tracked-account row so the UI can fetch it in a single
-- read alongside the rest of the account metadata. The user-level feedback
-- loop continues to write to `agent_memories` (migration 028) separately.
ALTER TABLE public.analytics_tracked_accounts
    ADD COLUMN IF NOT EXISTS ai_strategy_report TEXT;

ALTER TABLE public.analytics_tracked_accounts
    ADD COLUMN IF NOT EXISTS ai_strategy_generated_at TIMESTAMPTZ;
