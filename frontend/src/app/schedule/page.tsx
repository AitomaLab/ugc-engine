'use client';

import { useCallback, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import AnalyticsTabs, { type PublishTabKey } from '@/components/analytics/AnalyticsTabs';
import {
    analyticsFetch,
    ANALYTICS_PRIMARY,
    ANALYTICS_STUDIO_SYNCED_EVENT,
    pollRefreshStatus,
} from '@/components/analytics/analytics-types';
import CalendarTab from './CalendarTab';
import AnalyticsTab from './AnalyticsTab';

export default function SchedulePage() {
    const { t } = useTranslation();
    const [tab, setTab] = useState<PublishTabKey>('calendar');
    const [refreshing, setRefreshing] = useState(false);

    // Global "Refresh data" affordance lives on the page title row so it
    // reclaims the empty space opposite the title. It reuses the existing
    // `analyticsStudioSynced` event contract to tell the mounted AnalyticsTab
    // to reload its metrics — no analytics data hooks are duplicated here.
    const handleRefreshAll = useCallback(async () => {
        if (refreshing) return;
        setRefreshing(true);
        try {
            await analyticsFetch('/api/analytics/refresh-all', {
                method: 'POST',
                skipProjectScope: true,
            });
            await pollRefreshStatus();
            if (typeof window !== 'undefined') {
                window.dispatchEvent(new CustomEvent(ANALYTICS_STUDIO_SYNCED_EVENT));
            }
        } catch {
            /* Keep cached data visible on failure. */
        } finally {
            setRefreshing(false);
        }
    }, [refreshing]);

    return (
        <div className="content-area">
            <header
                style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    gap: '16px',
                    flexWrap: 'wrap',
                    marginBottom: '20px',
                }}
            >
                <div>
                    <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700 }}>{t('publish.title')}</h1>
                    <p style={{ margin: '4px 0 0', color: 'var(--text-3)', fontSize: '14px' }}>
                        {t('publish.subtitle')}
                    </p>
                </div>

                {tab === 'analytics' && (
                    <button
                        type="button"
                        onClick={handleRefreshAll}
                        disabled={refreshing}
                        style={{
                            padding: '8px 14px',
                            borderRadius: '8px',
                            border: '1px solid var(--border)',
                            background: refreshing ? ANALYTICS_PRIMARY : 'white',
                            color: refreshing ? 'white' : 'var(--text-1)',
                            fontSize: '13px',
                            fontWeight: 600,
                            cursor: refreshing ? 'wait' : 'pointer',
                            whiteSpace: 'nowrap',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            transition: 'background 0.15s ease, color 0.15s ease, border-color 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                            if (refreshing) return;
                            e.currentTarget.style.background = ANALYTICS_PRIMARY;
                            e.currentTarget.style.color = 'white';
                            e.currentTarget.style.borderColor = ANALYTICS_PRIMARY;
                        }}
                        onMouseLeave={(e) => {
                            if (refreshing) return;
                            e.currentTarget.style.background = 'white';
                            e.currentTarget.style.color = 'var(--text-1)';
                            e.currentTarget.style.borderColor = 'var(--border)';
                        }}
                    >
                        <RefreshIcon spinning={refreshing} />
                        {refreshing ? t('analytics.refresh.refreshing') : t('analytics.refresh.cta')}
                    </button>
                )}
            </header>

            <AnalyticsTabs value={tab} onChange={setTab} />

            <div style={{ marginTop: '20px' }}>
                {tab === 'calendar' ? <CalendarTab /> : <AnalyticsTab />}
            </div>

            {/* Keyframes for the refresh spinner — scoped style tag so the
                animation is available without touching globals. */}
            <style>{`@keyframes analytics-spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    );
}

function RefreshIcon({ spinning }: { spinning?: boolean }) {
    return (
        <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.2}
            strokeLinecap="round"
            strokeLinejoin="round"
            style={spinning ? { animation: 'analytics-spin 0.9s linear infinite' } : undefined}
        >
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
        </svg>
    );
}
