'use client';

import { useTranslation } from '@/lib/i18n';
import { formatCount, type AnalyticsStats } from '../analytics-types';
import Sparkline from './Sparkline';

interface Props {
    stats: AnalyticsStats | null;
    loading?: boolean;
}

/**
 * Top-row KPI cards on the light-themed dashboard.
 *
 *   • Total Views         — large numeric + sparkline + delta pill
 *   • Engagement Rate     — large % + horizontal progress bar (capped 100)
 *   • Total Posted        — large numeric + decorative chevron pattern
 *
 * All cards live on a white background with a subtle border and the green
 * accent (brand blue #337AFF) reserved for the icons / value highlights so
 * it pops against the lighter surface. Up/down deltas keep their own
 * green/red semantic scale.
 */
export default function KpiCards({ stats, loading }: Props) {
    const { t } = useTranslation();
    if (loading || !stats) {
        return null;
    }
    const data = stats;

    const enRatePct = Math.min(100, Math.max(0, data.avg_engagement_rate));
    const hasPosts = (data.posts_total ?? data.posts_tracked) > 0;
    const showPostsTotal = (data.posts_total ?? 0) > data.posts_tracked;

    return (
        <div className="dash-kpi-grid">
            <DashCard>
                <CardLabel icon={<EyeIcon />}>{t('analytics.dashboard.kpi.totalViews')}</CardLabel>
                <CardValue>{formatCount(data.total_views)}</CardValue>
                <DeltaPill delta={data.views_delta_pct} />
                <CardSpark values={data.daily_views} />
            </DashCard>

            <DashCard>
                <CardLabel icon={<HeartIcon />}>{t('analytics.dashboard.kpi.engagementRate')}</CardLabel>
                <CardValue>
                    {hasPosts ? (
                        <>
                            {enRatePct.toFixed(1)}
                            <span style={{ fontSize: 24, color: '#94A3B8', marginLeft: 4 }}>%</span>
                        </>
                    ) : (
                        <span style={{ fontSize: 28, color: '#94A3B8' }}>—</span>
                    )}
                </CardValue>
                <DeltaPill delta={data.engagement_delta_pct} />
                <CardSpark values={data.daily_engagement} />
            </DashCard>

            <DashCard accent>
                <CardLabel icon={<StackIcon />}>{t('analytics.dashboard.kpi.totalPosted')}</CardLabel>
                <CardValue>{formatCount(data.posts_tracked)}</CardValue>
                {showPostsTotal && (
                    <div style={{ marginTop: 4, fontSize: 11, fontWeight: 600, color: '#64748B' }}>
                        {formatCount(data.posts_total)} total in library
                    </div>
                )}
                <DeltaPill delta={data.posts_delta_pct} />
                <CardSpark values={data.daily_posts} />
            </DashCard>
        </div>
    );
}

/**
 * Uniform bottom for every KPI card: a flat-tolerant sparkline anchored to
 * the bottom edge (`marginTop: auto`) so all three cards share the same
 * footer rhythm regardless of the metric above it.
 */
function CardSpark({ values }: { values: number[] }) {
    return (
        <div style={{ marginTop: 'auto', paddingTop: 14 }}>
            <Sparkline values={values} color="#337AFF" height={44} />
        </div>
    );
}

function DashCard({ children, accent }: { children: React.ReactNode; accent?: boolean }) {
    return (
        <div
            className="dash-card"
            style={{
                background: accent
                    ? 'linear-gradient(140deg, #FFFFFF 0%, #EBF1FF 100%)'
                    : '#FFFFFF',
                border: '1px solid #E2E8F0',
                borderRadius: '18px',
                padding: '16px 18px',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
                overflow: 'hidden',
                minHeight: 152,
                boxShadow: '0 1px 2px rgba(15,23,42,0.04)',
            }}
        >
            {children}
        </div>
    );
}

function CardLabel({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#64748B', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.6 }}>
            <span style={{ color: '#337AFF', display: 'inline-flex' }}>{icon}</span>
            {children}
        </div>
    );
}

function CardValue({ children }: { children: React.ReactNode }) {
    return (
        <div style={{ marginTop: 6, fontSize: 34, lineHeight: 1.05, color: '#0F172A', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
            {children}
        </div>
    );
}

function DeltaPill({ delta }: { delta: number }) {
    if (!Number.isFinite(delta) || delta === 0) {
        return (
            <div style={{ marginTop: 6, fontSize: 11, color: '#94A3B8', fontWeight: 600 }}>
                — vs previous period
            </div>
        );
    }
    const positive = delta > 0;
    const color = positive ? '#059669' : '#DC2626';
    const bg = positive ? 'rgba(16,185,129,0.12)' : 'rgba(220,38,38,0.10)';
    return (
        <div
            style={{
                marginTop: 8,
                alignSelf: 'flex-start',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '3px 10px',
                borderRadius: 999,
                background: bg,
                color,
                fontSize: 11,
                fontWeight: 700,
            }}
        >
            <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                {positive ? <polyline points="3 11 8 6 13 11" /> : <polyline points="3 5 8 10 13 5" />}
            </svg>
            {positive ? '+' : ''}{delta.toFixed(1)}%
        </div>
    );
}

function EyeIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
        </svg>
    );
}

function HeartIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 1 0-7.78 7.78L12 21l8.84-8.84a5.5 5.5 0 0 0 0-7.78z" />
        </svg>
    );
}

function StackIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
            <rect x="3" y="3" width="18" height="18" rx="3" />
            <line x1="3" y1="9" x2="21" y2="9" />
            <line x1="9" y1="21" x2="9" y2="9" />
        </svg>
    );
}
