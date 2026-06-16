'use client';

import Link from 'next/link';
import { useTranslation } from '@/lib/i18n';

interface Props {
    /**
     * `none` — neither connections nor tracked accounts → encourage both.
     * `noConnections` — accounts tracked but no Studio connections.
     * `noTrackedAccounts` — connected but not tracking competitors.
     * `both` — render both CTAs as a thin reminder strip.
     */
    state: 'none' | 'noConnections' | 'noTrackedAccounts' | 'both';
    onAddExternal: () => void;
}

export default function ConnectExternalCta({ state, onAddExternal }: Props) {
    const { t } = useTranslation();

    const cards: Array<{
        key: 'connect' | 'track';
        title: string;
        body: string;
        cta: string;
        accent: string;
        icon: React.ReactNode;
        action: React.ReactNode;
    }> = [];

    if (state === 'none' || state === 'noConnections' || state === 'both') {
        cards.push({
            key: 'connect',
            title: t('analytics.dashboard.cta.connect.title'),
            body: t('analytics.dashboard.cta.connect.body'),
            cta: t('analytics.dashboard.cta.connect.button'),
            accent: '#337AFF',
            icon: <PlugIcon />,
            action: (
                <Link
                    href="/connections"
                    style={{
                        padding: '10px 20px',
                        borderRadius: 12,
                        background: '#337AFF',
                        color: '#FFFFFF',
                        fontSize: 13,
                        fontWeight: 700,
                        textDecoration: 'none',
                        whiteSpace: 'nowrap',
                        boxShadow: '0 1px 2px rgba(51,122,255,0.25)',
                    }}
                >
                    {t('analytics.dashboard.cta.connect.button')}
                </Link>
            ),
        });
    }

    if (state === 'none' || state === 'noTrackedAccounts' || state === 'both') {
        cards.push({
            key: 'track',
            title: t('analytics.dashboard.cta.track.title'),
            body: t('analytics.dashboard.cta.track.body'),
            cta: t('analytics.dashboard.cta.track.button'),
            accent: '#8B5CF6',
            icon: <SearchIcon />,
            action: (
                <button
                    type="button"
                    onClick={onAddExternal}
                    style={{
                        padding: '10px 20px',
                        borderRadius: 12,
                        background: '#8B5CF6',
                        color: '#FFFFFF',
                        fontSize: 13,
                        fontWeight: 700,
                        border: 'none',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                        boxShadow: '0 1px 2px rgba(139,92,246,0.25)',
                    }}
                >
                    {t('analytics.dashboard.cta.track.button')}
                </button>
            ),
        });
    }

    if (cards.length === 0) return null;

    return (
        <div
            style={{
                display: 'grid',
                gridTemplateColumns: cards.length === 1 ? '1fr' : 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 14,
            }}
        >
            {cards.map((c) => (
                <div
                    key={c.key}
                    style={{
                        background: `linear-gradient(135deg, #FFFFFF 0%, ${c.accent}10 100%)`,
                        border: `1px solid ${c.accent}30`,
                        borderRadius: 18,
                        padding: '18px 22px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 16,
                        flexWrap: 'wrap',
                        boxShadow: '0 1px 2px rgba(15,23,42,0.03)',
                    }}
                >
                    <div
                        style={{
                            width: 44,
                            height: 44,
                            borderRadius: 12,
                            background: `${c.accent}1A`,
                            color: c.accent,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                        }}
                    >
                        {c.icon}
                    </div>
                    <div style={{ flex: 1, minWidth: 200 }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#0F172A' }}>{c.title}</div>
                        <div style={{ fontSize: 12, color: '#64748B', marginTop: 4, lineHeight: 1.5 }}>
                            {c.body}
                        </div>
                    </div>
                    {c.action}
                </div>
            ))}
        </div>
    );
}

function PlugIcon() {
    return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M9 2v6" />
            <path d="M15 2v6" />
            <rect x="6" y="8" width="12" height="8" rx="2" />
            <path d="M12 16v4" />
            <path d="M9 22h6" />
        </svg>
    );
}

function SearchIcon() {
    return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="11" cy="11" r="7" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
    );
}
