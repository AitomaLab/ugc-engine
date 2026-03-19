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
