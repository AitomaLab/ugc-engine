"""Pydantic request / response models for the Analytics module."""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ── Domain primitives ───────────────────────────────────────────────────────

Platform = Literal["tiktok", "instagram", "youtube", "facebook"]
Source = Literal["internal", "external"]
ScrapeKind = Literal["post", "account", "batch"]
JobStatus = Literal["pending", "running", "completed", "failed"]
BreakdownStatus = Literal["pending", "running", "completed", "failed"]


# ── Posts ───────────────────────────────────────────────────────────────────

class AnalyticsPostOut(BaseModel):
    id: str
    user_id: str
    source: Source
    platform: str
    username: str
    post_url: str
    external_post_id: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    media_type: Optional[str] = None
    media_urls: Optional[List[Any]] = None
    storage_video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    posted_at: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    saves: Optional[int] = None
    # Funnel metrics — only populated when Ayrshare returns them for the
    # platform's tier (Instagram Business / Facebook Pages / YouTube).
    impressions: Optional[int] = None
    reach: Optional[int] = None
    clicks: Optional[int] = None
    ctr: Optional[float] = Field(
        default=None,
        description="Click-through rate, 0.0–1.0. Multiply by 100 for display.",
    )
    total_engagement: int = 0
    social_post_id: Optional[str] = None
    video_job_id: Optional[str] = None
    breakdown_status: Optional[str] = None
    scraped_at: Optional[str] = None


# ── Scrape ──────────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    input: str = Field(..., description="Post URL, profile URL, or @handle")
    kind: Optional[ScrapeKind] = None
    platform: Optional[Platform] = Field(
        default=None,
        description="Required only when the input is a bare @handle so we know which platform to scrape.",
    )


class TrackedAccountOut(BaseModel):
    id: str
    platform: str
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    followers: Optional[int] = None
    total_posts: Optional[int] = None
    is_active: bool = True
    last_scraped_at: Optional[str] = None
    # v2 — scrape config + health (migration 035)
    scrape_frequency: Optional[str] = None
    top_n_retention: Optional[int] = None
    health_score: Optional[int] = None
    follower_count: Optional[int] = None
    linked_via_connections: bool = Field(
        default=False,
        description="True when synced from OAuth / Ayrshare (Connections).",
    )


class TrackedAccountAggregateOut(TrackedAccountOut):
    """Account row enriched with rolling-window metrics used by the Accounts
    dashboard cards. All metrics are computed against `analytics_posts` rows
    scraped within the same period the page uses for the KPI strip."""
    total_views: int = 0
    total_engagement: int = 0
    avg_engagement_rate: float = 0.0
    posts_in_period: int = 0
    health_label: str = "unknown"  # 'good' | 'warning' | 'at_risk' | 'unknown'


class AccountAggregatesResponse(BaseModel):
    accounts: List[TrackedAccountAggregateOut]
    total_accounts: int = 0
    total_scraped_posts: int = 0
    avg_health_score: Optional[float] = None


class TrendPoint(BaseModel):
    date: str               # ISO date (YYYY-MM-DD)
    engagement: int = 0
    views: int = 0
    posts: int = 0


class AccountTrendResponse(BaseModel):
    account_id: str
    points: List[TrendPoint] = []


class AccountTopPostsResponse(BaseModel):
    account_id: str
    posts: List["AnalyticsPostOut"] = []
    studio_avg_engagement: Optional[float] = None
    external_avg_engagement: Optional[float] = None
    studio_vs_external_pct: Optional[float] = None


class ScrapeResponse(BaseModel):
    job_id: str
    status: JobStatus
    posts: List[AnalyticsPostOut] = []
    tracked_account: Optional[TrackedAccountOut] = None
    error_message: Optional[str] = None


# ── Posts list / detail ─────────────────────────────────────────────────────

class PostsListResponse(BaseModel):
    items: List[AnalyticsPostOut]
    next_cursor: Optional[str] = None


class PostRefreshRequest(BaseModel):
    post_id: str


class PostDurationPatch(BaseModel):
    """Body of POST /posts/{id}/duration — set by the modal once it has the
    real duration from the loaded `<video>` element."""
    duration_seconds: float = Field(..., gt=0, le=60 * 60 * 6)  # cap at 6h


# ── Breakdowns ──────────────────────────────────────────────────────────────

