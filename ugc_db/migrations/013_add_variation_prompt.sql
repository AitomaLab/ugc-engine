-- Migration 013: Add variation_prompt column to video_jobs
-- Stores the AI-generated per-job environment/setting variation prompt
-- for the Dynamic Influencer Variation feature (bulk digital campaigns).
-- NULL = use the influencer's default setting (the ~30% "original" path).

ALTER TABLE video_jobs
ADD COLUMN IF NOT EXISTS variation_prompt TEXT;

COMMENT ON COLUMN video_jobs.variation_prompt IS
  'AI-generated scene environment override for campaign diversity (NULL = use influencer default setting)';
