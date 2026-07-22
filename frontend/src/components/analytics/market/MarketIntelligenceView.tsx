'use client';

import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import { analyticsFetch } from '../analytics-types';

/* Market Intelligence (Slice 2): audience language layer.
 *
 * Renders two record kinds with a hard visual distinction (data-integrity
 * contract): observations (scraped questions/phrases) always ship with
 * their source link + scrape date; personas are model interpretations and
 * are labelled AI-generated with their supporting-source count. */

interface ObservationOut {
    id: string;
    type: string;
    text: string;
    language: string | null;
    source: string | null;
    source_url: string | null;
    scraped_at: string | null;
    extra: Record<string, unknown>;
}

interface PersonaOut {
    archetype?: string;
    pains?: string[];
    vocabulary?: string[];
    triggers?: string[];
    language?: string | null;
    based_on?: number;
    ai_generated?: boolean;
}

interface AudienceResearchResponse {
    personas: PersonaOut[];
    questions: ObservationOut[];
    phrases: ObservationOut[];
    coverage: Record<string, { observations: number; low_confidence: boolean }>;
    updated_at: string | null;
}

const CARD: React.CSSProperties = {
    background: 'var(--surface-2, rgba(148,163,184,0.06))',
    border: '1px solid var(--line, rgba(148,163,184,0.15))',
    borderRadius: 12,
    padding: 16,
};

export default function MarketIntelligenceView({ refreshKey = 0 }: { refreshKey?: number }) {
    const { t } = useTranslation();
    const [data, setData] = useState<AudienceResearchResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const load = useCallback(async () => {
        try {
            const res = await analyticsFetch<AudienceResearchResponse>(
                '/api/analytics/research/audience',
                { skipProjectScope: true },
            );
            setData(res);
        } catch {
            /* leave prior state */
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load, refreshKey]);

    const startRefresh = useCallback(async () => {
        setRefreshing(true);
        try {
            await analyticsFetch('/api/analytics/research/audience/refresh', {
                method: 'POST',
                skipProjectScope: true,
            });
            // research runs in the background; poll a few times for arrival
            for (let i = 0; i < 6; i++) {
                await new Promise((r) => setTimeout(r, 20_000));
                await load();
            }
        } finally {
            setRefreshing(false);
        }
    }, [load]);

    if (loading) {
        return <div style={{ padding: 40, color: 'var(--text-3)', fontSize: 13 }}>{t('analytics.market.loading')}</div>;
    }

    const empty = !data || (data.personas.length === 0 && data.questions.length === 0 && data.phrases.length === 0);
    const lowCoverage = Object.entries(data?.coverage ?? {}).filter(([, c]) => c.low_confidence);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* header row */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                <div style={{ color: 'var(--text-3)', fontSize: 12 }}>
                    {data?.updated_at
                        ? `${t('analytics.market.asOf')} ${new Date(data.updated_at).toLocaleDateString()}`
                        : t('analytics.market.neverRun')}
                </div>
                <button
                    onClick={() => void startRefresh()}
                    disabled={refreshing}
                    style={{
                        border: '1px solid var(--line, rgba(148,163,184,0.25))',
                        background: refreshing ? 'transparent' : 'var(--surface-2, rgba(148,163,184,0.08))',
                        color: 'var(--text-2, #cbd5e1)',
                        borderRadius: 8, padding: '6px 14px', fontSize: 12, cursor: refreshing ? 'default' : 'pointer',
                    }}
                >
                    {refreshing ? t('analytics.market.refreshing') : t('analytics.market.refresh')}
                </button>
            </div>

            {lowCoverage.length > 0 && (
                <div style={{ ...CARD, borderColor: 'rgba(217,119,6,0.4)', fontSize: 12, color: 'var(--text-2)' }}>
                    {t('analytics.market.lowCoverage')}{' '}
                    {lowCoverage.map(([lang]) => lang.toUpperCase()).join(', ')}
                </div>
            )}

            {empty ? (
                <div style={{ ...CARD, textAlign: 'center', padding: 48 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{t('analytics.market.emptyTitle')}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-3)', maxWidth: 440, margin: '0 auto 16px' }}>
                        {t('analytics.market.emptyBody')}
                    </div>
                </div>
            ) : (
                <>
                    {/* personas — interpretations, visibly labelled */}
                    {data!.personas.length > 0 && (
                        <section>
                            <h3 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 10px' }}>{t('analytics.market.personas')}</h3>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                                {data!.personas.map((p, i) => (
                                    <div key={i} style={CARD}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
                                            <strong style={{ fontSize: 13 }}>{p.archetype}</strong>
                                            <span style={{ fontSize: 10, color: 'var(--text-3)', whiteSpace: 'nowrap' }}>
                                                {(p.language || '').toUpperCase()}
                                            </span>
                                        </div>
                                        {(p.pains ?? []).length > 0 && (
                                            <ul style={{ margin: '0 0 8px', paddingLeft: 16, fontSize: 12, color: 'var(--text-2)' }}>
                                                {p.pains!.map((x, j) => <li key={j}>{x}</li>)}
                                            </ul>
                                        )}
                                        {(p.vocabulary ?? []).length > 0 && (
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                                                {p.vocabulary!.map((v, j) => (
                                                    <span key={j} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: 'rgba(59,130,246,0.12)', color: 'var(--text-2)' }}>
                                                        “{v}”
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                        <div style={{ fontSize: 10, color: 'var(--text-3)' }}>
                                            {t('analytics.market.aiGenerated')} · {t('analytics.market.basedOn')} {p.based_on ?? 0}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* observations — provenance always visible */}
                    <ObservationList title={t('analytics.market.questions')} items={data!.questions} t={t} />
                    <ObservationList title={t('analytics.market.phrases')} items={data!.phrases} t={t} />
                </>
            )}
        </div>
    );
}

function ObservationList({
    title,
    items,
    t,
}: {
    title: string;
    items: ObservationOut[];
    t: (k: string) => string;
}) {
    if (items.length === 0) return null;
    return (
        <section>
            <h3 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 10px' }}>{title}</h3>
            <div style={{ ...CARD, padding: 8 }}>
                {items.map((o) => (
                    <div
                        key={o.id}
                        style={{
                            display: 'flex', alignItems: 'baseline', gap: 10, padding: '7px 8px',
                            borderBottom: '1px solid var(--line, rgba(148,163,184,0.08))', fontSize: 12,
                        }}
                    >
                        <span style={{ flex: 1, color: 'var(--text-1, #e2e8f0)' }}>{o.text}</span>
                        <span style={{ fontSize: 10, color: 'var(--text-3)', whiteSpace: 'nowrap' }}>
                            {o.source === 'reddit' ? `r/${String(o.extra?.community ?? '').replace(/^r\//, '') || 'reddit'}` : 'Google'}
                            {o.scraped_at ? ` · ${new Date(o.scraped_at).toLocaleDateString()}` : ''}
                        </span>
                        {o.source_url && (
                            <a href={o.source_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--blue, #3b82f6)', textDecoration: 'none' }}>
                                ↗
                            </a>
                        )}
                    </div>
                ))}
            </div>
        </section>
    );
}
