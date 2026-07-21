'use client';

import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import {
    ANALYTICS_PRIMARY,
    buildDailyTrendPoints,
    useAnalyticsStats,
    type AccountOwnership,
    type Period,
    type TrackedAccountAggregate,
} from '../analytics-types';
import AccountsView from '../AccountsView';
import KpiCards from './KpiCards';
import CumulativeGrowthChart from './CumulativeGrowthChart';
import PlatformDistributionPanel from './PlatformDistributionPanel';
import ContentTypePanel from './ContentTypePanel';
import { ChartSkeleton, KpiCardsSkeleton, PanelSkeleton } from './DashboardLoadingSkeleton';

interface Props {
    period: Period;
    refreshKey?: number;
    /** Fired once stats have loaded — parent can defer heavy secondary fetches. */
    onStatsReady?: () => void;
    /** True while the tracked-accounts list is still loading (gates stats fetch). */
    trackedAccountsLoading: boolean;

    /* ── Accounts comparison section ─────────────────────────────────── */
    accounts: TrackedAccountAggregate[];
    accountsLoading: boolean;
    /** Row click — scopes the whole surface to that account. */
    onSelectAccount: (accountId: string) => void;
    /** Re-pull dashboard data after a per-card "Analyze Now" succeeds. */
    onAccountScraped: () => void;
    /** Stop tracking an external account. Studio-linked rows skip this. */
    onDeleteAccount: (accountId: string) => void;
    isStudioAccount?: (platform: string, username: string) => boolean;
    profilePicFor?: (platform: string, username: string) => string | undefined;
    ownership: AccountOwnership;
    onOwnershipChange: (next: AccountOwnership) => void;
    onOpenAdd: () => void;
}

type GrowthSeries = 'engagement' | 'views' | 'posts';

/**
 * All-accounts Overview body — blended KPIs, growth chart, platform +
 * content-type distribution, and the per-account comparison section
 * (which absorbed the old "Accounts" tab; clicking a row re-scopes the
 * surface to that account via the parent's scope bar).
 *
 * Scope switching, view tabs, period, and refresh live in the parent
 * (`AnalyticsTab`) toolbar — this component is content only.
 */
export default function DashboardView({
    period,
    refreshKey = 0,
    onStatsReady,
    trackedAccountsLoading,
    accounts,
    accountsLoading,
    onSelectAccount,
    onAccountScraped,
    onDeleteAccount,
    isStudioAccount,
    profilePicFor,
    ownership,
    onOwnershipChange,
    onOpenAdd,
}: Props) {
    const { t } = useTranslation();
    const [growthSeries, setGrowthSeries] = useState<GrowthSeries>('engagement');

    // null account filter → all-accounts blend from /api/analytics/stats.
    const { data: stats, loading: statsLoading, isRefreshing: statsRefreshing } = useAnalyticsStats(
        period,
        'all',
        'all',
        null,
        refreshKey,
        { enabled: !trackedAccountsLoading },
    );
    const statsReady = Boolean(stats) && !statsLoading;

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

            {/* Per-account comparison — row click scopes the surface. */}
            <AccountsView
                accounts={accounts}
                loading={accountsLoading}
                period={period}
                onOpenAccount={onSelectAccount}
                onScraped={onAccountScraped}
                onOpenAdd={onOpenAdd}
                /* Studio rows are managed under /connections — gate the
                 * trash icon to External-only so users can't accidentally
                 * unlink an OAuth-connected profile from this surface. */
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

            <style>{`
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
                    .dash-overview-grid {
                        grid-template-columns: 1fr;
                    }
                }
                @keyframes accountRefreshSpin {
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
}
