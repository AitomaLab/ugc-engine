'use client';

import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import type { AnalyticsPlatform } from '@/lib/types';
import {
    ANALYTICS_CTA_ORANGE,
    ANALYTICS_CTA_ORANGE_HOVER,
    ANALYTICS_PRIMARY,
    buildDailyTrendPoints,
    useAnalyticsStats,
    useMetricsFreshness,
    timeAgo,
    type AccountFilter,
    type AccountOwnership,
    type Period,
    type PlatformFilter,
    type TrackedAccountAggregate,
} from '../analytics-types';
import AccountsView from '../AccountsView';
import DashboardPeriodToggle from './DashboardPeriodToggle';
import KpiCards from './KpiCards';
import CumulativeGrowthChart from './CumulativeGrowthChart';
import PlatformDistributionPanel from './PlatformDistributionPanel';
import ContentTypePanel from './ContentTypePanel';
import VideoPerformanceView from './VideoPerformanceView';
import { ChartSkeleton, KpiCardsSkeleton, PanelSkeleton } from './DashboardLoadingSkeleton';

interface Props {
    period: Period;
    onPeriodChange: (next: Period) => void;
    refreshKey?: number;
    /** Open the Add External Account modal in the parent. */
    onAddExternal: () => void;
    /** Open the post detail page in the parent (drives ?post=<id>). */
    onOpenPost?: (postId: string) => void;
    /** Fired once stats have loaded — parent can defer heavy secondary fetches. */
    onStatsReady?: () => void;
    /** Controlled Overview / By Video / Accounts subview (lifted so detail Back restores it). */
    subview: DashboardSubview;
    onSubviewChange: (subview: DashboardSubview) => void;
    /** Selected account for the Overview subview (per-account metrics). */
    overviewAccountId: string | null;
    onOverviewAccountChange: (accountId: string) => void;
    /** Page-level refresh-all (POST /api/analytics/refresh-all). */
    onRefreshAll?: () => void;
    refreshing?: boolean;

    /* ── Accounts subview wiring ─────────────────────────────────────── */
    /** Aggregated tracked accounts for the Accounts subview. */
    accounts: TrackedAccountAggregate[];
    accountsLoading: boolean;
    /** True while the tracked-accounts list is still loading (gates stats fetch). */
    trackedAccountsLoading: boolean;
    /** Open the account detail page in the parent. */
    onOpenAccount: (accountId: string) => void;
    /** Re-pull dashboard data after a per-card "Analyze Now" succeeds. */
    onAccountScraped: () => void;
    /** Stop tracking an external account. Studio-linked rows skip this. */
    onDeleteAccount: (accountId: string) => void;
    /** Studio classifier — used as the secondary signal when
     *  `linked_via_connections` is missing on the account row. */
    isStudioAccount?: (platform: string, username: string) => boolean;
    /** Resolved profile-photo lookup — backed by /api/connections. */
    profilePicFor?: (platform: string, username: string) => string | undefined;
    /** Ownership filter (All / Studio / External) — owned by the parent so
     *  the list survives subview switches. */
    ownership: AccountOwnership;
    onOwnershipChange: (next: AccountOwnership) => void;
}

type GrowthSeries = 'engagement' | 'views' | 'posts';
export type DashboardSubview = 'overview' | 'videos' | 'accounts';

/**
 * Light-themed analytics dashboard.
 *
 * Composes:
 *   • Title + period toggle
 *   • Subview toggle (Overview / By Video)
 *   • KPI cards (views, engagement rate, total posted)
 *   • Daily trend area chart with series toggle
 *   • Platform + content-type distribution panels (side-by-side)
 *   • CTAs to connect / track external accounts
 *
 * The "By Video" subview groups Studio-published posts by `video_job_id`
 * so the user can see lifetime performance for each uploaded video across
 * every platform it was posted to.
 *
 * All aggregates are driven by `/api/analytics/stats` and
 * `/api/analytics/posts?source=internal`
 * (the last only when the videos subview is active) — no per-component
 * fetching so the period toggle stays in lockstep across widgets.
 */
