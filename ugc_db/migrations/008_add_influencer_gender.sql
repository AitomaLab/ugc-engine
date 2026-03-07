-- 008: Add gender column to influencers table
-- This enables correct gender references in Veo 3.1 prompts

ALTER TABLE public.influencers
ADD COLUMN IF NOT EXISTS gender TEXT DEFAULT 'Female';

COMMENT ON COLUMN public.influencers.gender IS 'Male or Female — used in video generation prompts';
