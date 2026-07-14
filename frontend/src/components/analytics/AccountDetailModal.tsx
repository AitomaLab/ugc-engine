'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import Modal from './Modal';
import PostCard from './PostCard';
import TrendChart from './TrendChart';
import StrategyReportMarkdown from './StrategyReportMarkdown';
import {
    analyticsFetch,
    formatCount,
    pollScrapeJob,
    timeAgo,
    useAccountStrategyReport,
    useAccountTopPosts,
    useAccountTrend,
    useAnalyticsPostThumbnails,
    useCreativeGuidelines,
    type TrackedAccountAggregate,
    type TrackedAccountWithJob,
} from './analytics-types';

interface Props {
    account: TrackedAccountAggregate;
    onClose: () => void;
    /** Open a specific post in the existing PostDetailModal (driven by the
     *  parent so both modals don't try to render on top of each other). */
    onOpenPost: (postId: string) => void;
    /** Called after a fresh scrape/sync completes so parent KPIs update. */
    onRefreshed?: () => void;
    /**
     * Resolved profile photo URL — caller (AnalyticsTab) should pass a
     * Connections `profilePic` for Studio accounts and fall back to the
     * tracked-account `avatar_url` for External accounts. Undefined means
     * we render a coloured initial circle.
     */
    avatarUrl?: string;
}

/**
 * Account detail panel — the "card click" destination from the Accounts grid.
 *
 *   • 30-day engagement trend (TrendChart)
 *   • Top 5 posts (re-uses PostCard for visual consistency with the Posts feed)
 *   • Scrape config summary (frequency + top-N)
 *   • Lightweight Scrape Jobs log (recent runs, expandable drawer)
 *   • Studio-vs-External delta header when both kinds of posts exist
 *
 * The trend + top-posts panes are independently fetched so a slow top-posts
 * query doesn't block the chart from rendering.
 */
const PLATFORM_ACCENT: Record<string, string> = {
    instagram: '#E1306C',
    tiktok:    '#000000',
    youtube:   '#FF0000',
    facebook:  '#1877F2',
};

/**
 * Compact avatar puck rendered above the summary metrics so external
 * accounts get the same visual identity treatment as Studio-connected
 * ones. Falls back to a platform-tinted initial circle when no photo
 * URL is available (e.g. a freshly-added @handle whose BrightData scrape
 * didn't surface `profile_pic_url`).
 */
function AvatarPuck({ url, platform, pulsing }: { url?: string; platform: string; pulsing?: boolean }) {
    const accent = PLATFORM_ACCENT[platform] || 'var(--text-3)';
    const [broken, setBroken] = useState(false);
    const ringStyle = pulsing
        ? { boxShadow: `0 0 0 3px ${accent}33`, animation: 'accountRefreshPulse 1.2s ease-in-out infinite' }
        : {};
    if (url && !broken) {
        return (
            // eslint-disable-next-line @next/next/no-img-element
            <img
                src={url}
                alt=""
                loading="lazy"
                referrerPolicy="no-referrer"
                onError={() => setBroken(true)}
                style={{
                    width: 56, height: 56, borderRadius: '50%',
                    objectFit: 'cover',
                    border: '2px solid var(--border)',
                    background: 'var(--blue-light)',
                    flexShrink: 0,
                    ...ringStyle,
                }}
            />
        );
    }
    return (
        <div
            aria-hidden
            style={{
                width: 56, height: 56, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: `${accent}18`,
                color: accent,
                fontSize: 22, fontWeight: 800,
                border: '2px solid var(--border)',
                flexShrink: 0,
                ...ringStyle,
            }}
        >
            {platform.slice(0, 1).toUpperCase()}
        </div>
    );
}

function RefreshSpinner() {
    return (
        <span
            aria-hidden
            style={{
                width: 14,
                height: 14,
                borderRadius: '50%',
                border: '2px solid rgba(51,122,255,0.25)',
                borderTopColor: 'var(--blue)',
                animation: 'accountRefreshSpin 0.8s linear infinite',
                flexShrink: 0,
            }}
        />
    );
}

