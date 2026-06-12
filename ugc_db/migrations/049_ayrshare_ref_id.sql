-- 040_ayrshare_ref_id.sql
-- Store Ayrshare refId alongside profileKey for profile lookups and OAuth propagation.

ALTER TABLE ayrshare_profiles
    ADD COLUMN IF NOT EXISTS ayrshare_ref_id TEXT;

CREATE INDEX IF NOT EXISTS idx_ayrshare_profiles_ref_id
    ON ayrshare_profiles (ayrshare_ref_id)
    WHERE ayrshare_ref_id IS NOT NULL;
