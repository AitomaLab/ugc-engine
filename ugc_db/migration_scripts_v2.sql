-- ==========================================================================
-- Scripts Engine v2 Migration
-- Adds structured script support (script_json, methodology, video_length,
-- source, is_trending, times_used) and Row-Level Security.
--
-- Safe to run multiple times (all operations use IF NOT EXISTS / IF EXISTS).
-- Existing rows are preserved -- all new columns have defaults or are nullable.
-- ==========================================================================

-- 1. Add new columns to the existing scripts table
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS script_json JSONB;
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS methodology TEXT NOT NULL DEFAULT 'Hook/Benefit/CTA';
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS video_length INTEGER NOT NULL DEFAULT 15;
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS product_id UUID REFERENCES products(id) ON DELETE SET NULL;
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS influencer_id UUID REFERENCES influencers(id) ON DELETE SET NULL;
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS is_trending BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS times_used INTEGER NOT NULL DEFAULT 0;

-- 2. Ensure the 'name' column exists (legacy table may use 'name' already)
ALTER TABLE scripts ADD COLUMN IF NOT EXISTS name TEXT;

-- 3. Ensure the 'category' column exists with a default
-- (It may already exist without a default, so we just set a default)
ALTER TABLE scripts ALTER COLUMN category SET DEFAULT 'General';

-- 4. Enable Row-Level Security
ALTER TABLE scripts ENABLE ROW LEVEL SECURITY;

-- 5. Create RLS policies (drop first if they exist to make re-runs safe)
DROP POLICY IF EXISTS scripts_select ON scripts;
DROP POLICY IF EXISTS scripts_insert ON scripts;
DROP POLICY IF EXISTS scripts_update ON scripts;
DROP POLICY IF EXISTS scripts_delete ON scripts;

-- Allow reads for own scripts OR scripts with no user_id (legacy rows)
CREATE POLICY scripts_select ON scripts
    FOR SELECT USING (user_id = auth.uid() OR user_id IS NULL);

-- Allow inserts only for the authenticated user
CREATE POLICY scripts_insert ON scripts
    FOR INSERT WITH CHECK (user_id = auth.uid());

-- Allow updates only for own scripts or legacy (no user_id)
CREATE POLICY scripts_update ON scripts
    FOR UPDATE USING (user_id = auth.uid() OR user_id IS NULL);

-- Allow deletes only for own scripts or legacy (no user_id)
CREATE POLICY scripts_delete ON scripts
    FOR DELETE USING (user_id = auth.uid() OR user_id IS NULL);

-- 6. Create indexes for common filter patterns
CREATE INDEX IF NOT EXISTS idx_scripts_user_id ON scripts(user_id);
CREATE INDEX IF NOT EXISTS idx_scripts_category ON scripts(category);
CREATE INDEX IF NOT EXISTS idx_scripts_methodology ON scripts(methodology);
CREATE INDEX IF NOT EXISTS idx_scripts_source ON scripts(source);
CREATE INDEX IF NOT EXISTS idx_scripts_is_trending ON scripts(is_trending);
