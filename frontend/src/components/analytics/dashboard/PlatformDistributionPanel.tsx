'use client';

import { useMemo } from 'react';
import { useTranslation } from '@/lib/i18n';
import { formatCount, type DistributionEntry } from '../analytics-types';

interface Props {
    entries: DistributionEntry[];
    loading?: boolean;
}

const PLATFORM_COLORS: Record<string, string> = {
    instagram: '#E1306C',
    tiktok: '#0EA5E9',
    youtube: '#EF4444',
    facebook: '#2563EB',
    unknown: '#94A3B8',
};

/**
 * Donut + legend showing how views distribute across platforms.
 *
 * The donut renders zero-state copy when there's no data instead of a hollow
 * ring — empty rings look broken and we'd rather hint the user that
 * connecting accounts is the prerequisite.
 */
export default function PlatformDistributionPanel({ entries, loading }: Props) {
    const { t } = useTranslation();

    const { total, slices, viewBox, radius, stroke } = useMemo(() => {
        const t = entries.reduce((acc, e) => acc + e.value, 0);
        const r = 80;
        const w = 220;
        const sw = 28;
        if (t === 0) return { total: 0, slices: [], viewBox: w, radius: r, stroke: sw };
        let cumulative = 0;
        const circumference = 2 * Math.PI * r;
        const sl = entries.map((e) => {
            const fraction = e.value / t;
            const dash = fraction * circumference;
            const slice = {
                key: e.key,
                value: e.value,
                fraction,
                color: PLATFORM_COLORS[e.key.toLowerCase()] || '#94A3B8',
                dasharray: `${dash} ${circumference - dash}`,
                offset: -cumulative * circumference,
            };
            cumulative += fraction;
            return slice;
        });
        return { total: t, slices: sl, viewBox: w, radius: r, stroke: sw };
    }, [entries]);

    return (
        <div
            className="dash-panel"
            style={{
                background: '#FFFFFF',
                border: '1px solid #E2E8F0',
                borderRadius: '18px',
                padding: '22px',
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
                flex: 1,
                height: '100%',
                opacity: loading ? 0.7 : 1,
                boxShadow: '0 1px 2px rgba(15,23,42,0.03)',
            }}
        >
            <div style={{ fontSize: 18, fontWeight: 700, color: '#0F172A' }}>
                {t('analytics.dashboard.distribution.platformTitle')}
            </div>

            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
                <div style={{ position: 'relative', width: viewBox, height: viewBox, flexShrink: 0 }}>
                    <svg viewBox={`0 0 ${viewBox} ${viewBox}`} width={viewBox} height={viewBox}>
                        {/* Background ring — light gray track */}
                        <circle
                            cx={viewBox / 2}
                            cy={viewBox / 2}
                            r={radius}
                            fill="none"
                            stroke="#F1F5F9"
                            strokeWidth={stroke}
                        />
                        {slices.map((s) => (
                            <circle
                                key={s.key}
                                cx={viewBox / 2}
                                cy={viewBox / 2}
                                r={radius}
                                fill="none"
                                stroke={s.color}
                                strokeWidth={stroke}
                                strokeDasharray={s.dasharray}
                                strokeDashoffset={s.offset}
                                transform={`rotate(-90 ${viewBox / 2} ${viewBox / 2})`}
                                strokeLinecap="butt"
                            />
                        ))}
                    </svg>
                    <div
                        style={{
                            position: 'absolute',
                            inset: 0,
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#0F172A',
                        }}
                    >
                        <div style={{ fontSize: 11, color: '#94A3B8' }}>{t('analytics.dashboard.kpi.totalViews')}</div>
                        <div style={{ fontSize: 22, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                            {formatCount(total)}
                        </div>
                    </div>
                </div>

                <div style={{ flex: 1, minWidth: 140, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {entries.length === 0 ? (
                        <div style={{ fontSize: 12, color: '#94A3B8', lineHeight: 1.5 }}>
                            {t('analytics.dashboard.distribution.empty')}
                        </div>
                    ) : (
                        entries.map((e) => {
                            const pct = total ? (e.value / total) * 100 : 0;
                            return (
                                <div key={e.key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <span
                                        aria-hidden
                                        style={{
                                            width: 10,
                                            height: 10,
                                            borderRadius: 3,
                                            background: PLATFORM_COLORS[e.key.toLowerCase()] || '#94A3B8',
                                        }}
                                    />
                                    <span style={{ flex: 1, fontSize: 13, color: '#0F172A', textTransform: 'capitalize' }}>
                                        {e.key}
                                    </span>
                                    <span style={{ fontSize: 13, fontWeight: 600, color: '#475569', fontVariantNumeric: 'tabular-nums' }}>
                                        {pct.toFixed(0)}%
                                    </span>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>
        </div>
    );
}
