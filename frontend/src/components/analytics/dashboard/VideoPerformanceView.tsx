'use client';

import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import VideoThumbnail from '@/components/ui/VideoThumbnail';
import {
    analyticsFetch,
    formatCount,
    periodToApiParam,
    pickBestPostPreview,
    timeAgo,
    type AnalyticsPost,
    type Period,
    type PostsListResponse,
} from '../analytics-types';

interface Props {
    period: Period;
    refreshKey?: number;
    /**
     * Open the post detail modal in the parent. When the user clicks a
     * platform chip the parent receives the underlying `analytics_posts.id`
     * so the existing `?post=<id>` deep-link path can drive the modal.
     */
    onOpenPost?: (postId: string) => void;
}

/**
 * Performance grouped by **uploaded video** (Studio-published content only).
 *
 * The same video can be scheduled to multiple platforms — the Schedule modal
 * inserts one `social_posts` (and downstream one `analytics_posts`) row per
 * (asset, platform) tuple. Without this view, the user has to mentally
 * stitch together how each upload performed across its destinations.
 *
 * We fetch the raw post list (`source=internal`) once, then group by
 * `video_job_id` (or the social post id as a fallback for legacy rows that
 * didn't get stamped) and aggregate views / engagement / per-platform metrics
 * client-side. No new backend endpoint is required — this is a pure
 * presentation reslice of `/api/analytics/posts`.
 */
