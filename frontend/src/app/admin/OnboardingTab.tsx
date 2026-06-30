'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { adminFetch, ADMIN_PRIMARY } from './adminFetch';

interface OnboardingRow {
    id: string;
    user_id: string;
    name: string;
    email?: string | null;
    role: string;
    team_size: string;
    challenge: string;
    content_type: string;
    monthly_volume: string;
    ui_language?: string | null;
    completed_at: string;
}

function formatDateHeader(iso: string): string {
    try {
        return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
        return iso;
    }
}

function formatTime(iso: string): string {
    try {
        return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    } catch {
        return '';
    }
}

const ANSWER_FIELDS: { key: keyof OnboardingRow; label: string }[] = [
    { key: 'role', label: 'Role' },
    { key: 'team_size', label: 'Team size' },
    { key: 'challenge', label: 'Challenge' },
    { key: 'content_type', label: 'Content type' },
    { key: 'monthly_volume', label: 'Monthly volume' },
];

export default function OnboardingTab() {
    const [rows, setRows] = useState<OnboardingRow[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await adminFetch<OnboardingRow[]>('/api/onboarding/list');
            setRows(Array.isArray(data) ? data : []);
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to load onboarding responses';
            setError(message);
            setRows([]);
            console.error('Failed to load onboarding responses', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const grouped = useMemo(() => {
        const map = new Map<string, OnboardingRow[]>();
        for (const row of rows) {
            const key = formatDateHeader(row.completed_at);
            if (!map.has(key)) map.set(key, []);
            map.get(key)!.push(row);
        }
        return Array.from(map.entries());
    }, [rows]);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                <button
                    type="button"
                    onClick={load}
                    disabled={loading}
                    style={{
                        padding: '8px 14px',
                        borderRadius: 10,
                        border: 'none',
                        background: loading ? '#94A3B8' : ADMIN_PRIMARY,
                        color: '#FFFFFF',
                        fontSize: 13,
                        fontWeight: 700,
                        cursor: loading ? 'not-allowed' : 'pointer',
                    }}
                >
                    {loading ? 'Refreshing…' : 'Refresh'}
                </button>
            </div>

            {error && (
                <div style={{ padding: '14px 16px', color: '#B91C1C', fontSize: 14, background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 12 }}>
                    {error === 'Not Found'
                        ? 'Could not reach /api/onboarding/list (404). Restart ugc_backend so it loads the onboarding router, then refresh.'
                        : error}
                </div>
            )}

            {loading && rows.length === 0 && !error && (
                <div style={{ padding: 24, color: '#94A3B8', fontSize: 14 }}>Loading…</div>
            )}

            {!loading && rows.length === 0 && !error && (
                <div style={{ padding: 24, color: '#94A3B8', fontSize: 14, background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: 16 }}>
                    No onboarding responses yet.
                </div>
            )}

            {grouped.map(([dateLabel, items]) => (
                <section key={dateLabel}>
                    <h3 style={{ margin: '0 0 10px', fontSize: 14, fontWeight: 700, color: '#64748B' }}>{dateLabel}</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {items.map((item) => {
                            const expanded = expandedId === item.id;
                            return (
                                <article
                                    key={item.id}
                                    style={{
                                        background: '#FFFFFF',
                                        border: '1px solid #E2E8F0',
                                        borderRadius: 12,
                                        overflow: 'hidden',
                                    }}
                                >
                                    <button
                                        type="button"
                                        onClick={() => setExpandedId(expanded ? null : item.id)}
                                        style={{
                                            width: '100%',
                                            textAlign: 'left',
                                            padding: '14px 16px',
                                            border: 'none',
                                            background: 'transparent',
                                            cursor: 'pointer',
                                        }}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                                            <div style={{ minWidth: 0, flex: 1 }}>
                                                <strong style={{ fontSize: 14, color: '#0F172A' }}>{item.name}</strong>
                                                {item.email && (
                                                    <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748B' }}>{item.email}</p>
                                                )}
                                                <p style={{ margin: '6px 0 0', fontSize: 13, color: '#475569' }}>
                                                    {item.role} · {item.team_size} · {item.content_type}
                                                </p>
                                            </div>
                                            <span style={{ fontSize: 12, color: '#94A3B8', whiteSpace: 'nowrap' }}>
                                                {formatTime(item.completed_at)}
                                            </span>
                                        </div>
                                    </button>

                                    {expanded && (
                                        <div style={{ padding: '0 16px 16px', borderTop: '1px solid #F1F5F9' }}>
                                            <dl style={{ margin: '12px 0 0', display: 'grid', gap: 10 }}>
                                                {ANSWER_FIELDS.map(({ key, label }) => (
                                                    <div key={key}>
                                                        <dt style={{ margin: 0, fontSize: 11, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                                            {label}
                                                        </dt>
                                                        <dd style={{ margin: '2px 0 0', fontSize: 14, color: '#0F172A' }}>
                                                            {String(item[key] ?? '—')}
                                                        </dd>
                                                    </div>
                                                ))}
                                                {item.ui_language && (
                                                    <div>
                                                        <dt style={{ margin: 0, fontSize: 11, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                                            UI language
                                                        </dt>
                                                        <dd style={{ margin: '2px 0 0', fontSize: 14, color: '#0F172A' }}>
                                                            {item.ui_language.toUpperCase()}
                                                        </dd>
                                                    </div>
                                                )}
                                            </dl>
                                        </div>
                                    )}
                                </article>
                            );
                        })}
                    </div>
                </section>
            ))}
        </div>
    );
}
