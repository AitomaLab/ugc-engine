-- Add gender column to user_ai_clones
-- Used by Nano Banana Pro composite prompts (must not default to 'woman')
ALTER TABLE user_ai_clones
ADD COLUMN IF NOT EXISTS gender TEXT NOT NULL DEFAULT 'male';