export default function VideoPerformanceView({ period, refreshKey = 0, onOpenPost }: Props) {
    const { t } = useTranslation();
    const [posts, setPosts] = useState<AnalyticsPost[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            setLoading(true);
            setError(null);
            const params = new URLSearchParams({
                period: periodToApiParam(period),
                platform: 'all',
                source: 'internal',
                sort: 'recent',
                limit: '100',
            });
            try {
                const data = await analyticsFetch<PostsListResponse>(
                    `/api/analytics/posts?${params.toString()}`,
                    { skipProjectScope: true },
                );
                if (cancelled) return;
                setPosts(data.items || []);
            } catch (e) {
                if (cancelled) return;
                setError(e instanceof Error ? e.message : 'Failed to load video performance');
                setPosts([]);
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [period, refreshKey]);

    const groups = useMemo(() => groupByUploadedVideo(posts), [posts]);

    if (loading && posts.length === 0) {
        return (
            <Panel>
                <PanelHeader />
                <div style={{ padding: '32px 0', textAlign: 'center', color: '#94A3B8', fontSize: 13 }}>
                    {t('analytics.dashboard.videos.loading')}
                </div>
            </Panel>
        );
    }

    if (error) {
        return (
            <Panel>
                <PanelHeader />
                <div style={{ padding: '20px 0', color: '#DC2626', fontSize: 13 }}>{error}</div>
            </Panel>
        );
    }

    if (groups.length === 0) {
        return (
            <Panel>
                <PanelHeader />
                <div
                    style={{
                        padding: '36px 24px',
                        textAlign: 'center',
                        color: '#475569',
                        fontSize: 13,
                        background: '#F8FAFC',
                        border: '1px dashed #E2E8F0',
                        borderRadius: 14,
                    }}
                >
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#0F172A', marginBottom: 6 }}>
                        {t('analytics.dashboard.videos.empty.title')}
                    </div>
                    <div style={{ fontSize: 12, lineHeight: 1.55, color: '#64748B', maxWidth: 420, margin: '0 auto' }}>
                        {t('analytics.dashboard.videos.empty.body')}
                    </div>
                </div>
            </Panel>
        );
    }

    const subtitle = t('analytics.dashboard.videos.subtitle')
        .replace('{count}', String(groups.length));

    return (
        <Panel>
            <PanelHeader subtitle={subtitle} />

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {groups.map((g) => (
                    <VideoRow key={g.key} group={g} onOpenPost={onOpenPost} />
                ))}
            </div>
        </Panel>
    );
}

/* ── Grouping ─────────────────────────────────────────────────────────── */

interface PlatformPost {
    post: AnalyticsPost;
    views: number;
    engagement: number;
}

interface VideoGroup {
    key: string;
    title: string;
    caption?: string;
    previewUrl?: string;
    videoUrl?: string;
    /** First posted timestamp across this video's platform copies. */
    postedAt?: string;
    /** Aggregated across every platform this video was posted to. */
    totals: { views: number; likes: number; comments: number; shares: number; saves: number; engagement: number };
    /** One entry per platform (sorted by engagement desc). */
    platforms: Array<{ platform: string; post: AnalyticsPost; views: number; engagement: number }>;
    /** True when at least one platform copy has a completed AI breakdown. */
    hasBreakdown: boolean;
}

function groupByUploadedVideo(posts: AnalyticsPost[]): VideoGroup[] {
    const buckets = new Map<string, PlatformPost[]>();

    for (const p of posts) {
        // Studio-only safety check; backend filter already excludes externals
        // but protects future callers that pass mixed lists.
        if ((p as any).source && (p as any).source !== 'internal') continue;

        // Group key: video_job_id (canonical), then fall back to
        // social_post_id (covers older rows pre-035 backfill), then to the
        // analytics_posts.id itself so single-platform schedules still
        // appear as a one-row group instead of being silently dropped.
        const key = String(
            p.video_job_id
            || (p as { social_post_id?: string }).social_post_id
            || p.id,
        );
        const list = buckets.get(key) || [];
        list.push({
            post: p,
            views: Number(p.views || 0),
            engagement: Number(p.total_engagement || 0),
        });
        buckets.set(key, list);
    }

    const groups: VideoGroup[] = [];

    for (const [key, list] of buckets.entries()) {
        // Sort platforms by engagement so the most-successful destination
        // surfaces first inside the row.
        list.sort((a, b) => b.engagement - a.engagement);

        const top = list[0]?.post;
        if (!top) continue;

        const totals = list.reduce(
            (acc, item) => {
                acc.views += Number(item.post.views || 0);
                acc.likes += Number(item.post.likes || 0);
                acc.comments += Number(item.post.comments || 0);
                acc.shares += Number(item.post.shares || 0);
                acc.saves += Number(item.post.saves || 0);
                acc.engagement += Number(item.post.total_engagement || 0);
                return acc;
            },
            { views: 0, likes: 0, comments: 0, shares: 0, saves: 0, engagement: 0 },
        );

        const earliestPosted = list
            .map((i) => i.post.posted_at)
            .filter((v): v is string => !!v)
            .sort()[0];

        const titleSource = top.caption?.trim() || '';
        const title = titleSource
            ? truncate(titleSource, 80)
            : `Video · ${shortId(key)}`;

        const preview = pickBestPostPreview(list.map((i) => i.post));

        const platformRows = collapsePostsByPlatform(list);

        groups.push({
            key,
            title,
            caption: titleSource || undefined,
            previewUrl: preview.previewUrl,
            videoUrl: preview.videoUrl,
            postedAt: earliestPosted,
            totals,
            platforms: platformRows,
            hasBreakdown: list.some((i) => i.post.breakdown_status === 'completed'),
        });
    }

    // Order videos by total engagement desc — winners first.
    groups.sort((a, b) => b.totals.engagement - a.totals.engagement);
    return groups;
}

/** Collapse duplicate platform rows for the same upload (e.g. two Instagram
 *  analytics_posts for one video_job) into a single chip with summed metrics. */
function collapsePostsByPlatform(
    list: PlatformPost[],
): VideoGroup['platforms'] {
    const byPlatform = new Map<string, PlatformPost[]>();

    for (const item of list) {
        const platform = (item.post.platform || 'unknown').toLowerCase();
        const bucket = byPlatform.get(platform) || [];
        bucket.push(item);
        byPlatform.set(platform, bucket);
    }

    return Array.from(byPlatform.entries())
        .map(([platform, items]) => {
            items.sort((a, b) => b.engagement - a.engagement);
            return {
                platform,
                // Open the best-performing copy when the chip is clicked.
                post: items[0].post,
                views: items.reduce((sum, i) => sum + i.views, 0),
                engagement: items.reduce((sum, i) => sum + i.engagement, 0),
            };
        })
        .sort((a, b) => b.engagement - a.engagement);
}

/* ── Row layout ───────────────────────────────────────────────────────── */

function VideoRow({
    group,
    onOpenPost,
}: {
    group: VideoGroup;
    onOpenPost?: (postId: string) => void;
}) {
    const { t } = useTranslation();
    const topPost = group.platforms[0]?.post;

    return (
        <div
            style={{
                display: 'flex',
                gap: 16,
                alignItems: 'stretch',
                padding: 16,
                background: '#FFFFFF',
                border: '1px solid #E2E8F0',
                borderRadius: 14,
                boxShadow: '0 1px 2px rgba(15,23,42,0.03)',
                transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
            }}
            onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#CBD5E1';
                e.currentTarget.style.boxShadow = '0 2px 6px rgba(15,23,42,0.06)';
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#E2E8F0';
                e.currentTarget.style.boxShadow = '0 1px 2px rgba(15,23,42,0.03)';
            }}
        >
            <Thumbnail previewUrl={group.previewUrl} videoUrl={group.videoUrl} alt={group.caption || group.title} />

            <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                    <div style={{ minWidth: 0 }}>
                        <div
                            style={{
                                fontSize: 14,
                                fontWeight: 700,
                                color: '#0F172A',
                                lineHeight: 1.35,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                            }}
                            title={group.caption || group.title}
                        >
                            {group.title}
                        </div>
                        <div style={{ marginTop: 4, fontSize: 11, color: '#94A3B8', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                            <span>{group.platforms.length} {t('analytics.dashboard.videos.platforms')}</span>
                            {group.postedAt && <span>· {timeAgo(group.postedAt)}</span>}
                            {group.hasBreakdown && (
                                <span
                                    style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: 4,
                                        color: '#337AFF',
                                        fontWeight: 700,
                                    }}
                                >
                                    <SparklesIcon /> {t('analytics.dashboard.videos.aiAnalyzed')}
                                </span>
                            )}
                        </div>
                    </div>

                    {topPost && onOpenPost && (
                        <button
                            type="button"
                            onClick={() => onOpenPost(topPost.id)}
                            style={{
                                padding: '7px 14px',
                                borderRadius: 8,
                                border: '1px solid #E2E8F0',
                                background: '#FFFFFF',
                                color: '#0F172A',
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: 'pointer',
                                whiteSpace: 'nowrap',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 6,
                                transition: 'background 0.15s ease, border-color 0.15s ease',
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.background = '#EBF1FF';
                                e.currentTarget.style.borderColor = '#337AFF';
                                e.currentTarget.style.color = '#0F172A';
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.background = '#FFFFFF';
                                e.currentTarget.style.borderColor = '#E2E8F0';
                                e.currentTarget.style.color = '#0F172A';
                            }}
                        >
                            {t('analytics.dashboard.videos.viewDetail')} <ArrowIcon />
                        </button>
                    )}
                </div>

                <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
                    <Metric label={t('analytics.dashboard.videos.metrics.views')} value={group.totals.views} accent />
                    <Metric label={t('analytics.dashboard.videos.metrics.engagement')} value={group.totals.engagement} />
                    <Metric label={t('analytics.dashboard.videos.metrics.likes')} value={group.totals.likes} muted />
                    <Metric label={t('analytics.dashboard.videos.metrics.comments')} value={group.totals.comments} muted />
                    {group.totals.shares > 0 && (
                        <Metric label={t('analytics.dashboard.videos.metrics.shares')} value={group.totals.shares} muted />
                    )}
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {group.platforms.map((p) => (
                        <PlatformChip
                            key={`${p.platform}-${p.post.id}`}
                            platform={p.platform}
                            views={p.views}
                            engagement={p.engagement}
                            onClick={onOpenPost ? () => onOpenPost(p.post.id) : undefined}
                        />
                    ))}
                </div>
            </div>
        </div>
    );
}

