'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
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
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const postsRef = useRef<AnalyticsPost[]>([]);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            if (!postsRef.current.length) setLoading(true);
            setIsRefreshing(true);
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
                postsRef.current = data.items || [];
            } catch (e) {
                if (cancelled) return;
                setError(e instanceof Error ? e.message : 'Failed to load video performance');
                setPosts([]);
                postsRef.current = [];
            } finally {
                if (!cancelled) {
                    setLoading(false);
                    setIsRefreshing(false);
                }
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

            <div className="video-perf-grid">
                {groups.map((g) => (
                    <VideoCard key={g.key} group={g} onOpenPost={onOpenPost} />
                ))}
            </div>

            <style>{`
                .video-perf-grid {
                    display: grid;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    gap: 12px;
                }
                .video-perf-card:hover:not(:disabled) {
                    border-color: #D5DEE8 !important;
                    background: #FFFFFF !important;
                }
                .video-perf-card:hover:not(:disabled) .video-perf-arrow {
                    border-color: #337AFF;
                    color: #FFFFFF;
                    background: #337AFF;
                }
                @media (max-width: 1200px) {
                    .video-perf-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
                }
                @media (max-width: 900px) {
                    .video-perf-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                }
                @media (max-width: 560px) {
                    .video-perf-grid { grid-template-columns: 1fr; }
                }
            `}</style>
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

/* ── Card layout ──────────────────────────────────────────────────────── */

function VideoCard({
    group,
    onOpenPost,
}: {
    group: VideoGroup;
    onOpenPost?: (postId: string) => void;
}) {
    const { t } = useTranslation();
    const topPost = group.platforms[0]?.post;
    const clickable = Boolean(topPost && onOpenPost);

    const open = () => {
        if (topPost && onOpenPost) onOpenPost(topPost.id);
    };

    return (
        <button
            type="button"
            onClick={open}
            disabled={!clickable}
            className="video-perf-card"
            aria-label={clickable ? t('analytics.dashboard.videos.viewDetail') : undefined}
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'stretch',
                textAlign: 'left',
                padding: 0,
                margin: 0,
                width: '100%',
                minWidth: 0,
                height: '100%',
                background: '#FFFFFF',
                border: '1px solid #E8EEF4',
                borderRadius: 12,
                overflow: 'hidden',
                cursor: clickable ? 'pointer' : 'default',
                boxShadow: 'none',
                transition: 'border-color 0.15s ease, background 0.15s ease',
                color: 'inherit',
                font: 'inherit',
            }}
        >
            <Thumbnail
                previewUrl={group.previewUrl}
                videoUrl={group.videoUrl}
                alt={group.caption || group.title}
                platforms={group.platforms.map((p) => p.platform)}
            />

            <div
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                    padding: '10px 12px 12px',
                    minWidth: 0,
                    boxSizing: 'border-box',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, minWidth: 0 }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                        <div
                            style={{
                                fontSize: 12.5,
                                fontWeight: 600,
                                color: '#64748B',
                                lineHeight: 1.3,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                            }}
                            title={group.caption || group.title}
                        >
                            {group.title}
                        </div>
                        <div
                            style={{
                                marginTop: 3,
                                fontSize: 10.5,
                                color: '#A0AEC0',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 5,
                                flexWrap: 'wrap',
                            }}
                        >
                            <span>
                                {group.platforms.length} {t('analytics.dashboard.videos.platforms')}
                                {group.postedAt ? ` · ${timeAgo(group.postedAt)}` : ''}
                            </span>
                            {group.hasBreakdown && (
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, color: '#94A3B8' }}>
                                    <SparklesIcon /> {t('analytics.dashboard.videos.aiAnalyzed')}
                                </span>
                            )}
                        </div>
                    </div>
                    {clickable && (
                        <span
                            className="video-perf-arrow"
                            aria-hidden
                            style={{
                                width: 26,
                                height: 26,
                                borderRadius: '50%',
                                border: '1px solid rgba(51, 122, 255, 0.35)',
                                background: 'rgba(51, 122, 255, 0.10)',
                                color: '#337AFF',
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flexShrink: 0,
                                marginTop: 1,
                                transition: 'border-color 0.15s ease, color 0.15s ease, background 0.15s ease',
                            }}
                        >
                            <CircleArrowIcon />
                        </span>
                    )}
                </div>

                {/* Subtle metrics — soft wash, no heavy boxes */}
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        columnGap: 10,
                        rowGap: 6,
                        padding: '8px 10px',
                        borderRadius: 8,
                        background: 'rgba(148, 163, 184, 0.08)',
                    }}
                >
                    <Metric label={t('analytics.dashboard.videos.metrics.views')} value={group.totals.views} accent />
                    <Metric label={t('analytics.dashboard.videos.metrics.engagement')} value={group.totals.engagement} />
                    <Metric label={t('analytics.dashboard.videos.metrics.likes')} value={group.totals.likes} muted />
                    <Metric label={t('analytics.dashboard.videos.metrics.comments')} value={group.totals.comments} muted />
                </div>
            </div>
        </button>
    );
}

