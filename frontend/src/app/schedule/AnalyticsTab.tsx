'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslation } from '@/lib/i18n';
import AccountScopeBar from '@/components/analytics/AccountScopeBar';
import AccountScopeView, {
    useAccountBackgroundRefresh,
    type AnalyticsViewKey,
} from '@/components/analytics/account/AccountScopeView';
import LearningsView from '@/components/analytics/account/LearningsView';
import AddAccountModal from '@/components/analytics/AddAccountModal';
import DashboardView from '@/components/analytics/dashboard/DashboardView';
import DashboardPeriodToggle from '@/components/analytics/dashboard/DashboardPeriodToggle';
import VideoPerformanceView from '@/components/analytics/dashboard/VideoPerformanceView';
import PostDetailView from '@/components/analytics/PostDetailModal';
import StrategyHub from '@/components/analytics/StrategyHub';
import {
    ANALYTICS_PRIMARY,
    ANALYTICS_STUDIO_SYNCED_EVENT,
    DEFAULT_ANALYTICS_PERIOD,
    deleteTrackedAccount,
    timeAgo,
    trackedAccountToAggregateStub,
    useAccountAggregates,
    useConnections,
    useMetricsFreshness,
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

/** Legacy `?view=accounts` maps to the All-scope overview (comparison lives there). */
function parseView(raw: string | null): AnalyticsViewKey {
    if (raw === 'videos' || raw === 'strategy' || raw === 'learnings') return raw;
    return 'overview';
}

/**
 * Analytics — one surface scoped by the persistent account scope bar
 * ("All accounts" or a single connected/tracked account). Every view tab
 * (Overview / Videos / AI Strategy / AI Learnings) follows the scope, so
 * global blends and per-account drilldowns are the same page instead of
 * separate navigations.
 *
 * URL: `?account=<id>` (absent ⇒ All) · `?view=videos|strategy|learnings`
 * (absent ⇒ overview) · `?post=<id>` renders the full-page post detail on
 * top; Back restores scope + view.
 */
export default function AnalyticsTab({ onRefreshAll, refreshing = false }: Props) {
    const { t } = useTranslation();
    const router = useRouter();
    const search = useSearchParams();

    const [period, setPeriod] = useState<Period>(DEFAULT_ANALYTICS_PERIOD);

    const initialAccountId = search.get('account');
    const [activePostId, setActivePostId] = useState<string | null>(search.get('post'));
    const [scope, setScope] = useState<string>(initialAccountId ?? 'all');
    const [view, setView] = useState<AnalyticsViewKey>(() => parseView(search.get('view')));
    const [addOpen, setAddOpen] = useState(false);
    const [metricsEpoch, setMetricsEpoch] = useState(0);
    const [accountOwnership, setAccountOwnership] = useState<AccountOwnership>('all');
    const [statsReady, setStatsReady] = useState(false);
    const [aggregatesEnabled, setAggregatesEnabled] = useState(() => Boolean(initialAccountId));

    const writeParams = useCallback((mutate: (params: URLSearchParams) => void) => {
        const params = new URLSearchParams(Array.from(search.entries()));
        mutate(params);
        const qs = params.toString();
        router.replace(qs ? `?${qs}` : '?', { scroll: false });
    }, [router, search]);

    const persistView = useCallback((next: AnalyticsViewKey, params: URLSearchParams) => {
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
    const aggregateAccounts = useMemo(() => aggData?.accounts ?? [], [aggData]);
    const displayAccounts: TrackedAccountAggregate[] = useMemo(() => {
        if (aggregateAccounts.length > 0) return aggregateAccounts;
        return trackedRaw.map(trackedAccountToAggregateStub);
    }, [aggregateAccounts, trackedRaw]);

    const { isStudio, profilePicFor, reload: reloadConnections } = useConnections();

    const { lastRefreshedAt } = useMetricsFreshness(metricsEpoch, { enabled: statsReady });

    const reloadAllMetrics = useCallback(() => {
        setAggregatesEnabled(true);
        reloadConnections();
        reloadAccounts();
        reloadAggregates();
        bumpMetrics();
    }, [reloadConnections, reloadAccounts, reloadAggregates, bumpMetrics]);

    const handleStatsReady = useCallback(() => {
        setStatsReady(true);
        setAggregatesEnabled(true);
    }, []);

    useEffect(() => {
        const onSynced = () => {
            reloadAllMetrics();
        };
        window.addEventListener(ANALYTICS_STUDIO_SYNCED_EVENT, onSynced);
        return () => {
            window.removeEventListener(ANALYTICS_STUDIO_SYNCED_EVENT, onSynced);
        };
    }, [reloadAllMetrics]);

    // Scoped account needs aggregates to resolve its row.
    useEffect(() => {
        if (scope !== 'all') setAggregatesEnabled(true);
    }, [scope]);

    // Sync URL → state for post, scope, and view.
    useEffect(() => {
        const nextPost = search.get('post');
        const nextScope = search.get('account') ?? 'all';
        const nextView = parseView(search.get('view'));
        if (nextPost !== activePostId) setActivePostId(nextPost);
        if (nextScope !== scope) setScope(nextScope);
        if (nextView !== view) setView(nextView);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [search]);

    const activeAccount = scope !== 'all'
        ? displayAccounts.find((a) => a.id === scope) || null
        : null;

    const activeAccountIsStudio = activeAccount
        ? (Boolean(activeAccount.linked_via_connections)
            || isStudio(activeAccount.platform, activeAccount.username))
        : false;

    // Per-account scrape refresh — surfaces in the toolbar when scoped, so
    // the page has exactly one refresh affordance per scope.
    const accountRefresh = useAccountBackgroundRefresh(activeAccount, reloadAllMetrics);

    // AI Learnings is user-level — hidden for external (competitor) accounts.
    const learningsAvailable = scope === 'all' || activeAccountIsStudio;

    useEffect(() => {
        if (!learningsAvailable && view === 'learnings') {
            setView('overview');
            writeParams((params) => {
                persistView('overview', params);
            });
        }
    }, [learningsAvailable, view, persistView, writeParams]);

    // Scoped account vanished (deleted / bad deep link) after lists loaded → All.
    const accountsResolved = !trackedLoading && (!aggregatesEnabled || !aggLoading);
    useEffect(() => {
        if (scope !== 'all' && !activeAccount && accountsResolved) {
            setScope('all');
            writeParams((params) => {
                params.delete('account');
            });
        }
    }, [scope, activeAccount, accountsResolved, writeParams]);

    const closePost = useCallback(() => {
        setActivePostId(null);
        writeParams((params) => {
            params.delete('post');
        });
    }, [writeParams]);

    const openPost = useCallback((postId: string) => {
        // Scope + view stay in the URL so Back returns exactly here.
        setActivePostId(postId);
        writeParams((params) => {
            params.set('post', postId);
        });
    }, [writeParams]);

    const handleScopeChange = useCallback((next: string) => {
        setScope(next);
        if (next !== 'all') setAggregatesEnabled(true);
        writeParams((params) => {
            if (next === 'all') params.delete('account');
            else params.set('account', next);
            params.delete('post');
        });
    }, [writeParams]);

    const handleViewChange = useCallback((next: AnalyticsViewKey) => {
        setView(next);
        writeParams((params) => {
            persistView(next, params);
        });
    }, [persistView, writeParams]);

    const openAccountStrategy = useCallback((accountId: string) => {
        setScope(accountId);
        setView('strategy');
        setAggregatesEnabled(true);
        writeParams((params) => {
            params.set('account', accountId);
            persistView('strategy', params);
            params.delete('post');
        });
    }, [persistView, writeParams]);

    const handleDeleteAccount = useCallback(
        async (accountId: string) => {
            if (scope === accountId) {
                setScope('all');
                writeParams((params) => {
                    params.delete('account');
                    params.delete('post');
                });
            }
            const ok = await deleteTrackedAccount(accountId);
            if (ok) reloadAllMetrics();
        },
        [scope, reloadAllMetrics, writeParams],
    );

    // 1) Full-page post detail (scope + view kept in URL for Back)
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

    return (
        <div
            className="analytics-dashboard"
            style={{
                background: 'linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%)',
                borderRadius: 20,
                padding: 'clamp(12px, 2.5vw, 18px)',
                color: 'var(--text-1, #0F172A)',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
                border: '1px solid var(--border, #E2E8F0)',
                boxShadow: '0 1px 3px rgba(15,23,42,0.04), 0 8px 24px rgba(15,23,42,0.04)',
                position: 'relative',
                overflow: 'hidden',
            }}
        >
            <div
                aria-hidden
                style={{
                    position: 'absolute',
                    top: -120,
                    right: -120,
                    width: 320,
                    height: 320,
                    borderRadius: '50%',
                    background: 'radial-gradient(circle, rgba(51,122,255,0.10) 0%, rgba(51,122,255,0) 70%)',
                    pointerEvents: 'none',
                }}
            />

            {/* Persistent account scope — the surface's core control. */}
            <AccountScopeBar
                accounts={displayAccounts}
                scope={scope}
                onScopeChange={handleScopeChange}
                profilePicFor={profilePicFor}
                isStudioAccount={isStudio}
                onAddAccount={() => setAddOpen(true)}
            />

            {/* Toolbar — view tabs | period (center) | freshness · refresh */}
            <div className="dash-toolbar-nav">
                <div className="dash-toolbar-left">
                    <ViewTabs
                        view={view}
                        onChange={handleViewChange}
                        showLearnings={learningsAvailable}
                    />
                </div>
                <div className="dash-toolbar-center">
                    <DashboardPeriodToggle period={period} onChange={setPeriod} />
                </div>
                <div className="dash-toolbar-right">
                    {scope === 'all' ? (
                        <>
                            {lastRefreshedAt && (
                                <span style={{ fontSize: 12, color: 'var(--text-3, #64748B)', whiteSpace: 'nowrap' }}>
                                    {t('analytics.refresh.asOf').replace('{when}', timeAgo(lastRefreshedAt))}
                                </span>
                            )}
                            {onRefreshAll && (
                                <button
                                    type="button"
                                    onClick={onRefreshAll}
                                    disabled={refreshing}
                                    style={{
                                        padding: '7px 12px',
                                        borderRadius: 8,
                                        border: '1px solid var(--border, #E2E8F0)',
                                        background: refreshing ? ANALYTICS_PRIMARY : 'white',
                                        color: refreshing ? 'white' : 'var(--text-1, #0F172A)',
                                        fontSize: 12,
                                        fontWeight: 600,
                                        cursor: refreshing ? 'wait' : 'pointer',
                                        whiteSpace: 'nowrap',
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: 6,
                                    }}
                                >
                                    <RefreshIcon spinning={refreshing} />
                                    {refreshing ? t('analytics.refresh.refreshing') : t('analytics.refresh.cta')}
                                </button>
                            )}
                        </>
                    ) : (
                        <>
                            <span style={{ fontSize: 12, color: 'var(--text-3, #64748B)', whiteSpace: 'nowrap' }}>
                                {accountRefresh.statusLabel}
                            </span>
                            <button
                                type="button"
                                onClick={() => accountRefresh.refresh()}
                                disabled={accountRefresh.isRefreshing}
                                style={{
                                    padding: '7px 12px',
                                    borderRadius: 8,
                                    border: '1px solid var(--border, #E2E8F0)',
                                    background: accountRefresh.isRefreshing ? ANALYTICS_PRIMARY : 'white',
                                    color: accountRefresh.isRefreshing ? 'white' : 'var(--text-1, #0F172A)',
                                    fontSize: 12,
                                    fontWeight: 600,
                                    cursor: accountRefresh.isRefreshing ? 'wait' : 'pointer',
                                    whiteSpace: 'nowrap',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 6,
                                }}
                            >
                                <RefreshIcon spinning={accountRefresh.isRefreshing} />
                                {accountRefresh.isRefreshing
                                    ? t('analytics.accounts.analyzing')
                                    : t('analytics.tracked.refresh')}
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* ── Scoped body ─────────────────────────────────────────── */}
            {scope === 'all' ? (
                view === 'overview' ? (
                    <DashboardView
                        period={period}
                        refreshKey={metricsEpoch}
                        onStatsReady={handleStatsReady}
                        trackedAccountsLoading={trackedLoading}
                        accounts={displayAccounts}
                        accountsLoading={aggregatesEnabled && aggLoading}
                        onSelectAccount={(id) => handleScopeChange(id)}
                        onAccountScraped={reloadAllMetrics}
                        onDeleteAccount={handleDeleteAccount}
                        isStudioAccount={isStudio}
                        profilePicFor={profilePicFor}
                        ownership={accountOwnership}
                        onOwnershipChange={setAccountOwnership}
                        onOpenAdd={() => setAddOpen(true)}
                    />
                ) : view === 'videos' ? (
                    <VideoPerformanceView
                        period={period}
                        refreshKey={metricsEpoch}
                        onOpenPost={openPost}
                    />
                ) : view === 'strategy' ? (
                    <StrategyHub
                        accounts={displayAccounts}
                        profilePicFor={profilePicFor}
                        isStudioAccount={isStudio}
                        onOpenStrategy={openAccountStrategy}
                        refreshKey={metricsEpoch}
                        onOpenAdd={() => setAddOpen(true)}
                    />
                ) : (
                    <LearningsView refreshKey={metricsEpoch} />
                )
            ) : activeAccount ? (
                <AccountScopeView
                    account={activeAccount}
                    view={view}
                    isStudio={activeAccountIsStudio}
                    refreshKey={metricsEpoch + accountRefresh.epoch}
                    isRefreshing={accountRefresh.isRefreshing}
                    onOpenPost={openPost}
                    onSwitchView={handleViewChange}
                />
            ) : (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>
                    Loading account…
                </div>
            )}

            {addOpen && (
                <AddAccountModal
                    onClose={() => setAddOpen(false)}
                    onAdded={reloadAllMetrics}
                />
            )}

            <style>{`
                .dash-toolbar-nav {
                    display: grid;
                    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
                    align-items: center;
                    gap: 12px;
                    position: relative;
                }
                .dash-toolbar-left {
                    justify-self: start;
                    min-width: 0;
                }
                .dash-toolbar-center {
                    justify-self: center;
                }
                .dash-toolbar-right {
                    justify-self: end;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    flex-wrap: wrap;
                    justify-content: flex-end;
                }
                @media (max-width: 900px) {
                    .dash-toolbar-nav {
                        grid-template-columns: 1fr;
                        gap: 10px;
                    }
                    .dash-toolbar-left,
                    .dash-toolbar-center,
                    .dash-toolbar-right {
                        justify-self: stretch;
                    }
                    .dash-toolbar-center {
                        display: flex;
                        justify-content: center;
                    }
                    .dash-toolbar-right {
                        justify-content: space-between;
                    }
                }
                .analytics-dashboard ::selection { background: rgba(51,122,255,0.22); color: #0F172A; }
                @keyframes analytics-spin { to { transform: rotate(360deg); } }
            `}</style>
        </div>
    );
}

/* ── Toolbar view tabs (Overview / Videos / AI Strategy / AI Learnings) ── */

function ViewTabs({
    view,
    onChange,
    showLearnings,
}: {
    view: AnalyticsViewKey;
    onChange: (next: AnalyticsViewKey) => void;
    showLearnings: boolean;
}) {
    const { t } = useTranslation();
    const tabs: Array<{ id: AnalyticsViewKey; label: string; icon: React.ReactNode }> = [
        { id: 'overview', label: t('analytics.dashboard.subview.overview'), icon: <GridIcon /> },
        { id: 'videos',   label: t('analytics.dashboard.subview.videos'),   icon: <PlayIcon /> },
        { id: 'strategy', label: t('analytics.accounts.tabs.strategy'),     icon: <AiSparkIcon /> },
        ...(showLearnings
            ? [{ id: 'learnings' as const, label: t('analytics.accounts.tabs.learnings'), icon: <LightbulbIcon /> }]
            : []),
    ];

    return (
        <div
            role="tablist"
            aria-label="Analytics view"
            style={{
                display: 'inline-flex',
                gap: 4,
                padding: 4,
                borderRadius: 12,
                background: '#F1F5F9',
                border: '1px solid #E2E8F0',
                alignSelf: 'flex-start',
                flexWrap: 'wrap',
            }}
        >
            {tabs.map((tab) => {
                const active = tab.id === view;
                return (
                    <button
                        key={tab.id}
                        type="button"
                        role="tab"
                        aria-selected={active}
                        onClick={() => onChange(tab.id)}
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 7,
                            padding: '6px 12px',
                            borderRadius: 8,
                            border: 'none',
                            background: active ? '#337AFF' : 'transparent',
                            color: active ? '#FFFFFF' : '#475569',
                            fontSize: 12,
                            fontWeight: 700,
                            cursor: 'pointer',
                            transition: 'background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease',
                            boxShadow: active ? '0 1px 2px rgba(51,122,255,0.30)' : 'none',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        <span style={{ color: active ? '#FFFFFF' : '#94A3B8', display: 'inline-flex' }}>{tab.icon}</span>
                        {tab.label}
                    </button>
                );
            })}
        </div>
    );
}

function RefreshIcon({ spinning }: { spinning?: boolean }) {
    return (
        <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.2}
            style={spinning ? { animation: 'analytics-spin 0.8s linear infinite' } : undefined}
            aria-hidden
        >
            <path d="M21 12a9 9 0 1 1-2.64-6.36" strokeLinecap="round" />
            <polyline points="21 3 21 9 15 9" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}

function GridIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
            <rect x="3" y="3" width="7" height="7" rx="1.5" />
            <rect x="14" y="3" width="7" height="7" rx="1.5" />
            <rect x="3" y="14" width="7" height="7" rx="1.5" />
            <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
    );
}

function PlayIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinejoin="round">
            <polygon points="6 4 20 12 6 20 6 4" />
        </svg>
    );
}

/** The AI star used across the product to denote AI-generated analysis. */
function AiSparkIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z" />
            <path d="M18.2 15.4l.7 1.9 1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7z" />
        </svg>
    );
}

function LightbulbIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.1} strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 18h6" />
            <path d="M10 21.5h4" />
            <path d="M15.1 14c.18-.98.65-1.74 1.4-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1.22.5 2.54 1.5 3.5.75.76 1.22 1.52 1.4 2.5" />
        </svg>
    );
}
