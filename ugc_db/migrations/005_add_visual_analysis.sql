-- Add visual_analysis column to products table
-- This stores the AI-generated visual description of the product to avoid re-analysis costs.

ALTER TABLE products
ADD COLUMN IF NOT EXISTS visual_analysis JSONB DEFAULT '{}'::jsonb;

-- Comment on column
COMMENT ON COLUMN products.visual_analysis IS 'Stores OpenAI Vision analysis: brand, color_scheme, font_style, description';
