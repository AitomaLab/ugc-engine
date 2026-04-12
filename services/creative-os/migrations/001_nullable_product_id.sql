-- Migration: Make product_id nullable in product_shots table
-- This allows creating standalone shots (influencer-only, upload-only, prompt-only)
-- without requiring a product reference.
--
-- Run this in Supabase SQL Editor: Dashboard > SQL Editor > New Query

ALTER TABLE product_shots ALTER COLUMN product_id DROP NOT NULL;

-- Add a comment for documentation
COMMENT ON COLUMN product_shots.product_id IS 'Optional FK to products. Null for influencer-only or prompt-only shots.';