export default function DashboardView({
    period,
    onPeriodChange,
    refreshKey = 0,
    onAddExternal,
    onOpenPost,
    onStatsReady,
    subview,
    onSubviewChange,
    accounts,
    accountsLoading,
    trackedAccountsLoading,
    onOpenAccount,
    onAccountScraped,
    onDeleteAccount,
    isStudioAccount,
    profilePicFor,
    ownership,
    onOwnershipChange,
    overviewAccountId,
    onOverviewAccountChange,
    onRefreshAll,
    refreshing = false,
}: Props) {
    const { t } = useTranslation();
    const [growthSeries, setGrowthSeries] = useState<GrowthSeries>('engagement');

    const activeTabId = overviewAccountId ?? accounts[0]?.id ?? null;
    const selectedAccount = activeTabId
        ? accounts.find((a) => a.id === activeTabId) ?? null
        : null;

    const accountFilter: AccountFilter = useMemo(() => {
        if (!selectedAccount) return null;
        return {
            platform: selectedAccount.platform as AnalyticsPlatform,
            username: selectedAccount.username,
        };
    }, [selectedAccount?.id, selectedAccount?.platform, selectedAccount?.username]);

    useEffect(() => {
        if (!overviewAccountId && accounts[0]?.id) {
            onOverviewAccountChange(accounts[0].id);
        }
    }, [overviewAccountId, accounts, onOverviewAccountChange]);

    const platformFilter: PlatformFilter = selectedAccount
        ? (selectedAccount.platform as AnalyticsPlatform)
        : 'all';

    const { data: stats, loading: statsLoading, isRefreshing: statsRefreshing } = useAnalyticsStats(
        period,
        platformFilter,
        'all',
        accountFilter,
        refreshKey,
        { enabled: !trackedAccountsLoading },
    );
    const statsReady = Boolean(stats) && !statsLoading;
    const { lastRefreshedAt } = useMetricsFreshness(refreshKey, { enabled: statsReady });

    useEffect(() => {
        if (statsReady) onStatsReady?.();
    }, [statsReady, onStatsReady]);

    const dailyTrendPoints = useMemo(
        () => (stats ? buildDailyTrendPoints(stats, period) : []),
        [stats, period],
    );

    const showKpiSkeleton = statsLoading && !stats;
    const showChartSkeleton = statsLoading && !stats;
    const showPanelSkeleton = statsLoading && !stats;
    const isRefreshing = statsRefreshing || accountsLoading;

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
                gap: 10,
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

            {/* Toolbar — subviews | period (center) | refresh · Add account */}
            <div className="dash-toolbar-nav">
                <div className="dash-toolbar-left">
                    <SubviewToggle subview={subview} onChange={onSubviewChange} />
                </div>
                <div className="dash-toolbar-center">
                    <DashboardPeriodToggle period={period} onChange={onPeriodChange} />
                </div>
                <div className="dash-toolbar-right">
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
                            <svg
                                width="13"
                                height="13"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth={2.2}
                                style={refreshing ? { animation: 'analytics-spin 0.8s linear infinite' } : undefined}
                                aria-hidden
                            >
                                <path d="M21 12a9 9 0 1 1-2.64-6.36" strokeLinecap="round" />
                                <polyline points="21 3 21 9 15 9" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            {refreshing ? t('analytics.refresh.refreshing') : t('analytics.refresh.cta')}
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={onAddExternal}
                        style={{
                            padding: '7px 14px',
                            borderRadius: 8,
                            border: 'none',
                            background: ANALYTICS_CTA_ORANGE,
                            color: 'white',
                            fontSize: 12,
                            fontWeight: 700,
                            cursor: 'pointer',
                            whiteSpace: 'nowrap',
                            transition: 'background 0.15s ease',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = ANALYTICS_CTA_ORANGE_HOVER; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = ANALYTICS_CTA_ORANGE; }}
                    >
                        <AddAccountPlusIcon /> {t('analytics.add.cta')}
                    </button>
                </div>
            </div>

            {subview === 'accounts' ? (
                <AccountsView
                    accounts={accounts}
                    loading={accountsLoading}
                    period={period}
                    onOpenAccount={onOpenAccount}
                    onScraped={onAccountScraped}
                    onOpenAdd={onAddExternal}
                    /* Studio rows are managed under /connections — gate the
                     * trash icon to External-only so users can't accidentally
                     * unlink an OAuth-connected profile from this surface.
                     * The card receives `undefined` for `onDelete` and hides
                     * the affordance entirely. */
                    onDelete={(id) => {
                        const a = accounts.find((row) => row.id === id);
                        const studio = Boolean(a?.linked_via_connections)
                            || (a && isStudioAccount ? isStudioAccount(a.platform, a.username) : false);
                        if (studio) return;
                        onDeleteAccount(id);
                    }}
                    isStudio={isStudioAccount}
                    profilePicFor={profilePicFor}
                    ownership={ownership}
                    setOwnership={onOwnershipChange}
                />
            ) : subview === 'overview' ? (
                <>
                    {accounts.length > 0 && activeTabId && (
                        <OverviewAccountTabs
                            accounts={accounts}
                            selectedId={activeTabId}
                            onSelect={onOverviewAccountChange}
                            canRemove={(acct) => !(
                                Boolean(acct.linked_via_connections)
                                || (isStudioAccount ? isStudioAccount(acct.platform, acct.username) : false)
                            )}
                            onRemove={(acct) => onDeleteAccount(acct.id)}
                        />
                    )}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, position: 'relative' }}>
                        {showKpiSkeleton ? (
                            <KpiCardsSkeleton />
                        ) : (
                            <div style={{ opacity: statsLoading ? 0.65 : 1, transition: 'opacity 0.2s ease' }}>
                                <KpiCards stats={stats} loading={false} />
                            </div>
                        )}

                        {/* Desktop: chart left + distribution panels right.
                            Mobile (<900px): stack via CSS class. */}
                        <div className="dash-overview-grid">
                            <section
                                className="dash-panel"
                                style={{
                                    background: '#FFFFFF',
                                    border: '1px solid var(--border, #E2E8F0)',
                                    borderRadius: 16,
                                    padding: 16,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 12,
                                    boxShadow: '0 1px 2px rgba(15,23,42,0.03)',
                                    minWidth: 0,
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-1, #0F172A)' }}>
                                        {t('analytics.dashboard.growth.title')}
                                    </div>
                                    <div role="tablist" style={{ display: 'inline-flex', borderRadius: 999, background: '#F1F5F9', padding: 3, gap: 2, border: '1px solid #E2E8F0' }}>
                                        {(['engagement', 'views', 'posts'] as GrowthSeries[]).map((s) => {
                                            const active = s === growthSeries;
                                            return (
                                                <button
                                                    key={s}
                                                    type="button"
                                                    role="tab"
                                                    aria-selected={active}
                                                    onClick={() => setGrowthSeries(s)}
                                                    style={{
                                                        padding: '5px 12px',
                                                        borderRadius: 999,
                                                        border: 'none',
                                                        background: active ? ANALYTICS_PRIMARY : 'transparent',
                                                        color: active ? '#FFFFFF' : '#475569',
                                                        fontSize: 11,
                                                        fontWeight: 700,
                                                        cursor: 'pointer',
                                                        textTransform: 'capitalize',
                                                        transition: 'background 0.15s ease, color 0.15s ease',
                                                    }}
                                                >
                                                    {t(`analytics.dashboard.growth.series.${s}`)}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>

                                {showChartSkeleton ? (
                                    <ChartSkeleton height={180} />
                                ) : (
                                    <div style={{ opacity: statsLoading ? 0.65 : 1, transition: 'opacity 0.2s ease' }}>
                                        <CumulativeGrowthChart
                                            points={dailyTrendPoints}
                                            series={growthSeries}
                                            height={180}
                                        />
                                    </div>
                                )}
                            </section>

                            <div className="dash-overview-side">
                                {showPanelSkeleton ? (
                                    <PanelSkeleton />
                                ) : (
                                    <div style={{ opacity: statsLoading ? 0.65 : 1, transition: 'opacity 0.2s ease', display: 'flex', flexDirection: 'column', gap: 12, height: '100%' }}>
                                        <PlatformDistributionPanel
                                            entries={stats?.platform_distribution || []}
                                            loading={false}
                                        />
                                        <ContentTypePanel
                                            entries={stats?.content_type_distribution || []}
                                            loading={false}
                                        />
                                    </div>
                                )}
                            </div>
                        </div>

                        {isRefreshing && !showKpiSkeleton && (
                            <div
                                aria-hidden
                                style={{
                                    position: 'absolute',
                                    top: 8,
                                    right: 8,
                                    width: 18,
                                    height: 18,
                                    borderRadius: '50%',
                                    border: '2px solid rgba(51,122,255,0.25)',
                                    borderTopColor: ANALYTICS_PRIMARY,
                                    animation: 'accountRefreshSpin 0.8s linear infinite',
                                }}
                            />
                        )}
                    </div>
                </>
            ) : subview === 'videos' ? (
                <VideoPerformanceView
                    period={period}
                    refreshKey={refreshKey}
                    onOpenPost={onOpenPost}
                />
            ) : null}

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
                .dash-kpi-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                    gap: 12px;
                }
                .dash-overview-grid {
                    display: grid;
                    grid-template-columns: 1.4fr 1fr;
                    gap: 12px;
                    align-items: stretch;
                }
                .dash-overview-side {
                    display: flex;
                    flex-direction: column;
                    min-width: 0;
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
                    .dash-overview-grid {
                        grid-template-columns: 1fr;
                    }
                }
                .analytics-dashboard ::selection { background: rgba(51,122,255,0.22); color: #0F172A; }
                @keyframes accountRefreshSpin {
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
}

/* ── Per-account tabs on Overview ───────────────────────────────────────── */

function OverviewAccountTabs({
    accounts,
    selectedId,
    onSelect,
    canRemove,
    onRemove,
}: {
    accounts: TrackedAccountAggregate[];
    selectedId: string;
    onSelect: (id: string) => void;
    canRemove?: (acct: TrackedAccountAggregate) => boolean;
    onRemove?: (acct: TrackedAccountAggregate) => void;
}) {
    return (
        <div
            role="tablist"
            aria-label="Tracked accounts"
            style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 6,
                padding: 3,
                borderRadius: 10,
                background: '#F8FAFC',
                border: '1px solid var(--border, #E2E8F0)',
            }}
        >
            {accounts.map((acct) => {
                const active = acct.id === selectedId;
                const removable = Boolean(onRemove && (!canRemove || canRemove(acct)));
                return (
                    <span
                        key={acct.id}
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            borderRadius: 7,
                            border: active ? '1px solid #337AFF' : '1px solid #E2E8F0',
                            background: active ? '#FFFFFF' : 'transparent',
                            boxShadow: active ? '0 1px 2px rgba(51,122,255,0.20)' : 'none',
                            paddingRight: removable ? 2 : 0,
                        }}
                    >
                        <button
                            type="button"
                            role="tab"
                            aria-selected={active}
                            onClick={() => onSelect(acct.id)}
                            style={{
                                padding: '5px 6px 5px 10px',
                                borderRadius: 7,
                                border: 'none',
                                background: 'transparent',
                                color: active ? 'var(--text-1, #0F172A)' : '#475569',
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: 'pointer',
                            }}
                        >
                            @{acct.username}
                            <span style={{ marginLeft: 5, fontSize: 9, fontWeight: 600, opacity: 0.65, textTransform: 'uppercase' }}>
                                {acct.platform}
                            </span>
                        </button>
                        {removable && (
                            <button
                                type="button"
                                aria-label={`Remove @${acct.username}`}
                                title={`Remove @${acct.username}`}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onRemove!(acct);
                                }}
                                style={{
                                    width: 18,
                                    height: 18,
                                    marginLeft: 2,
                                    borderRadius: '50%',
                                    border: 'none',
                                    background: 'transparent',
                                    color: '#94A3B8',
                                    cursor: 'pointer',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    padding: 0,
                                    flexShrink: 0,
                                    transition: 'background 0.15s ease, color 0.15s ease',
                                }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.background = 'rgba(220,38,38,0.12)';
                                    e.currentTarget.style.color = '#DC2626';
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.background = 'transparent';
                                    e.currentTarget.style.color = '#94A3B8';
                                }}
                            >
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round">
                                    <line x1="6" y1="6" x2="18" y2="18" />
                                    <line x1="18" y1="6" x2="6" y2="18" />
                                </svg>
                            </button>
                        )}
                    </span>
                );
            })}
        </div>
    );
}

/* ── Subview toggle (Overview / By Video) ─────────────────────────────── */

function SubviewToggle({
    subview,
    onChange,
}: {
    subview: DashboardSubview;
    onChange: (next: DashboardSubview) => void;
}) {
    const { t } = useTranslation();
    const tabs: Array<{ id: DashboardSubview; label: string; icon: React.ReactNode }> = [
        { id: 'overview', label: t('analytics.dashboard.subview.overview'), icon: <GridIcon /> },
        { id: 'videos',   label: t('analytics.dashboard.subview.videos'),   icon: <PlayIcon /> },
        { id: 'accounts', label: t('analytics.dashboard.subview.accounts'), icon: <UsersIcon /> },
    ];

    return (
        <div
            role="tablist"
            aria-label="Dashboard view"
            style={{
                display: 'inline-flex',
                gap: 4,
                padding: 4,
                borderRadius: 12,
                background: '#F1F5F9',
                border: '1px solid #E2E8F0',
                alignSelf: 'flex-start',
            }}
        >
            {tabs.map((tab) => {
                const active = tab.id === subview;
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
                            gap: 8,
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

function UsersIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
    );
}

function AddAccountPlusIcon() {
    return (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
    );
}
