'use client';

import { Suspense, useCallback, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import AnalyticsTabs, { type PublishTabKey } from '@/components/analytics/AnalyticsTabs';
import {
    analyticsFetch,
    ANALYTICS_STUDIO_SYNCED_EVENT,
    pollRefreshStatus,
} from '@/components/analytics/analytics-types';
import CalendarTab from './CalendarTab';
import AnalyticsTab from './AnalyticsTab';

function SchedulePageInner() {
    const search = useSearchParams();
    // Only the full-page post detail hides the Calendar/Analytics tab bar —
    // account scoping (?account=) is part of the main Analytics surface.
    const viewingDetail = Boolean(search.get('post'));
    const [tab, setTab] = useState<PublishTabKey>(() => (
        search.get('post') || search.get('account') || search.get('view')
            ? 'analytics'
            : 'calendar'
    ));
    const [refreshing, setRefreshing] = useState(false);

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
        <div
            className="content-area"
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'stretch',
                ...(viewingDetail ? { paddingTop: 16, paddingBottom: 24 } : {}),
            }}
        >
            {!viewingDetail && <AnalyticsTabs value={tab} onChange={setTab} />}

            <div style={{ marginTop: viewingDetail ? 0 : 12 }}>
                {tab === 'calendar' && !viewingDetail ? (
                    <CalendarTab />
                ) : (
                    <AnalyticsTab onRefreshAll={handleRefreshAll} refreshing={refreshing} />
                )}
            </div>

            <style>{`@keyframes analytics-spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    );
}

export default function SchedulePage() {
    return (
        <Suspense fallback={null}>
            <SchedulePageInner />
        </Suspense>
    );
}
