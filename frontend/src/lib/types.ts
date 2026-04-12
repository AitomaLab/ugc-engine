export interface Influencer {
    id: string;
    name: string;
    gender?: string;           // Male or Female — used in Veo 3.1 prompts
    description?: string;
    personality?: string;
    style?: string;          // Category (Travel, Fashion, etc.)
    speaking_style?: string;
    target_audience?: string;
    image_url?: string;
    elevenlabs_voice_id?: string;
    character_views?: string[];  // Character sheet view URLs (closeup, front, profile, full body)
}

export interface ScriptScene {
    scene_number: number;
    scene_title: string;
    dialogue: string;
    word_count: number;
    estimated_duration_sec: number;
    visual_cue?: string;
    on_screen_text?: string;
}

export interface ScriptJSON {
    name?: string;
    target_duration_sec?: number;
    target_platform?: string;
    methodology?: string;
    hook?: string;
    scenes?: ScriptScene[];
    _generated_hooks?: string[];
}

export interface Script {
    id: string;
    name?: string;
    text?: string;                         // Legacy ||| delimited string
    script_json?: ScriptJSON;               // New structured format
    category?: string;
    methodology?: string;
    video_length?: number;
    product_id?: string;
    influencer_id?: string;
    source?: string;                        // 'manual' | 'ai_generated' | 'csv_upload' | 'web_scraped'
    is_trending?: boolean;
    times_used?: number;
    created_at?: string;
}


export interface AppClipItem {
    id: string;
    name: string;
    description?: string;
    video_url: string;
    duration_seconds?: number;
    product_id?: string;
    first_frame_url?: string;
}

export interface Product {
    id: string;
    name: string;
    type?: string;
    product_type?: string;
    description?: string;
    category?: string;
    image_url?: string;
    website_url?: string;
    job_count?: number;
    visual_description?: any;
    product_views?: string[];
    created_at?: string;
}

export interface VideoJob {
    id: string;
    status: string;
    progress: number;
    final_video_url?: string;
    influencer_id?: string;
    script_id?: string;
    app_clip_id?: string;
    model_api?: string;
    campaign_name?: string;
    created_at?: string;
    error_message?: string;
    cost_video?: number;
    cost_voice?: number;
    cost_music?: number;
    cost_processing?: number;
    total_cost?: number;
    // Progressive scene previews
    preview_url?: string;
    preview_type?: string;  // "image" or "video"
    status_message?: string;
}

export interface Notification {
    id: string;
    type: 'job_success' | 'job_failed' | 'job_processing' | 'job_pending' | 'script_created';
    title: string;
    message: string;
    timestamp: string;
    video_url?: string | null;
}

export interface ProductShot {
    id: string;
    product_id: string;
    shot_type: string;
    status: 'image_pending' | 'image_completed' | 'animation_pending' | 'animation_completed' | 'failed';
    image_url?: string;
    video_url?: string;
    prompt?: string;
    error_message?: string;
    transition_type?: string;
    created_at: string;
}

export interface SocialPost {
    id: string;
    user_id: string;
    video_job_id: string;
    ayrshare_post_id?: string;
    status: 'scheduled' | 'posting' | 'posted' | 'failed' | 'cancelled';
    platform: string;
    caption?: string;
    hashtags?: string[];
    scheduled_at: string;
    posted_at?: string;
    error_message?: string;
    created_at: string;
    // Joined from video_jobs
    video_thumbnail_url?: string;
}

export interface SocialConnection {
    platform: string;
    username?: string;
    profilePic?: string;
}