/* ── Sub-components ───────────────────────────────────────────────────── */

function Panel({ children }: { children: React.ReactNode }) {
    return (
        <section
            style={{
                background: '#FFFFFF',
                border: '1px solid #E2E8F0',
                borderRadius: 18,
                padding: 22,
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
                boxShadow: '0 1px 2px rgba(15,23,42,0.03)',
            }}
        >
            {children}
        </section>
    );
}

function PanelHeader({ subtitle }: { subtitle?: string }) {
    const { t } = useTranslation();
    return (
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: 0.6 }}>
                    {t('analytics.dashboard.videos.label')}
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#0F172A', marginTop: 4 }}>
                    {t('analytics.dashboard.videos.title')}
                </div>
                {subtitle && (
                    <div style={{ fontSize: 12, color: '#64748B', marginTop: 4 }}>{subtitle}</div>
                )}
            </div>
        </div>
    );
}

function Thumbnail({
    previewUrl,
    videoUrl,
    alt,
}: {
    previewUrl?: string;
    videoUrl?: string;
    alt?: string;
}) {
    return (
        <div
            style={{
                position: 'relative',
                width: 96,
                height: 128,
                borderRadius: 12,
                overflow: 'hidden',
                background: '#F1F5F9',
                border: '1px solid #E2E8F0',
                flexShrink: 0,
            }}
        >
            <VideoThumbnail previewUrl={previewUrl} videoUrl={videoUrl} alt={alt || ''} />
        </div>
    );
}

