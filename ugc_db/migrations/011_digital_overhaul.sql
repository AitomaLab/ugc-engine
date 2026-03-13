-- Migration 011: Digital Product & App Clip Overhaul
-- Run this in the Supabase SQL Editor.

-- 1. Add type column to products (physical / digital)
ALTER TABLE products
ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'physical';

-- 2. Add website_url to products for dual-source AI analysis
ALTER TABLE products
ADD COLUMN IF NOT EXISTS website_url TEXT;

-- 2. Link app_clips to a specific digital product
ALTER TABLE app_clips
ADD COLUMN IF NOT EXISTS product_id UUID REFERENCES products(id) ON DELETE SET NULL;

-- 3. Store the extracted first frame for Nano Banana Pro visual consistency
ALTER TABLE app_clips
ADD COLUMN IF NOT EXISTS first_frame_url TEXT;

-- 4. Index for fast lookup of clips by product
CREATE INDEX IF NOT EXISTS idx_app_clips_product_id ON app_clips(product_id);
