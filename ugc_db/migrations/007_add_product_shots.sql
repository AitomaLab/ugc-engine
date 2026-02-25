-- 007_add_product_shots.sql
-- Cinematic Product Shots: new table for storing generated stills and animated videos

CREATE TABLE public.product_shots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    shot_type TEXT NOT NULL, -- e.g., 'hero', 'macro_detail', 'pedestal'
    status TEXT NOT NULL DEFAULT 'image_pending', -- image_pending, image_completed, animation_pending, animation_completed, failed
    image_url TEXT, -- URL of the still image from Nano Banana Pro
    video_url TEXT, -- URL of the animated video from Veo 3.1
    prompt TEXT, -- The SEALCaM prompt used for image generation
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE public.product_shots ENABLE ROW LEVEL SECURITY;

-- Create Policies (match existing 4-policy pattern from 004_add_products.sql)
CREATE POLICY "Allow public read access" ON public.product_shots FOR SELECT USING (true);
CREATE POLICY "Allow authenticated insert" ON public.product_shots FOR INSERT WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated update" ON public.product_shots FOR UPDATE USING (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated delete" ON public.product_shots FOR DELETE USING (auth.role() = 'authenticated');

-- Create Indexes
CREATE INDEX idx_product_shots_product_id ON public.product_shots(product_id);
CREATE INDEX idx_product_shots_status ON public.product_shots(status);

-- Add cinematic_shot_ids to video_jobs for Create Page integration
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS cinematic_shot_ids UUID[] DEFAULT '{}';
