'use client';

import { useTranslation } from '@/lib/i18n';
import {
    formatCount,
    useAnalyticsStats,
    type AccountFilter,
    type Period,
    type PlatformFilter,
    type SourceFilter,
} from './analytics-types';

interface Props {
    period: Period;
    onPeriodChange: (next: Period) => void;
    platform: PlatformFilter;
    source: SourceFilter;
    account?: AccountFilter;
    refreshKey?: number;
}

const PERIODS: Period[] = ['7d', '30d', '90d', 'all'];

function Card({
    label,
    value,
    accent,
    icon,
    suffix,
}: {
    label: string;
    value: string;
    accent: string;
    icon: React.ReactNode;
    suffix?: string;
}) {
    return (
        <div
            style={{
                background: 'white',
                borderRadius: 'var(--radius)',
                padding: '18px 20px',
                border: '1px solid var(--border)',
                display: 'flex',
                alignItems: 'center',
                gap: '14px',
                minWidth: 0,
            }}
        >
            <div
                style={{
                    width: 42, height: 42, borderRadius: '12px',
                    background: `${accent}14`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    color: accent,
                }}
            >
                {icon}
            </div>
            <div style={{ minWidth: 0 }}>
                <div
                    style={{
                        fontSize: '24px', fontWeight: 700, color: 'var(--text-1)', lineHeight: 1.1,
                        display: 'flex', alignItems: 'baseline', gap: '4px',
                    }}
                >
                    <span>{value}</span>
                    {suffix && <span style={{ fontSize: '14px', color: 'var(--text-3)', fontWeight: 600 }}>{suffix}</span>}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 500, marginTop: '2px' }}>
                    {label}
                </div>
            </div>
        </div>
    );
}

export default function AnalyticsKpiStrip({ period, onPeriodChange, platform, source, account, refreshKey = 0 }: Props) {
    const { t } = useTranslation();
    const { data, loading } = useAnalyticsStats(period, platform, source, account, refreshKey);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {PERIODS.map((p) => {
                    const active = p === period;
                    return (
                        <button
                            key={p}
                            onClick={() => onPeriodChange(p)}
                            style={{
                                padding: '6px 14px',
                                borderRadius: '999px',
                                border: '1px solid var(--border)',
                                background: active ? 'var(--blue)' : 'white',
                                color: active ? 'white' : 'var(--text-2)',
                                fontSize: '12px',
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                            }}
                        >
                            {t(`analytics.filters.period.${p}`)}
                        </button>
                    );
                })}
            </div>

            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
                    gap: '16px',
                    opacity: loading ? 0.6 : 1,
                    transition: 'opacity 0.15s ease',
                }}
            >
                <Card
                    label={t('analytics.kpis.views')}
                    value={formatCount(data?.total_views ?? 0)}
                    accent="var(--blue)"
                    icon={
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                            <circle cx="12" cy="12" r="3" />
                        </svg>
                    }
                />
                <Card
                    label={t('analytics.kpis.engagement')}
                    value={formatCount(data?.total_engagement ?? 0)}
                    accent="#34C759"
                    icon={
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 1 0-7.78 7.78L12 21l8.84-8.84a5.5 5.5 0 0 0 0-7.78z" />
                        </svg>
                    }
                />
                <Card
                    label={t('analytics.kpis.engagementRate')}
                    value={String(data?.avg_engagement_rate ?? 0)}
                    suffix="%"
                    accent="#FF9F0A"
                    icon={
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth={2}>
                            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                        </svg>
                    }
                />
                <Card
                    label={t('analytics.kpis.posts')}
                    value={formatCount(data?.posts_tracked ?? 0)}
                    accent="#5E5CE6"
                    icon={
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth={2}>
                            <rect x="3" y="3" width="18" height="18" rx="2" />
                            <line x1="3" y1="9" x2="21" y2="9" />
                            <line x1="9" y1="21" x2="9" y2="9" />
                        </svg>
                    }
                />
            </div>
        </div>
    );
}
