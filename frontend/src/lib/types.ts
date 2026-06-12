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
    product_view_descriptions?: Record<string, any>;
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
    image_url?: string | null;
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
    /** Set for video schedules; omitted / null when `media_kind` is image (migration 046). */
    video_job_id?: string | null;
    product_shot_id?: string | null;
    media_kind?: 'video' | 'image';
    ayrshare_post_id?: string;
    status: 'scheduled' | 'posting' | 'posted' | 'failed' | 'cancelled';
    platform: string;
    caption?: string;
    hashtags?: string[];
    scheduled_at: string;
    posted_at?: string;
    error_message?: string;
    created_at: string;
    /** Hydrated by GET /api/schedule — video poster or image URL */
    thumbnail_url?: string;
    // Joined from video_jobs (legacy name)
    video_thumbnail_url?: string;
}

export interface SocialConnection {
    platform: string;
    username?: string;
    profilePic?: string;
}

// ── Analytics module ────────────────────────────────────────────────────────
export type AnalyticsPlatform = 'tiktok' | 'instagram' | 'youtube' | 'facebook';
export type AnalyticsSource = 'internal' | 'external';

export interface AnalyticsPost {
    id: string;
    user_id?: string;
    source: AnalyticsSource;
    platform: AnalyticsPlatform | string;
    username: string;
    post_url: string;
    external_post_id?: string;
    caption?: string;
    hashtags?: string[];
    media_type?: 'video' | 'image' | 'carousel' | string;
    media_urls?: Array<{ url?: string; type?: string } | string>;
    storage_video_url?: string;
    thumbnail_url?: string;
    duration_seconds?: number;
    posted_at?: string;
    views?: number;
    likes?: number;
    comments?: number;
    shares?: number;
    saves?: number;
    impressions?: number;
    reach?: number;
    clicks?: number;
    ctr?: number;
    total_engagement: number;
    social_post_id?: string;
    video_job_id?: string;
    breakdown_status?: 'none' | 'pending' | 'running' | 'completed' | 'failed';
    scraped_at?: string;
}

export interface AnalyticsBreakdown {
    id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    model?: string;
    provider?: string;
    summary?: string;
    hook?: {
        timestamp?: string;
        on_screen_text?: string;
        visual?: string;
        why_it_works?: string;
    };
    scenes?: Array<{
        start?: string;
        end?: string;
        description?: string;
        on_screen_text?: string;
    }>;
    audio?: {
        has_audio: boolean;
        transcript?: Array<{ ts?: string; text?: string }>;
        notes?: string;
    };
    visual_details?: string[];
    key_moments?: Array<{ ts?: string; description?: string }>;
    takeaways?: string[];
    raw_markdown?: string;
    error_message?: string;
    created_at?: string;
    completed_at?: string;
}

export interface TrackedAccount {
    id: string;
    platform: AnalyticsPlatform | string;
    username: string;
    display_name?: string;
    avatar_url?: string;
    followers?: number;
    total_posts?: number;
    is_active: boolean;
    last_scraped_at?: string;
    // v2 — scrape config + health (migration 044)
    scrape_frequency?: ScrapeFrequency;
    top_n_retention?: number;
    health_score?: number;
    follower_count?: number;
    /** True when synced from OAuth (Connections / Ayrshare). Migration 045. */
    linked_via_connections?: boolean;
}

export type ScrapeFrequency = 'manual' | 'hourly' | '6h' | '12h' | 'daily' | 'weekly';
export type AccountHealth = 'good' | 'warning' | 'at_risk' | 'unknown';

export interface TrackedAccountAggregate extends TrackedAccount {
    total_views: number;
    total_engagement: number;
    avg_engagement_rate: number;
    posts_in_period: number;
    health_label: AccountHealth;
}

export interface TrendPoint {
    date: string;
    engagement: number;
    views: number;
    posts: number;
}

export interface AnalyticsSettings {
    default_scrape_frequency: ScrapeFrequency;
    default_top_n: number;
    monthly_budget_limit_usd: number;
    alert_threshold_usd: number;
    brightdata_configured: boolean;
}