export default function AccountDetailModal({ account, onClose, onOpenPost, onRefreshed, avatarUrl }: Props) {
    const { t, lang } = useTranslation();
    const [refreshKey, setRefreshKey] = useState(0);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [lastScrapedAt, setLastScrapedAt] = useState<string | null>(account.last_scraped_at ?? null);
    const [justUpdated, setJustUpdated] = useState(false);
    const [displayCount, setDisplayCount] = useState(24);
    const justUpdatedTimer = useRef<number | null>(null);
    const refreshInFlight = useRef(false);

    const fetchLimit = displayCount === 0 ? 200 : Math.max(displayCount, 48);

    const { data: trend, loading: trendLoading } = useAccountTrend(account.id, 30, refreshKey);
    const { data: top, loading: topLoading } = useAccountTopPosts(account.id, fetchLimit, refreshKey);
    const { data: strategy, loading: strategyLoading } = useAccountStrategyReport(account.id, refreshKey, lang);
    const { data: guidelines, loading: guidelinesLoading } = useCreativeGuidelines(refreshKey);

    useEffect(() => {
        setLastScrapedAt(account.last_scraped_at ?? null);
    }, [account.id, account.last_scraped_at]);

    const markJustUpdated = useCallback(() => {
        setJustUpdated(true);
        if (justUpdatedTimer.current) window.clearTimeout(justUpdatedTimer.current);
        justUpdatedTimer.current = window.setTimeout(() => setJustUpdated(false), 5000);
    }, []);

    const startBackgroundRefresh = useCallback(async () => {
        if (refreshInFlight.current) return;
        refreshInFlight.current = true;
        setIsRefreshing(true);
        try {
            const res = await analyticsFetch<TrackedAccountWithJob>(
                `/api/analytics/tracked-accounts/${account.id}/refresh`,
                { method: 'POST', skipProjectScope: true },
            );
            if (res.account?.last_scraped_at) {
                setLastScrapedAt(res.account.last_scraped_at);
            }
            if (res.job_id) {
                const polled = await pollScrapeJob(res.job_id);
                if (polled.status === 'completed') {
                    setRefreshKey((n) => n + 1);
                    markJustUpdated();
                    setLastScrapedAt(new Date().toISOString());
                    onRefreshed?.();
                } else if (polled.status === 'failed') {
                    console.warn('[AccountDetailModal] refresh failed:', polled.error_message);
                }
            }
        } catch (err) {
            console.warn('[AccountDetailModal] refresh error:', err);
        } finally {
            setIsRefreshing(false);
            refreshInFlight.current = false;
        }
    }, [account.id, markJustUpdated, onRefreshed]);

    /* Kick off a background refresh on open — cached posts render immediately. */
    useEffect(() => {
        startBackgroundRefresh();
        return () => {
            if (justUpdatedTimer.current) window.clearTimeout(justUpdatedTimer.current);
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh once per account open
    }, [account.id]);

    const followers = account.follower_count ?? account.followers;
    const delta = top?.studio_vs_external_pct;
    const allPosts = top?.posts ?? [];
    const visiblePosts = displayCount > 0 ? allPosts.slice(0, displayCount) : allPosts;
    const thumbMap = useAnalyticsPostThumbnails(visiblePosts);

    const resolvedAvatar = avatarUrl || account.avatar_url || undefined;

    const refreshStatusLabel = (() => {
        if (isRefreshing) return t('analytics.accounts.refreshingPostsStatus');
        if (justUpdated) return t('analytics.accounts.updatedJustNow');
        if (lastScrapedAt) {
            return `${t('analytics.accounts.lastUpdated')} ${timeAgo(lastScrapedAt)}`;
        }
        return t('analytics.accounts.neverScraped');
    })();

    return (
        <Modal
            title={`@${account.username} · ${account.platform}`}
            onClose={onClose}
            maxWidth={920}
        >
            <style>{`
                @keyframes accountRefreshSpin {
                    to { transform: rotate(360deg); }
                }
                @keyframes accountRefreshPulse {
                    0%, 100% { box-shadow: 0 0 0 3px rgba(51,122,255,0.15); }
                    50% { box-shadow: 0 0 0 5px rgba(51,122,255,0.35); }
                }
            `}</style>

            {/* Avatar header — visible profile identity for both Studio &
                External accounts. Sits above the summary metric row so the
                user doesn't have to read the modal title bar to know which
                handle they're inspecting. */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <AvatarPuck url={resolvedAvatar} platform={account.platform} pulsing={isRefreshing} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0, flex: 1 }}>
                    <span style={{
                        fontSize: 16, fontWeight: 800, color: 'var(--text-1)',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
                        @{account.username}
                    </span>
                    <span style={{
                        fontSize: 11, fontWeight: 700,
                        color: PLATFORM_ACCENT[account.platform] || 'var(--text-3)',
                        textTransform: 'uppercase', letterSpacing: 0.4,
                    }}>
                        {account.platform}
                        {account.linked_via_connections && (
                            <span style={{
                                marginLeft: 8,
                                color: 'var(--blue)',
                                background: 'rgba(51,122,255,0.12)',
                                padding: '2px 8px', borderRadius: 999,
                                fontSize: 10,
                            }}>
                                {t('analytics.accounts.ownership.studioBadge')}
                            </span>
                        )}
                    </span>
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        flexWrap: 'wrap',
                        marginTop: 2,
                    }}>
                        {isRefreshing && <RefreshSpinner />}
                        <span style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 500 }}>
                            {refreshStatusLabel}
                        </span>
                        <button
                            type="button"
                            onClick={() => startBackgroundRefresh()}
                            disabled={isRefreshing}
                            style={{
                                marginLeft: 'auto',
                                padding: '4px 10px',
                                borderRadius: 8,
                                border: '1px solid var(--border)',
                                background: isRefreshing ? 'var(--surface)' : 'white',
                                color: 'var(--text-2)',
                                fontSize: 11,
                                fontWeight: 600,
                                cursor: isRefreshing ? 'default' : 'pointer',
                                opacity: isRefreshing ? 0.6 : 1,
                            }}
                        >
                            {isRefreshing ? t('analytics.accounts.analyzing') : t('analytics.tracked.refresh')}
                        </button>
                    </div>
                </div>
            </div>

            {/* Studio vs External delta — only when both sides have data */}
            {delta !== null && delta !== undefined && (
                <div
                    style={{
                        padding: '12px 14px',
                        borderRadius: '10px',
                        background: delta >= 0 ? 'rgba(52,199,89,0.10)' : 'rgba(255,159,10,0.10)',
                        color: delta >= 0 ? '#1f7a3a' : '#a35a00',
                        fontSize: '13px',
                        fontWeight: 600,
                    }}
                >
                    {delta >= 0
                        ? t('analytics.accounts.delta.beats').replace('{pct}', String(Math.abs(delta)))
                        : t('analytics.accounts.delta.behind').replace('{pct}', String(Math.abs(delta)))}
                </div>
            )}

            {/* Summary metric row */}
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
                    gap: '8px',
                }}
            >
                {account.platform === 'tiktok' && (
                    <SummaryCell label={t('analytics.accounts.metrics.views')} value={formatCount(account.total_views)} />
                )}
                <SummaryCell label={t('analytics.accounts.metrics.engagement')} value={formatCount(account.total_engagement)} accent />
                <SummaryCell label={t('analytics.accounts.metrics.followers')} value={followers != null ? formatCount(followers) : '—'} />
                <SummaryCell label={t('analytics.accounts.metrics.posts')} value={String(account.posts_in_period)} />
                <SummaryCell label={t('analytics.accounts.metrics.engRate')} value={`${account.avg_engagement_rate.toFixed(2)}%`} />
            </div>

            {/* Trend chart */}
            <Section title={t('analytics.accounts.trend.title')}>
                {trendLoading
                    ? <div style={{ fontSize: '12px', color: 'var(--text-3)' }}>{t('common.loading')}</div>
                    : <TrendChart points={trend?.points || []} />
                }
            </Section>

            {/* Latest posts — cached data shown while background refresh runs */}
            <Section
                title={t('analytics.accounts.topPosts.title')}
                action={
                    allPosts.length > 0 ? (
                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-2)' }}>
                            <span>{t('analytics.accounts.topPosts.show')}</span>
                            <select
                                value={displayCount}
                                onChange={(e) => setDisplayCount(Number(e.target.value))}
                                style={{
                                    padding: '4px 8px',
                                    borderRadius: 6,
                                    border: '1px solid var(--border)',
                                    fontSize: 12,
                                    fontWeight: 600,
                                    background: 'white',
                                    color: 'var(--text-1)',
                                }}
                            >
                                <option value={12}>12</option>
                                <option value={24}>24</option>
                                <option value={48}>48</option>
                                <option value={0}>{t('analytics.accounts.topPosts.all')}</option>
                            </select>
                        </label>
                    ) : null
                }
            >
                {topLoading && allPosts.length === 0
                    ? <div style={{ fontSize: '12px', color: 'var(--text-3)' }}>{t('common.loading')}</div>
                    : allPosts.length > 0
                        ? (
                            <>
                                <p style={{ margin: 0, fontSize: 11, color: 'var(--text-3)' }}>
                                    {t('analytics.accounts.topPosts.loadedCount')
                                        .replace('{shown}', String(visiblePosts.length))
                                        .replace('{total}', String(allPosts.length))}
                                    {isRefreshing ? ` · ${t('analytics.accounts.refreshingPostsStatus')}` : ''}
                                </p>
                                <div
                                    style={{
                                        display: 'grid',
                                        gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                                        gap: '12px',
                                    }}
                                >
                                    {visiblePosts.map((p) => (
                                        <PostCard
                                            key={p.id}
                                            post={p}
                                            thumbnailUrl={thumbMap[p.id]}
                                            onOpen={onOpenPost}
                                        />
                                    ))}
                                </div>
                            </>
                        )
                        : <div style={{ fontSize: '12px', color: 'var(--text-3)' }}>
                            {isRefreshing
                                ? t('analytics.accounts.refreshingPosts')
                                : t('analytics.accounts.topPosts.empty')}
                        </div>
                }
            </Section>

            {/* AI Strategy Report — "Do More / Do Less" diagnosis generated
                asynchronously after each refresh. Pending until the analyzer
                thread persists the first report. */}
            <Section
                title={t('analytics.accounts.strategy.title')}
                action={
                    strategy?.generated_at ? (
                        <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                            {t('analytics.accounts.strategy.updated').replace('{when}', timeAgo(strategy.generated_at))}
                        </span>
                    ) : null
                }
            >
                {strategy?.report
                    ? (
                        <div
                            style={{
                                background: 'white',
                                border: '1px solid var(--border)',
                                borderRadius: 12,
                                padding: '16px 18px',
                            }}
                        >
                            <StrategyReportMarkdown source={strategy.report} />
                        </div>
                    )
                    : (
                        <div
                            style={{
                                background: 'var(--blue-light)',
                                border: '1px dashed var(--border)',
                                borderRadius: 12,
                                padding: '16px 18px',
                                fontSize: 13,
                                color: 'var(--text-2)',
                                lineHeight: 1.5,
                            }}
                        >
                            {strategyLoading
                                ? t('analytics.accounts.strategy.loading')
                                : t('analytics.accounts.strategy.pending')}
                        </div>
                    )
                }
            </Section>

            {/* What Your AI Has Learned — user-level creative guidelines the
                nightly self-improvement reflection maintains. Creator-wide
                (spans all connected accounts), rendered read-only. */}
            <Section
                title={t('analytics.accounts.guidelines.title')}
                action={
                    guidelines?.updated_at ? (
                        <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                            {t('analytics.accounts.guidelines.updated').replace('{when}', timeAgo(guidelines.updated_at))}
                        </span>
                    ) : null
                }
            >
                {guidelines?.guidelines
                    ? (
                        <div
                            style={{
                                background: 'white',
                                border: '1px solid var(--border)',
                                borderRadius: 12,
                                padding: '16px 18px',
                            }}
                        >
                            <StrategyReportMarkdown source={guidelines.guidelines} />
                        </div>
                    )
                    : (
                        <div
                            style={{
                                background: 'var(--blue-light)',
                                border: '1px dashed var(--border)',
                                borderRadius: 12,
                                padding: '16px 18px',
                                fontSize: 13,
                                color: 'var(--text-2)',
                                lineHeight: 1.5,
                            }}
                        >
                            {guidelinesLoading
                                ? t('analytics.accounts.guidelines.loading')
                                : t('analytics.accounts.guidelines.empty')}
                        </div>
                    )
                }
            </Section>
        </Modal>
    );
}

function SummaryCell({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
    return (
        <div
            style={{
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: '10px',
                padding: '10px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
                minWidth: 0,
            }}
        >
            <span style={{ fontSize: '15px', fontWeight: 700, color: accent ? 'var(--blue)' : 'var(--text-1)' }}>
                {value}
            </span>
            <span style={{ fontSize: '10px', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: 0.4 }}>
                {label}
            </span>
        </div>
    );
}

function Section({
    title, action, children,
}: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
    return (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h3 style={{ margin: 0, fontSize: '12px', fontWeight: 700, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    {title}
                </h3>
                {action}
            </div>
            {children}
        </section>
    );
}
