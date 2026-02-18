export interface Influencer {
    id: string;
    name: string;
    description?: string;
    personality?: string;
    style?: string;          // Category (Travel, Fashion, etc.)
    speaking_style?: string;
    target_audience?: string;
    image_url?: string;
    elevenlabs_voice_id?: string;
}

export interface Script {
    id: string;
    text: string;
    category?: string;
}

export interface AppClipItem {
    id: string;
    name: string;
    description?: string;
    video_url: string;
    duration_seconds?: number;
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