function Metric({
    label,
    value,
    accent,
    muted,
}: {
    label: string;
    value: number;
    accent?: boolean;
    muted?: boolean;
}) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 64 }}>
            <span style={{ fontSize: 10, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 700 }}>
                {label}
            </span>
            <span
                style={{
                    fontSize: muted ? 14 : 18,
                    fontWeight: 700,
                    color: accent ? '#337AFF' : muted ? '#475569' : '#0F172A',
                    fontVariantNumeric: 'tabular-nums',
                    lineHeight: 1.1,
                }}
            >
                {formatCount(value)}
            </span>
        </div>
    );
}

const PLATFORM_COLORS: Record<string, string> = {
    instagram: '#E1306C',
    tiktok: '#0EA5E9',
    youtube: '#EF4444',
    facebook: '#2563EB',
};

function PlatformChip({
    platform,
    views,
    engagement,
    onClick,
}: {
    platform: string;
    views: number;
    engagement: number;
    onClick?: () => void;
}) {
    const color = PLATFORM_COLORS[platform] || '#64748B';
    const isClickable = !!onClick;
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={!isClickable}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 10px',
                borderRadius: 8,
                background: '#F8FAFC',
                border: '1px solid #E2E8F0',
                color: '#0F172A',
                fontSize: 11,
                fontWeight: 600,
                cursor: isClickable ? 'pointer' : 'default',
                transition: 'background 0.15s ease, border-color 0.15s ease',
            }}
            onMouseEnter={(e) => {
                if (!isClickable) return;
                e.currentTarget.style.background = '#EBF1FF';
                e.currentTarget.style.borderColor = color;
            }}
            onMouseLeave={(e) => {
                if (!isClickable) return;
                e.currentTarget.style.background = '#F8FAFC';
                e.currentTarget.style.borderColor = '#E2E8F0';
            }}
        >
            <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} aria-hidden />
            <span style={{ textTransform: 'capitalize' }}>{platform}</span>
            <span style={{ color: '#94A3B8', fontWeight: 500 }}>·</span>
            <span style={{ fontVariantNumeric: 'tabular-nums', color: '#475569' }}>
                {formatCount(views)}
            </span>
            <span style={{ color: '#94A3B8' }}>views</span>
            <span style={{ color: '#94A3B8', fontWeight: 500 }}>·</span>
            <span style={{ fontVariantNumeric: 'tabular-nums', color: '#337AFF', fontWeight: 700 }}>
                {formatCount(engagement)}
            </span>
        </button>
    );
}

/* ── Helpers ──────────────────────────────────────────────────────────── */

function truncate(s: string, n: number): string {
    if (s.length <= n) return s;
    return s.slice(0, n - 1).trimEnd() + '…';
}

function shortId(id: string): string {
    return id.replace(/-/g, '').slice(0, 6).toUpperCase();
}

/* ── Icons ────────────────────────────────────────────────────────────── */

function SparklesIcon() {
    return (
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z" />
            <path d="M5 19l.8 2.2L8 22l-2.2.8L5 25" transform="scale(0.6)" />
        </svg>
    );
}

function ArrowIcon() {
    return (
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
        </svg>
    );
}

