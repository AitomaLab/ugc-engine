-- Migration: Cache Kling 3.0 element IDs per product/influencer.
--
-- WaveSpeed's Kling 3.0 i2v/t2v API requires `element_list[].element_id`
-- (pre-registered string IDs), not inline image URLs. Each registration
-- costs $0.01, so we cache the element_id per source image so repeat
-- generations of the same product/influencer don't re-pay.
--
-- The image hash is over the public URL string (cheap, deterministic).
-- When a product/influencer image changes, the hash changes and we
-- re-register, overwriting the stored element_id. Already-generated
-- clips reference the element_id captured at generation time and remain
-- valid (WaveSpeed retains element registrations).
--
-- Run in Supabase SQL Editor: Dashboard > SQL Editor > New Query.

ALTER TABLE products
  ADD COLUMN IF NOT EXISTS kling_element_id TEXT,
  ADD COLUMN IF NOT EXISTS kling_element_image_hash TEXT;

ALTER TABLE influencers
  ADD COLUMN IF NOT EXISTS kling_element_id TEXT,
  ADD COLUMN IF NOT EXISTS kling_element_image_hash TEXT;

COMMENT ON COLUMN products.kling_element_id IS 'WaveSpeed Kling 3.0 element_id registered for this product image. Re-registered + overwritten if the source image changes.';
COMMENT ON COLUMN products.kling_element_image_hash IS 'SHA-256 of the source image URL used at registration time. Mismatch triggers re-registration.';
COMMENT ON COLUMN influencers.kling_element_id IS 'WaveSpeed Kling 3.0 element_id registered for this influencer image.';
COMMENT ON COLUMN influencers.kling_element_image_hash IS 'SHA-256 of the source image URL used at registration time.';

-- Generic fallback cache for ad-hoc element images (e.g. @mention assets
-- that aren't a product/influencer row). Keyed by image-URL hash so the
-- same image used across projects only registers once.
CREATE TABLE IF NOT EXISTS kling_element_cache (
  image_hash TEXT PRIMARY KEY,
  element_id TEXT NOT NULL,
  element_name TEXT,
  source_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kling_element_cache IS 'Per-image-hash cache of WaveSpeed Kling element_id for ad-hoc element references that are not products or influencers.';
