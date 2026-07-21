'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import {
    analyticsFetch,
    isWithinTrailingDays,
    periodToDays,
    pollScrapeJob,
    timeAgo,
    useAccountStrategyReport,
    useAccountTopPosts,
    useAccountTrend,
    useAnalyticsPostThumbnails,
    type Period,
    type TrackedAccountAggregate,
    type TrackedAccountWithJob,
} from '../analytics-types';
import { parseStrategyReport } from './parseAccountReport';
import AccountOverviewTab from './AccountOverviewTab';
import AccountStrategyTab from './AccountStrategyTab';
import AccountVideosGrid from './AccountVideosGrid';
import LearningsView from './LearningsView';

export type AnalyticsViewKey = 'overview' | 'videos' | 'strategy' | 'learnings';

/**
 * Per-account background refresh — kicks a scrape on scope-in, exposes the
 * spinner + "Last updated" status for the parent toolbar so the surface has
 * exactly one refresh affordance. Pass `null` while the scope is All
 * accounts; the hook is inert until an account is selected.
 */
export function useAccountBackgroundRefresh(
    account: TrackedAccountAggregate | null,
    onRefreshed?: () => void,
) {
    const { t } = useTranslation();
    const [epoch, setEpoch] = useState(0);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [lastScrapedAt, setLastScrapedAt] = useState<string | null>(account?.last_scraped_at ?? null);
    const [justUpdated, setJustUpdated] = useState(false);
    const justUpdatedTimer = useRef<number | null>(null);
    const refreshInFlight = useRef(false);
    const accountId = account?.id ?? null;

    useEffect(() => {
        setLastScrapedAt(account?.last_scraped_at ?? null);
    }, [accountId, account?.last_scraped_at]);

    const markJustUpdated = useCallback(() => {
        setJustUpdated(true);
        if (justUpdatedTimer.current) window.clearTimeout(justUpdatedTimer.current);
        justUpdatedTimer.current = window.setTimeout(() => setJustUpdated(false), 5000);
    }, []);

    const refresh = useCallback(async () => {
        if (!accountId || refreshInFlight.current) return;
        refreshInFlight.current = true;
        setIsRefreshing(true);
        try {
            const res = await analyticsFetch<TrackedAccountWithJob>(
                `/api/analytics/tracked-accounts/${accountId}/refresh`,
                { method: 'POST', skipProjectScope: true },
            );
            if (res.account?.last_scraped_at) {
                setLastScrapedAt(res.account.last_scraped_at);
            }
            if (res.job_id) {
                const polled = await pollScrapeJob(res.job_id);
                if (polled.status === 'completed') {
                    setEpoch((n) => n + 1);
                    markJustUpdated();
                    setLastScrapedAt(new Date().toISOString());
                    onRefreshed?.();
                } else if (polled.status === 'failed') {
                    console.warn('[AccountScopeView] refresh failed:', polled.error_message);
                }
            }
        } catch (err) {
            console.warn('[AccountScopeView] refresh error:', err);
        } finally {
            setIsRefreshing(false);
            refreshInFlight.current = false;
        }
    }, [accountId, markJustUpdated, onRefreshed]);

    /*
     * No auto-scrape on scope-in. A refresh runs the whole pipeline (scrape →
     * metrics → a fresh LLM strategy report), so firing it on every mount cost
     * 10-15s on each navigation and rewrote the report under the user. Data
     * still self-updates via the nightly sweep and the page-level
     * `analyticsStudioSynced` event; the toolbar Refresh button is the manual path.
     */
    useEffect(() => () => {
        if (justUpdatedTimer.current) window.clearTimeout(justUpdatedTimer.current);
    }, []);

    const statusLabel = !account
        ? ''
        : isRefreshing
            ? t('analytics.accounts.refreshingPostsStatus')
            : justUpdated
                ? t('analytics.accounts.updatedJustNow')
                : lastScrapedAt
                    ? `${t('analytics.accounts.lastUpdated')} ${timeAgo(lastScrapedAt)}`
                    : t('analytics.accounts.neverScraped');

    return { epoch, isRefreshing, statusLabel, refresh };
}

interface Props {
    account: TrackedAccountAggregate;
    view: AnalyticsViewKey;
    /** Drives the trend window and filters the post grids. */
    period: Period;
    /** Studio (OAuth-linked) — gates the AI Learnings body. */
    isStudio: boolean;
    /** Combined refresh epoch (parent metrics + per-account scrapes). */
    refreshKey?: number;
    /** True while the toolbar's per-account refresh is scraping. */
    isRefreshing?: boolean;
    onOpenPost: (postId: string) => void;
    /** Switch the top-level view tab (AI snapshot → full strategy). */
    onSwitchView: (view: AnalyticsViewKey) => void;
}

/**
 * Scoped account surface — data container for every tab when the scope bar
 * has a single account selected. The parent owns navigation (scope bar +
 * view tabs) and the refresh affordance (via `useAccountBackgroundRefresh`),
 * so this renders only the active view body.
 */
export default function AccountScopeView({
    account,
    view,
    period,
    isStudio,
    refreshKey = 0,
    isRefreshing = false,
    onOpenPost,
    onSwitchView,
}: Props) {
    const { lang } = useTranslation();
    const periodDays = periodToDays(period);

    const { data: trend, loading: trendLoading } = useAccountTrend(account.id, periodDays, refreshKey);
    const { data: top, loading: topLoading } = useAccountTopPosts(account.id, 48, refreshKey);
    const { data: strategy, loading: strategyLoading } = useAccountStrategyReport(account.id, refreshKey, lang);

    const posts = useMemo(() => top?.posts ?? [], [top]);
    const thumbMap = useAnalyticsPostThumbnails(posts);

    /**
     * `/accounts/{id}/top-posts` has no period filter, so scope the grids
     * client-side. Keeps the post lists consistent with the period-driven
     * KPI strip (which reads "posts in period") instead of always showing
     * the full history regardless of the selected range.
     */
    const periodPosts = useMemo(
        () => posts.filter((p) => isWithinTrailingDays(p.posted_at || p.scraped_at, periodDays)),
        [posts, periodDays],
    );
    const strategyParsed = useMemo(
        () => (strategy?.report ? parseStrategyReport(strategy.report) : null),
        [strategy],
    );

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {view === 'overview' && (
                <AccountOverviewTab
                    account={account}
                    posts={periodPosts}
                    periodDays={periodDays}
                    postsLoading={topLoading}
                    isRefreshing={isRefreshing}
                    thumbMap={thumbMap}
                    trend={trend}
                    trendLoading={trendLoading}
                    delta={top?.studio_vs_external_pct}
                    topActions={strategyParsed?.actionItems ?? []}
                    onOpenPost={onOpenPost}
                    onOpenStrategy={() => onSwitchView('strategy')}
                />
            )}

            {view === 'videos' && (
                <AccountVideosGrid
                    posts={periodPosts}
                    loading={topLoading}
                    isRefreshing={isRefreshing}
                    thumbMap={thumbMap}
                    onOpenPost={onOpenPost}
                />
            )}

            {view === 'strategy' && (
                <AccountStrategyTab
                    report={strategy?.report ?? null}
                    loading={strategyLoading}
                    isRefreshing={isRefreshing}
                    posts={posts}
                    thumbMap={thumbMap}
                    onOpenPost={onOpenPost}
                />
            )}

            {view === 'learnings' && isStudio && (
                <LearningsView refreshKey={refreshKey} />
            )}
        </div>
    );
}