class AnalyzeVideoRequest(BaseModel):
    analytics_post_id: Optional[str] = None
    video_job_id: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "AnalyzeVideoRequest":
        provided = [v for v in (self.analytics_post_id, self.video_job_id) if v]
        if len(provided) != 1:
            raise ValueError(
                "Provide exactly one of analytics_post_id or video_job_id"
            )
        return self


class HookSection(BaseModel):
    timestamp: Optional[str] = None
    on_screen_text: Optional[str] = None
    visual: Optional[str] = None
    why_it_works: Optional[str] = None


class SceneSection(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    description: Optional[str] = None
    on_screen_text: Optional[str] = None


class AudioTranscriptItem(BaseModel):
    ts: Optional[str] = None
    text: Optional[str] = None


class AudioSection(BaseModel):
    has_audio: bool = False
    transcript: Optional[List[AudioTranscriptItem]] = None
    notes: Optional[str] = None


class KeyMoment(BaseModel):
    ts: Optional[str] = None
    description: Optional[str] = None


class BreakdownOut(BaseModel):
    id: str
    status: BreakdownStatus
    model: Optional[str] = None
    provider: Optional[str] = None
    summary: Optional[str] = None
    hook: Optional[HookSection] = None
    scenes: Optional[List[SceneSection]] = None
    audio: Optional[AudioSection] = None
    visual_details: Optional[List[str]] = None
    key_moments: Optional[List[KeyMoment]] = None
    takeaways: Optional[List[str]] = None
    raw_markdown: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class AnalyzeVideoResponse(BaseModel):
    breakdown_id: str
    status: BreakdownStatus


class PostDetailResponse(BaseModel):
    post: AnalyticsPostOut
    breakdown: Optional[BreakdownOut] = None


# ── Tracked accounts ────────────────────────────────────────────────────────

ScrapeFrequency = Literal["manual", "hourly", "6h", "12h", "daily", "weekly"]


class TrackedAccountCreate(BaseModel):
    platform: Platform
    username: str
    # v2 — optional per-account scrape config. Defaults inherit from the
    # tenant's analytics_settings on the server side when omitted.
    scrape_frequency: Optional[ScrapeFrequency] = None
    top_n_retention: Optional[int] = Field(default=None, ge=1, le=200)


class TrackedAccountConfigPatch(BaseModel):
    """Body of PUT /tracked-accounts/{id} — only the fields the user explicitly
    sends are updated. All optional so callers can update one knob at a time."""
    scrape_frequency: Optional[ScrapeFrequency] = None
    top_n_retention: Optional[int] = Field(default=None, ge=1, le=200)
    is_active: Optional[bool] = None


class TrackedAccountWithJob(BaseModel):
    """Response shape for POST /tracked-accounts and POST .../{id}/refresh.
    Includes the (just-)scraped posts so the frontend grid + KPIs can update
    without a separate fetch."""
    account: TrackedAccountOut
    job_id: Optional[str] = None
    status: JobStatus = "completed"
    posts: List[AnalyticsPostOut] = []
    error_message: Optional[str] = None


# ── Video prep (modal lazy-mirror) ──────────────────────────────────────────

VideoPrepStatus = Literal[
    "ready",        # storage_video_url is populated, frontend can play it
    "queued",       # task just started, no real work done yet
    "scraping",     # doing a per-post BrightData scrape to get the video URL
    "downloading",  # streaming the video from CDN into Supabase Storage
    "failed",       # terminal — error_message is set
]


class VideoPrepResponse(BaseModel):
    status: VideoPrepStatus
    progress_pct: int = 0
    storage_video_url: Optional[str] = None
    error_message: Optional[str] = None


# ── Stats ───────────────────────────────────────────────────────────────────

class DistributionEntry(BaseModel):
    """One slice of a categorical breakdown (platform / media type)."""
    key: str
    value: int = 0
    posts: int = 0


class StatsResponse(BaseModel):
    total_views: int = 0
    total_engagement: int = 0
    avg_engagement_rate: float = 0.0
    posts_tracked: int = 0
    posts_total: int = Field(
        default=0,
        description="All scraped posts for the account in library (ignores period window).",
    )
    # Period-over-period change in raw values (delta vs. the previous window
    # of the same length). 0 when there's no prior window to compare to.
    views_delta_pct: float = 0.0
    engagement_delta_pct: float = 0.0
    posts_delta_pct: float = 0.0
    # Sparkline payload — daily totals across the active window. Always sized
    # to ``max(period_days, 1)`` and zero-filled so the FE can render without
    # extra normalization.
    daily_views: List[int] = Field(default_factory=list)
    daily_engagement: List[int] = Field(default_factory=list)
    daily_posts: List[int] = Field(default_factory=list)
    # Distribution payloads — sorted descending by `value`.
    platform_distribution: List[DistributionEntry] = Field(default_factory=list)
    content_type_distribution: List[DistributionEntry] = Field(default_factory=list)


class CumulativePoint(BaseModel):
    date: str  # ISO YYYY-MM-DD
    # Architecture-reference contract names…
    cumulative_views: int = 0
    cumulative_engagement: int = 0
    cumulative_posts: int = 0
    # …with shorter aliases the existing FE chart already reads.
    views: int = 0
    engagement: int = 0
    posts: int = 0


class CumulativeStatsResponse(BaseModel):
    points: List[CumulativePoint] = Field(default_factory=list)
    total_views: int = 0
    total_engagement: int = 0
    total_posts: int = 0


class SyncStudioConnectionsResponse(BaseModel):
    linked_profiles: int = Field(ge=0, description="Distinct (platform,@handle) pairs from Connections.")
    tracked_rows_linked: int = Field(
        ge=0,
        description="analytics_tracked_accounts rows upserted with linked_via_connections=true.",
    )
    scrape_jobs_enqueued: int = Field(
        ge=0,
        description="Background BrightData refreshes queued for handles without last_scraped_at.",
    )
    publications_synced: int = Field(
        ge=0,
        description="social_posts mirrored into analytics_posts as source=internal.",
    )


class RefreshAllResponse(BaseModel):
    """Summary for POST /refresh-all — studio sync + Ayrshare metrics + AI queue."""
    status: str = Field(default="queued", description="queued when accepted for background processing")
    publications_synced: int = Field(default=0, ge=0)
    metrics_refreshed: int = Field(default=0, description="Studio posts updated from Ayrshare analytics.")
    breakdowns_queued: int = Field(default=0, description="AI breakdown jobs started for Studio videos.")
    linked_profiles: int = Field(default=0, ge=0)
    tracked_rows_linked: int = Field(default=0, ge=0)
    scrape_jobs_enqueued: int = Field(default=0, ge=0)


class RefreshStatusResponse(BaseModel):
    status: str = Field(default="idle", description="idle | queued | running | completed | failed")
    last_metrics_refreshed_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: Optional[str] = None


class AccountStrategyReportResponse(BaseModel):
    """AI "Do More / Do Less" strategy report for one tracked account."""
    account_id: str
    report: Optional[str] = Field(
        default=None, description="Markdown report, or null when not yet generated.",
    )
    generated_at: Optional[str] = Field(
        default=None, description="ISO timestamp of the last generation.",
    )


class EnsureThumbnailsRequest(BaseModel):
    post_ids: List[str] = Field(default_factory=list)


class EnsureThumbnailsResponse(BaseModel):
    thumbnails: dict[str, str] = Field(default_factory=dict)
    pending: int = Field(
        default=0,
        ge=0,
        description="Posts queued for slow background mirroring.",
    )


# ── Settings (analytics_settings, per user) ────────────────────────────────

class AnalyticsSettingsOut(BaseModel):
    default_scrape_frequency: ScrapeFrequency = "daily"
    default_top_n: int = 50
    monthly_budget_limit_usd: float = 10.00
    alert_threshold_usd: float = 0.05
    # Surface BrightData configuration status read-only — the API token itself
    # is environment-managed (see scraper_service._api_key) and never leaves
    # the server, but the modal needs to show "Configured / Not configured"
    # so the user knows whether scrapes will actually work.
    brightdata_configured: bool = False


class AnalyticsSettingsPatch(BaseModel):
    default_scrape_frequency: Optional[ScrapeFrequency] = None
    default_top_n: Optional[int] = Field(default=None, ge=1, le=200)
    monthly_budget_limit_usd: Optional[float] = Field(default=None, ge=0)
    alert_threshold_usd: Optional[float] = Field(default=None, ge=0)


# Forward-ref resolution (AccountTopPostsResponse references AnalyticsPostOut).
AccountTopPostsResponse.model_rebuild()
