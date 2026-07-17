'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import AccountDetailView from '@/components/analytics/AccountDetailModal';
import AddAccountModal from '@/components/analytics/AddAccountModal';
import DashboardView, {
    type DashboardSubview,
} from '@/components/analytics/dashboard/DashboardView';
import PostDetailView from '@/components/analytics/PostDetailModal';
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

interface Props {
    /** Page-level refresh-all handler (hits /api/analytics/refresh-all). */
    onRefreshAll?: () => void;
    refreshing?: boolean;
}

function parseSubview(raw: string | null): DashboardSubview {
    if (raw === 'videos' || raw === 'accounts' || raw === 'overview') return raw;
    return 'overview';
}

function inferSubview(search: URLSearchParams): DashboardSubview {
    const explicit = parseSubview(search.get('view'));
    if (search.get('view')) return explicit;
    // Deep links without ?view= — land on the relevant list after Back.
    if (search.get('account')) return 'accounts';
    return 'overview';
}

/**
 * Analytics tab — dashboard with full-page post (`?post=`) and account
 * (`?account=`) detail. Opening a post from an account keeps `account` in
 * the URL so Back returns to the account page. Subview is lifted + synced
 * via `?view=` so Back restores By Video / Accounts instead of Overview.
 */
export default function AnalyticsTab({ onRefreshAll, refreshing = false }: Props) {
    const router = useRouter();
    const search = useSearchParams();

    const [period, setPeriod] = useState<Period>(DEFAULT_ANALYTICS_PERIOD);

    const initialPostId = search.get('post');
    const initialAccountId = search.get('account');
    const [activePostId, setActivePostId] = useState<string | null>(initialPostId);
    const [activeAccountId, setActiveAccountId] = useState<string | null>(initialAccountId);
    const [subview, setSubview] = useState<DashboardSubview>(() => inferSubview(search));
    const [addOpen, setAddOpen] = useState(false);
    const [metricsEpoch, setMetricsEpoch] = useState(0);
    const [accountOwnership, setAccountOwnership] = useState<AccountOwnership>('all');
    const [overviewAccountId, setOverviewAccountId] = useState<string | null>(null);
    const [aggregatesEnabled, setAggregatesEnabled] = useState(
        () => inferSubview(search) === 'accounts' || Boolean(initialAccountId),
    );

    const writeParams = useCallback((mutate: (params: URLSearchParams) => void) => {
        const params = new URLSearchParams(Array.from(search.entries()));
        mutate(params);
        const qs = params.toString();
        router.replace(qs ? `?${qs}` : '?', { scroll: false });
    }, [router, search]);

    const persistSubview = useCallback((next: DashboardSubview, params: URLSearchParams) => {
        if (next === 'overview') params.delete('view');
        else params.set('view', next);
    }, []);

    const bumpMetrics = useCallback(() => {
        setMetricsEpoch((n) => n + 1);
    }, []);

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

    const handleSubviewChange = useCallback((next: DashboardSubview) => {
        setSubview(next);
        if (next === 'accounts') setAggregatesEnabled(true);
        writeParams((params) => {
            persistSubview(next, params);
        });
    }, [persistSubview, writeParams]);

    const activeAccount = activeAccountId
        ? displayAccounts.find((a) => a.id === activeAccountId) || null
        : null;

    useEffect(() => {
        const onSynced = () => {
            reloadAllMetrics();
        };
        window.addEventListener(ANALYTICS_STUDIO_SYNCED_EVENT, onSynced);
        return () => {
            window.removeEventListener(ANALYTICS_STUDIO_SYNCED_EVENT, onSynced);
        };
    }, [reloadAllMetrics]);

    // Deep-linked account detail needs aggregates so we can resolve the row.
    useEffect(() => {
        if (activeAccountId) setAggregatesEnabled(true);
    }, [activeAccountId]);

    // Sync URL → state for post, account, and dashboard subview.
    useEffect(() => {
        const nextPost = search.get('post');
        const nextAccount = search.get('account');
        const nextView = inferSubview(search);
        if (nextPost !== activePostId) setActivePostId(nextPost);
        if (nextAccount !== activeAccountId) setActiveAccountId(nextAccount);
        if (nextView !== subview) {
            setSubview(nextView);
            if (nextView === 'accounts') setAggregatesEnabled(true);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [search]);

    const closePost = useCallback(() => {
        setActivePostId(null);
        writeParams((params) => {
            params.delete('post');
            persistSubview(subview, params);
        });
    }, [persistSubview, subview, writeParams]);

    const openPost = useCallback((postId: string) => {
        // Coming from By Video → keep videos; from account → keep accounts.
        const nextView: DashboardSubview = activeAccountId
            ? 'accounts'
            : subview === 'overview'
                ? 'videos'
                : subview;
        setSubview(nextView);
        setActivePostId(postId);
        writeParams((params) => {
            params.set('post', postId);
            persistSubview(nextView, params);
            // Keep existing ?account= so Back from post returns to account detail.
        });
    }, [activeAccountId, persistSubview, subview, writeParams]);

    const openAccount = useCallback((id: string) => {
        setActiveAccountId(id);
        setSubview('accounts');
        setAggregatesEnabled(true);
        writeParams((params) => {
            params.set('account', id);
            params.delete('post');
            persistSubview('accounts', params);
        });
    }, [persistSubview, writeParams]);

    const closeAccount = useCallback(() => {
        setActiveAccountId(null);
        setSubview('accounts');
        writeParams((params) => {
            params.delete('account');
            params.delete('post');
            persistSubview('accounts', params);
        });
    }, [persistSubview, writeParams]);

    const handleDeleteAccount = useCallback(
        async (accountId: string) => {
            if (activeAccountId === accountId) {
                setActiveAccountId(null);
                writeParams((params) => {
                    params.delete('account');
                    params.delete('post');
                    persistSubview('accounts', params);
                });
            }
            if (overviewAccountId === accountId) setOverviewAccountId(null);
            const ok = await deleteTrackedAccount(accountId);
            if (ok) reloadAllMetrics();
        },
        [activeAccountId, overviewAccountId, persistSubview, reloadAllMetrics, writeParams],
    );

    const accountAvatar = activeAccount
        ? (profilePicFor(activeAccount.platform, activeAccount.username)
            || activeAccount.avatar_url
            || undefined)
        : undefined;

    // 1) Post detail (may sit on top of an account deep-link)
    if (activePostId) {
        return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <PostDetailView
                    postId={activePostId}
                    onClose={closePost}
                    refreshKey={metricsEpoch}
                />
            </div>
        );
    }

    // 2) Account detail full page
    if (activeAccountId) {
        if (!activeAccount) {
            // Account id in URL but list not loaded / missing — show loading or back.
            if (trackedLoading || (aggregatesEnabled && aggLoading)) {
                return (
                    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>
                        Loading account…
                    </div>
                );
            }
            return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 24 }}>
                    <button
                        type="button"
                        onClick={closeAccount}
                        style={{
                            alignSelf: 'flex-start',
                            padding: '7px 12px',
                            borderRadius: 8,
                            border: '1px solid var(--border)',
                            background: 'white',
                            cursor: 'pointer',
                            fontWeight: 600,
                            fontSize: 13,
                        }}
                    >
                        Back
                    </button>
                    <p style={{ margin: 0, color: 'var(--text-3)', fontSize: 13 }}>
                        Account not found.
                    </p>
                </div>
            );
        }

        return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <AccountDetailView
                    account={activeAccount}
                    onClose={closeAccount}
                    onRefreshed={reloadAllMetrics}
                    onOpenPost={openPost}
                    avatarUrl={accountAvatar}
                />
            </div>
        );
    }

    // 3) Dashboard
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <DashboardView
                period={period}
                onPeriodChange={setPeriod}
                refreshKey={metricsEpoch}
                onAddExternal={() => setAddOpen(true)}
                onOpenPost={openPost}
                onStatsReady={handleStatsReady}
                subview={subview}
                onSubviewChange={handleSubviewChange}
                accounts={displayAccounts}
                accountsLoading={aggregatesEnabled && aggLoading}
                trackedAccountsLoading={trackedLoading}
                onOpenAccount={openAccount}
                onAccountScraped={reloadAllMetrics}
                onDeleteAccount={handleDeleteAccount}
                isStudioAccount={isStudio}
                profilePicFor={profilePicFor}
                ownership={accountOwnership}
                onOwnershipChange={setAccountOwnership}
                overviewAccountId={overviewAccountId}
                onOverviewAccountChange={setOverviewAccountId}
                onRefreshAll={onRefreshAll}
                refreshing={refreshing}
            />

            {addOpen && (
                <AddAccountModal
                    onClose={() => setAddOpen(false)}
                    onAdded={reloadAllMetrics}
                />
            )}
        </div>
    );
}
