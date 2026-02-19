-- Ensure visual_description column exists (renaming from visual_analysis if present)

DO $$
BEGIN
    -- If visual_analysis exists, rename it
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'products' AND column_name = 'visual_analysis') THEN
        ALTER TABLE products RENAME COLUMN visual_analysis TO visual_description;
    -- If neither exists, add visual_description
    ELSIF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'products' AND column_name = 'visual_description') THEN
        ALTER TABLE products ADD COLUMN visual_description JSONB DEFAULT '{}'::jsonb;
    END IF;
END $$;

COMMENT ON COLUMN products.visual_description IS 'Stores OpenAI Vision analysis (YAML-based)';
