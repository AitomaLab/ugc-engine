'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import AccountDetailModal from '@/components/analytics/AccountDetailModal';
import AddAccountModal from '@/components/analytics/AddAccountModal';
import AnalyzeSearchBar from '@/components/analytics/AnalyzeSearchBar';
import DashboardView from '@/components/analytics/dashboard/DashboardView';
import PostDetailModal from '@/components/analytics/PostDetailModal';
import {
    ANALYTICS_STUDIO_SYNCED_EVENT,
    DEFAULT_ANALYTICS_PERIOD,
    deleteTrackedAccount,
    trackedAccountToAggregateStub,
    useAccountAggregates,
    useConnections,
    useTrackedAccounts,
    type AccountOwnership,
    type Period,
    type TrackedAccountAggregate,
} from '@/components/analytics/analytics-types';

/**
 * Analytics tab — dashboard-only (v3 redesign).
 *
 * Replaces the previous segmented Accounts/Posts experience with a single
 * dashboard surface. Drilldown into individual posts is still supported via
 * `PostDetailModal` (driven by `?post=<id>` deep links from elsewhere in
 * the app, plus the dashboard's own "Use as Template" flow). External
 * account ingestion still routes through `AnalyzeSearchBar` and
 * `AddAccountModal` so the parser contract in `url_parser.py` is untouched.
 *
 * Per the architecture-reference doc:
 *   • Top-level `AnalyticsTabs` in `schedule/page.tsx` stays untouched
 *   • Intake parser contract via `AnalyzeSearchBar` is preserved
 *   • The `Period` state owns all child widgets through `DashboardView`
 */
