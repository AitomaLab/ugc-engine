-- Migration 009: Cinematic Shots Engine v2
-- 1. Rename shot_type 'pedestal' → 'elevated' in existing product_shots
-- 2. Add columns for Workflow B (transition shots)

-- Step 1: Rename existing pedestal shots
UPDATE public.product_shots
SET shot_type = 'elevated', updated_at = NOW()
WHERE shot_type = 'pedestal';

-- Step 2: Add transition shot columns for Workflow B
ALTER TABLE public.product_shots
ADD COLUMN IF NOT EXISTS transition_type TEXT;

ALTER TABLE public.product_shots
ADD COLUMN IF NOT EXISTS preceding_video_url TEXT;

ALTER TABLE public.product_shots
ADD COLUMN IF NOT EXISTS analysis_json JSONB;

-- Step 3: Add auto_transition_type to video_jobs for Workflow B
ALTER TABLE public.video_jobs
ADD COLUMN IF NOT EXISTS auto_transition_type TEXT;
