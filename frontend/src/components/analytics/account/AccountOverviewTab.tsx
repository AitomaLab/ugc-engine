'use client';

import { useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import PostCard from '../PostCard';
import TrendChart from '../TrendChart';
import {
    formatCount,
    type AnalyticsPost,
    type AccountTrendResponse,
    type TrackedAccountAggregate,
} from '../analytics-types';
import { Section, StatCell, renderInlineBold } from './AccountUiKit';

interface Props {
    account: TrackedAccountAggregate;
    posts: AnalyticsPost[];
    /** Selected period in days — drives the trend heading. */
    periodDays: number;
    postsLoading: boolean;
    isRefreshing: boolean;
    thumbMap: Record<string, string>;
    trend: AccountTrendResponse | null;
    trendLoading: boolean;
    /** Studio-vs-external engagement delta (%) — only shown when both sides exist. */
    delta: number | null | undefined;
    /** Top 2-3 ranked actions from the strategy report (teaser). */
    topActions: string[];
    onOpenPost: (postId: string) => void;
    onOpenStrategy: () => void;
}

const GRID_STEP = 12;

export default function AccountOverviewTab({
    account,
    posts,
    periodDays,
    postsLoading,
    isRefreshing,
    thumbMap,
    trend,
    trendLoading,
    delta,
    topActions,
    onOpenPost,
    onOpenStrategy,
}: Props) {
    const { t } = useTranslation();
    const [visibleCount, setVisibleCount] = useState(GRID_STEP);

    const followers = account.follower_count ?? account.followers;
    const visiblePosts = posts.slice(0, visibleCount);
    const hasMore = posts.length > visiblePosts.length;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {/* KPI strip */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8 }}>
                {account.platform === 'tiktok' && (
                    <StatCell label={t('analytics.accounts.metrics.views')} value={formatCount(account.total_views)} />
                )}
                <StatCell label={t('analytics.accounts.metrics.engagement')} value={formatCount(account.total_engagement)} accent />
                <StatCell label={t('analytics.accounts.metrics.followers')} value={followers != null ? formatCount(followers) : '—'} />
                <StatCell label={t('analytics.accounts.metrics.posts')} value={String(account.posts_in_period)} />
                <StatCell label={t('analytics.accounts.metrics.engRate')} value={`${account.avg_engagement_rate.toFixed(2)}%`} />
            </div>

            {/* Studio vs External delta */}
            {delta !== null && delta !== undefined && (
                <div
                    style={{
                        padding: '10px 14px',
                        borderRadius: 10,
                        background: delta >= 0 ? 'rgba(52,199,89,0.10)' : 'rgba(255,159,10,0.10)',
                        color: delta >= 0 ? '#1f7a3a' : '#a35a00',
                        fontSize: 13,
                        fontWeight: 600,
                    }}
                >
                    {delta >= 0
                        ? t('analytics.accounts.delta.beats').replace('{pct}', String(Math.abs(delta)))
                        : t('analytics.accounts.delta.behind').replace('{pct}', String(Math.abs(delta)))}
                </div>
            )}

            {/* AI snapshot — top ranked actions, links into the Strategy tab */}
            {topActions.length > 0 && (
                <Section
                    title={t('analytics.accounts.overview.aiSnapshot')}
                    action={
                        <button
                            type="button"
                            onClick={onOpenStrategy}
                            style={{
                                padding: '5px 10px',
                                borderRadius: 8,
                                border: '1px solid var(--border)',
                                background: 'white',
                                color: 'var(--blue)',
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: 'pointer',
                                whiteSpace: 'nowrap',
                            }}
                        >
                            {t('analytics.accounts.overview.seeStrategy')} →
                        </button>
                    }
                >
                    <div
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 8,
                            background: 'linear-gradient(180deg, rgba(51,122,255,0.06), rgba(51,122,255,0.02))',
                            border: '1px solid rgba(51,122,255,0.18)',
                            borderRadius: 14,
                            padding: '14px 16px',
                        }}
                    >
                        {topActions.slice(0, 3).map((item, i) => (
                            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                                <span
                                    aria-hidden
                                    style={{
                                        flexShrink: 0,
                                        width: 20, height: 20, borderRadius: '50%',
                                        background: 'var(--blue)', color: 'white',
                                        fontSize: 11, fontWeight: 800,
                                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                        marginTop: 1,
                                    }}
                                >
                                    {i + 1}
                                </span>
                                <span style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--text-2)', minWidth: 0 }}>
                                    {renderInlineBold(item, `snap-${i}`)}
                                </span>
                            </div>
                        ))}
                    </div>
                </Section>
            )}

            {/* 30-day trend */}
            <Section title={t('analytics.accounts.trend.title').replace('{days}', String(periodDays))}>
                {trendLoading && !(trend?.points?.length)
                    ? <div style={{ fontSize: 12, color: 'var(--text-3)' }}>{t('common.loading')}</div>
                    : <TrendChart points={trend?.points || []} />
                }
            </Section>

            {/* Post grid with real previews */}
            <Section
                title={t('analytics.accounts.topPosts.title')}
                subtitle={
                    posts.length > 0
                        ? t('analytics.accounts.topPosts.loadedCount')
                            .replace('{shown}', String(visiblePosts.length))
                            .replace('{total}', String(posts.length))
                        : undefined
                }
            >
                {postsLoading && posts.length === 0 ? (
                    <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                        {isRefreshing ? t('analytics.accounts.refreshingPosts') : t('common.loading')}
                    </div>
                ) : posts.length === 0 ? (
                    <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                        {isRefreshing ? t('analytics.accounts.refreshingPosts') : t('analytics.accounts.topPosts.empty')}
                    </div>
                ) : (
                    <>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
                            {visiblePosts.map((p) => (
                                <PostCard key={p.id} post={p} thumbnailUrl={thumbMap[p.id]} onOpen={onOpenPost} />
                            ))}
                        </div>
                        {hasMore && (
                            <button
                                type="button"
                                onClick={() => setVisibleCount((n) => n + GRID_STEP)}
                                style={{
                                    alignSelf: 'center',
                                    marginTop: 4,
                                    padding: '7px 16px',
                                    borderRadius: 8,
                                    border: '1px solid var(--border)',
                                    background: 'white',
                                    color: 'var(--text-2)',
                                    fontSize: 12,
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                }}
                            >
                                {t('analytics.accounts.topPosts.loadMore')}
                            </button>
                        )}
                    </>
                )}
            </Section>
        </div>
    );
}
