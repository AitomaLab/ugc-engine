'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import Modal from './Modal';
import PostCard from './PostCard';
import TrendChart from './TrendChart';
import StrategyReportMarkdown from './StrategyReportMarkdown';
import {
    analyticsFetch,
    formatCount,
    timeAgo,
    useAccountStrategyReport,
    useAccountTopPosts,
    useAccountTrend,
    type TrackedAccountAggregate,
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
function AvatarPuck({ url, platform }: { url?: string; platform: string }) {
    const accent = PLATFORM_ACCENT[platform] || 'var(--text-3)';
    const [broken, setBroken] = useState(false);
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
            }}
        >
            {platform.slice(0, 1).toUpperCase()}
        </div>
    );
}

export default function AccountDetailModal({ account, onClose, onOpenPost, onRefreshed, avatarUrl }: Props) {
    const { t } = useTranslation();
    const [refreshKey, setRefreshKey] = useState(0);
    const [syncing, setSyncing] = useState(true);
    const [displayCount, setDisplayCount] = useState(24);
    const { data: trend, loading: trendLoading } = useAccountTrend(account.id, 30, refreshKey);
    const { data: top, loading: topLoading } = useAccountTopPosts(account.id, 200, refreshKey);
    const { data: strategy, loading: strategyLoading } = useAccountStrategyReport(account.id, refreshKey);

    /* Every open: scrape the public feed + sync Studio/Ayrshare posts, then
     * reload the chart and latest-posts grid from fresh data. */
    useEffect(() => {
        let cancelled = false;
        setSyncing(true);
        analyticsFetch(
            `/api/analytics/tracked-accounts/${account.id}/refresh`,
            { method: 'POST', skipProjectScope: true },
        )
            .catch(() => { /* show cached data if refresh fails */ })
            .finally(() => {
                if (cancelled) return;
                setSyncing(false);
                setRefreshKey((n) => n + 1);
                onRefreshed?.();
            });
        return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh once per account open
    }, [account.id]);

    const followers = account.follower_count ?? account.followers;
    const delta = top?.studio_vs_external_pct;
    const allPosts = top?.posts ?? [];
    const visiblePosts = displayCount > 0 ? allPosts.slice(0, displayCount) : allPosts;

    const resolvedAvatar = avatarUrl || account.avatar_url || undefined;

    return (
        <Modal
            title={`@${account.username} · ${account.platform}`}
            onClose={onClose}
            maxWidth={920}
        >
            {/* Avatar header — visible profile identity for both Studio &
                External accounts. Sits above the summary metric row so the
                user doesn't have to read the modal title bar to know which
                handle they're inspecting. */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <AvatarPuck url={resolvedAvatar} platform={account.platform} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
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

            {/* Latest posts — all scraped posts loaded; dropdown controls grid density */}
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
                {(syncing || topLoading) && allPosts.length === 0
                    ? <div style={{ fontSize: '12px', color: 'var(--text-3)' }}>
                        {syncing ? t('analytics.accounts.refreshingPosts') : t('common.loading')}
                    </div>
                    : allPosts.length > 0
                        ? (
                            <>
                                <p style={{ margin: 0, fontSize: 11, color: 'var(--text-3)' }}>
                                    {t('analytics.accounts.topPosts.loadedCount')
                                        .replace('{shown}', String(visiblePosts.length))
                                        .replace('{total}', String(allPosts.length))}
                                </p>
                                <div
                                    style={{
                                        display: 'grid',
                                        gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                                        gap: '12px',
                                    }}
                                >
                                    {visiblePosts.map((p) => (
                                        <PostCard key={p.id} post={p} onOpen={onOpenPost} />
                                    ))}
                                </div>
                            </>
                        )
                        : <div style={{ fontSize: '12px', color: 'var(--text-3)' }}>{t('analytics.accounts.topPosts.empty')}</div>
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
                            {(strategyLoading || syncing)
                                ? t('analytics.accounts.strategy.loading')
                                : t('analytics.accounts.strategy.pending')}
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
