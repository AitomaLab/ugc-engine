-- UGC Engine SaaS Database Schema

-- Users Table (Supabase Auth will handle most of this, but we need our own profile table)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    full_name TEXT,
    company_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Influencers Table
CREATE TABLE IF NOT EXISTS influencers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    age TEXT,
    gender TEXT,
    accent TEXT,
    tone TEXT,
    visual_description TEXT,
    personality TEXT,
    energy_level TEXT,
    reference_image_url TEXT,
    elevenlabs_voice_id TEXT,
    category TEXT, -- Travel, Shop, Fitness, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- App Clips Table
CREATE TABLE IF NOT EXISTS app_clips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    video_url TEXT NOT NULL,
    duration FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Video Jobs Table
CREATE TABLE IF NOT EXISTS video_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    influencer_id UUID REFERENCES influencers(id),
    app_clip_id UUID REFERENCES app_clips(id),
    project_name TEXT,
    status TEXT DEFAULT 'pending', -- pending, generating, assembling, success, failed
    progress_percent INT DEFAULT 0,
    final_video_url TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Products Table
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT,
    description TEXT,
    image_url TEXT,
    website_url TEXT,
    visual_description JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Scripts Table (v2 -- structured JSON format)
CREATE TABLE IF NOT EXISTS scripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT,
    text TEXT,                          -- Legacy |||delimited string (kept for backward compat)
    script_json JSONB,                  -- New structured format (see blueprint Section 3.3)
    category TEXT DEFAULT 'General',
    methodology TEXT NOT NULL DEFAULT 'Hook/Benefit/CTA',
    video_length INTEGER NOT NULL DEFAULT 15,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    influencer_id UUID REFERENCES influencers(id) ON DELETE SET NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    is_trending BOOLEAN NOT NULL DEFAULT false,
    times_used INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