/* ── Sub-components ───────────────────────────────────────────────────── */

function Panel({ children }: { children: React.ReactNode }) {
    return (
        <section
            style={{
                background: 'transparent',
                border: 'none',
                borderRadius: 0,
                padding: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
                boxShadow: 'none',
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
                <div style={{ fontSize: 11, fontWeight: 600, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    {t('analytics.dashboard.videos.label')}
                </div>
                <div style={{ fontSize: 17, fontWeight: 600, color: '#334155', marginTop: 3 }}>
                    {t('analytics.dashboard.videos.title')}
                </div>
                {subtitle && (
                    <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 3 }}>{subtitle}</div>
                )}
            </div>
        </div>
    );
}

function Thumbnail({
    previewUrl,
    videoUrl,
    alt,
    platforms,
}: {
    previewUrl?: string;
    videoUrl?: string;
    alt?: string;
    platforms: string[];
}) {
    return (
        <div
            style={{
                position: 'relative',
                width: '100%',
                height: 104,
                overflow: 'hidden',
                background: '#EEF2F6',
                flexShrink: 0,
            }}
        >
            <VideoThumbnail previewUrl={previewUrl} videoUrl={videoUrl} alt={alt || ''} />
            {platforms.length > 0 && (
                <div
                    style={{
                        position: 'absolute',
                        left: 8,
                        bottom: 8,
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 4,
                        maxWidth: 'calc(100% - 16px)',
                        zIndex: 1,
                        pointerEvents: 'none',
                    }}
                >
                    {platforms.map((platform) => (
                        <PlatformPill key={platform} platform={platform} overlay />
                    ))}
                </div>
            )}
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0 }}>
            <span style={{ fontSize: 9.5, color: '#A0AEC0', textTransform: 'uppercase', letterSpacing: 0.3, fontWeight: 600 }}>
                {label}
            </span>
            <span
                style={{
                    fontSize: muted ? 13 : 14.5,
                    fontWeight: 600,
                    color: accent ? '#5B86D6' : muted ? '#94A3B8' : '#64748B',
                    fontVariantNumeric: 'tabular-nums',
                    lineHeight: 1.15,
                }}
            >
                {formatCount(value)}
            </span>
        </div>
    );
}

const PLATFORM_META: Record<string, { short: string; color: string }> = {
    instagram: { short: 'IG', color: '#C13584' },
    tiktok: { short: 'TT', color: '#0EA5E9' },
    youtube: { short: 'YT', color: '#DC2626' },
    facebook: { short: 'FB', color: '#2563EB' },
};

/** Compact platform pill — short label so names never clip in narrow cards. */
function PlatformPill({ platform, overlay }: { platform: string; overlay?: boolean }) {
    const meta = PLATFORM_META[platform] || { short: platform.slice(0, 2).toUpperCase(), color: '#64748B' };
    return (
        <span
            title={platform}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                flexShrink: 0,
                padding: overlay ? '3px 7px' : '2px 6px',
                borderRadius: 999,
                background: overlay ? 'rgba(15, 23, 42, 0.72)' : 'rgba(148,163,184,0.1)',
                backdropFilter: overlay ? 'blur(6px)' : undefined,
                fontSize: 10,
                fontWeight: 700,
                color: overlay ? '#FFFFFF' : '#94A3B8',
                letterSpacing: 0.2,
                boxShadow: overlay ? '0 1px 3px rgba(0,0,0,0.25)' : undefined,
            }}
        >
            <span style={{ width: 6, height: 6, borderRadius: 2, background: meta.color, flexShrink: 0 }} aria-hidden />
            {meta.short}
        </span>
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

function CircleArrowIcon() {
    return (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
        </svg>
    );
}