export default function AnalyticsTab() {
    const router = useRouter();
    const search = useSearchParams();

    // ── Filter state owned by the dashboard ────────────────────────────
    const [period, setPeriod] = useState<Period>(DEFAULT_ANALYTICS_PERIOD);

    // ── Modal state ────────────────────────────────────────────────────
    // `?post=<id>` deep-link support — lets external surfaces (CTAs in the
    // Calendar, AI suggestions, email links) jump straight into a post.
    const initialPostId = search.get('post');
    const [activePostId, setActivePostId] = useState<string | null>(initialPostId);
    const [activeAccountId, setActiveAccountId] = useState<string | null>(null);
    const [addOpen, setAddOpen] = useState(false);
    const [metricsEpoch, setMetricsEpoch] = useState(0);
    const [accountOwnership, setAccountOwnership] = useState<AccountOwnership>('all');
    const [overviewAccountId, setOverviewAccountId] = useState<string | null>(null);
    const [aggregatesEnabled, setAggregatesEnabled] = useState(false);

    const bumpMetrics = useCallback(() => {
        setMetricsEpoch((n) => n + 1);
    }, []);

    // ── Data hooks the dashboard surface needs ─────────────────────────
    const { accounts: trackedRaw, loading: trackedLoading, reload: reloadAccounts } = useTrackedAccounts();
    const {
        data: aggData,
        loading: aggLoading,
        reload: reloadAggregates,
    } = useAccountAggregates(period, { enabled: aggregatesEnabled });
    const aggregateAccounts = aggData?.accounts ?? [];
    const displayAccounts: TrackedAccountAggregate[] = useMemo(() => {
        if (aggregateAccounts.length > 0) return aggregateAccounts;
        return trackedRaw.map(trackedAccountToAggregateStub);
    }, [aggregateAccounts, trackedRaw]);
    const totalAccounts = aggData?.total_accounts ?? trackedRaw.length;
    const totalScrapedPosts = aggData?.total_scraped_posts ?? 0;
    const avgHealth = aggData?.avg_health_score ?? null;

    const { isStudio, profilePicFor, reload: reloadConnections } = useConnections();

    const reloadAllMetrics = useCallback(() => {
        setAggregatesEnabled(true);
        reloadConnections();
        reloadAccounts();
        reloadAggregates();
        bumpMetrics();
    }, [reloadConnections, reloadAccounts, reloadAggregates, bumpMetrics]);

    const handleStatsReady = useCallback(() => {
        setAggregatesEnabled(true);
    }, []);

    const handleSubviewChange = useCallback((subview: 'overview' | 'videos' | 'accounts') => {
        if (subview === 'accounts') setAggregatesEnabled(true);
    }, []);

    // ── Account detail modal + delete plumbing ─────────────────────────
    const activeAccount = activeAccountId
        ? displayAccounts.find((a) => a.id === activeAccountId) || null
        : null;

    const openAccount = useCallback((id: string) => setActiveAccountId(id), []);
    const closeAccount = useCallback(() => setActiveAccountId(null), []);

    const handleDeleteAccount = useCallback(
        async (accountId: string) => {
            // Optimistic close if the trash was clicked from inside the modal.
            if (activeAccountId === accountId) setActiveAccountId(null);
            if (overviewAccountId === accountId) setOverviewAccountId(null);
            const ok = await deleteTrackedAccount(accountId);
            if (ok) reloadAllMetrics();
        },
        [activeAccountId, overviewAccountId, reloadAllMetrics],
    );

    // Hooks bootstrap their own fetch on mount — no duplicate reloadAllMetrics() here.
    // Studio sync still runs debounced via GET /api/connections?cached=true.

    // Refresh when sync completes elsewhere (connections, schedule, login)
    // OR when the page-level "Refresh data" button fires.
    useEffect(() => {
        const onSynced = () => {
            reloadAllMetrics();
        };
        window.addEventListener(ANALYTICS_STUDIO_SYNCED_EVENT, onSynced);
        return () => {
            window.removeEventListener(ANALYTICS_STUDIO_SYNCED_EVENT, onSynced);
        };
    }, [reloadAllMetrics]);

    // Keep `?post=<id>` ↔ modal in sync without forcing a route transition.
    useEffect(() => {
        const next = search.get('post');
        if (next !== activePostId) setActivePostId(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [search]);

    const closePost = useCallback(() => {
        setActivePostId(null);
        if (search.get('post')) {
            const params = new URLSearchParams(Array.from(search.entries()));
            params.delete('post');
            router.replace(`?${params.toString()}`, { scroll: false });
        }
    }, [router, search]);

    const openPost = useCallback((postId: string) => {
        setActivePostId(postId);
        const params = new URLSearchParams(Array.from(search.entries()));
        params.set('post', postId);
        router.replace(`?${params.toString()}`, { scroll: false });
    }, [router, search]);

    // ── Handlers ───────────────────────────────────────────────────────
    const handleAnalyzed = () => { reloadAllMetrics(); };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Intake — paste-to-track. Mode is fixed to `accounts` because
                the dashboard's primary external workflow is "watch this
                competitor handle"; pasting a bare post URL still routes
                through the same parser thanks to `AnalyzeSearchBar`'s
                URL detection logic. */}
            <AnalyzeSearchBar onAnalyzed={handleAnalyzed} mode="accounts" />

            <DashboardView
                period={period}
                onPeriodChange={setPeriod}
                refreshKey={metricsEpoch}
                onAddExternal={() => setAddOpen(true)}
                onOpenPost={openPost}
                onStatsReady={handleStatsReady}
                onSubviewChange={handleSubviewChange}
                accounts={displayAccounts}
                accountsLoading={aggregatesEnabled && aggLoading}
                trackedAccountsLoading={trackedLoading}
                totalAccounts={totalAccounts}
                totalScrapedPosts={totalScrapedPosts}
                avgHealth={avgHealth}
                onOpenAccount={openAccount}
                onAccountScraped={reloadAllMetrics}
                onDeleteAccount={handleDeleteAccount}
                isStudioAccount={isStudio}
                profilePicFor={profilePicFor}
                ownership={accountOwnership}
                onOwnershipChange={setAccountOwnership}
                overviewAccountId={overviewAccountId}
                onOverviewAccountChange={setOverviewAccountId}
            />

            {/* Modals — kept mounted at the parent so deep-links and
                cross-component triggers (e.g. a CTA inside the dashboard
                opening a post detail) drive them deterministically. */}
            {activePostId && (
                <PostDetailModal
                    postId={activePostId}
                    onClose={closePost}
                    refreshKey={metricsEpoch}
                />
            )}
            {activeAccount && (
                <AccountDetailModal
                    account={activeAccount}
                    onClose={closeAccount}
                    onRefreshed={reloadAllMetrics}
                    onOpenPost={(postId) => {
                        closeAccount();
                        openPost(postId);
                    }}
                    avatarUrl={
                        // Prefer Connections' Ayrshare profilePic for Studio
                        // accounts (always fresh, no scrape needed); fall
                        // back to BrightData-sourced `avatar_url` on the
                        // tracked-account row for External adds.
                        profilePicFor(activeAccount.platform, activeAccount.username)
                        || activeAccount.avatar_url
                        || undefined
                    }
                />
            )}
            {addOpen && (
                <AddAccountModal
                    onClose={() => setAddOpen(false)}
                    onAdded={reloadAllMetrics}
                />
            )}
        </div>
    );
}
