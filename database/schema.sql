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
