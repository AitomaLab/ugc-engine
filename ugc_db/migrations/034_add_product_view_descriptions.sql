-- 034_add_product_view_descriptions.sql
-- Per-shot visual descriptions keyed by image URL (hero + product_views carousel)

ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS product_view_descriptions JSONB DEFAULT '{}';
