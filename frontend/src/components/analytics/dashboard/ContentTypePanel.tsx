'use client';

import { useTranslation } from '@/lib/i18n';
import { formatCount, type DistributionEntry } from '../analytics-types';

interface Props {
    entries: DistributionEntry[];
    loading?: boolean;
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
    video: <VideoIcon />,
    image: <ImageIcon />,
    carousel: <CarouselIcon />,
    other: <OtherIcon />,
};

const TYPE_COLORS: Record<string, string> = {
    video: '#10B981',
    image: '#8B5CF6',
    carousel: '#F59E0B',
    other: '#94A3B8',
};

/**
 * Horizontal bar chart by content type. Each row shows the icon, label, post
 * count, and a normalized progress bar relative to the highest-volume type.
 */
export default function ContentTypePanel({ entries, loading }: Props) {
    const { t } = useTranslation();
    const max = entries.reduce((m, e) => Math.max(m, e.posts), 0);

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
                {t('analytics.dashboard.distribution.contentTypeTitle')}
            </div>

            {entries.length === 0 ? (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', fontSize: 12, color: '#94A3B8', lineHeight: 1.5 }}>
                    {t('analytics.dashboard.distribution.empty')}
                </div>
            ) : (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 16 }}>
                    {entries.map((e) => {
                        const key = e.key.toLowerCase();
                        const color = TYPE_COLORS[key] || TYPE_COLORS.other;
                        const pct = max ? (e.posts / max) * 100 : 0;
                        return (
                            <div key={e.key} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#0F172A' }}>
                                        <span style={{ color, display: 'inline-flex' }}>
                                            {TYPE_ICONS[key] || TYPE_ICONS.other}
                                        </span>
                                        <span style={{ fontSize: 13, fontWeight: 600, textTransform: 'capitalize' }}>
                                            {labelForType(t, key)}
                                        </span>
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, color: '#475569', fontVariantNumeric: 'tabular-nums' }}>
                                        <span style={{ fontSize: 16, fontWeight: 700, color: '#0F172A' }}>{formatCount(e.posts)}</span>
                                        <span style={{ fontSize: 11, color: '#94A3B8' }}>{t('analytics.dashboard.distribution.posts')}</span>
                                    </div>
                                </div>
                                <div
                                    style={{
                                        height: 6,
                                        borderRadius: 999,
                                        background: '#F1F5F9',
                                        overflow: 'hidden',
                                    }}
                                >
                                    <div
                                        style={{
                                            width: `${Math.max(4, pct)}%`,
                                            height: '100%',
                                            background: `linear-gradient(90deg, ${color} 0%, ${color}88 100%)`,
                                            borderRadius: 999,
                                            transition: 'width 0.3s ease',
                                        }}
                                    />
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

function labelForType(t: (k: string) => string, key: string): string {
    const candidate = t(`analytics.dashboard.contentType.${key}`);
    if (candidate && candidate !== `analytics.dashboard.contentType.${key}`) return candidate;
    return key.charAt(0).toUpperCase() + key.slice(1);
}

function VideoIcon() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <polygon points="23 7 16 12 23 17 23 7" />
            <rect x="1" y="5" width="15" height="14" rx="2" />
        </svg>
    );
}

function ImageIcon() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
        </svg>
    );
}

function CarouselIcon() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <rect x="2" y="6" width="14" height="14" rx="2" />
            <path d="M18 6h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-2" />
        </svg>
    );
}

function OtherIcon() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="9" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
    );
}
