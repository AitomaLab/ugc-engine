-- Create products table
CREATE TABLE IF NOT EXISTS products (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  description TEXT,
  category TEXT,
  image_url TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

-- Create Policies (allow all for now to simplify dev, restricted logically in backend)
CREATE POLICY "Allow public read access" ON products FOR SELECT USING (true);
CREATE POLICY "Allow authenticated insert" ON products FOR INSERT WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated update" ON products FOR UPDATE USING (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated delete" ON products FOR DELETE USING (auth.role() = 'authenticated');

-- Create Index
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- Update video_jobs table
ALTER TABLE video_jobs
ADD COLUMN IF NOT EXISTS product_type TEXT DEFAULT 'digital' CHECK (product_type IN ('digital', 'physical')),
ADD COLUMN IF NOT EXISTS product_id UUID REFERENCES products(id),
ADD COLUMN IF NOT EXISTS cost_image NUMERIC(10, 4) DEFAULT 0.00;

-- Create Indexes for video_jobs
CREATE INDEX IF NOT EXISTS idx_video_jobs_product_type ON video_jobs(product_type);
CREATE INDEX IF NOT EXISTS idx_video_jobs_product_id ON video_jobs(product_id);
