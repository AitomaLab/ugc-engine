'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { adminFetch, ADMIN_PRIMARY } from './adminFetch';

type FeedbackStatus = 'open' | 'complete' | 'archived';

interface FeedbackRow {
    id: string;
    user_id?: string | null;
    name: string;
    email?: string | null;
    message: string;
    image_url?: string | null;
    status: FeedbackStatus;
    created_at: string;
}

type StatusFilter = 'all' | FeedbackStatus;

function statusBadgeStyle(status: FeedbackStatus): { bg: string; color: string; label: string } {
    if (status === 'complete') return { bg: 'rgba(5,150,105,0.12)', color: '#059669', label: 'Complete' };
    if (status === 'archived') return { bg: '#F1F5F9', color: '#64748B', label: 'Archived' };
    return { bg: 'rgba(51,122,255,0.12)', color: ADMIN_PRIMARY, label: 'Open' };
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

export default function FeedbackTab() {
    const [rows, setRows] = useState<FeedbackRow[]>([]);
    const [loading, setLoading] = useState(false);
    const [filter, setFilter] = useState<StatusFilter>('all');
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const qs = filter === 'all' ? '' : `?status=${filter}`;
            const data = await adminFetch<FeedbackRow[]>(`/api/feedback/list${qs}`);
            setRows(Array.isArray(data) ? data : []);
        } catch (err) {
            console.error('Failed to load feedback', err);
        } finally {
            setLoading(false);
        }
    }, [filter]);

    useEffect(() => {
        load();
    }, [load]);

    const grouped = useMemo(() => {
        const map = new Map<string, FeedbackRow[]>();
        for (const row of rows) {
            const key = formatDateHeader(row.created_at);
            if (!map.has(key)) map.set(key, []);
            map.get(key)!.push(row);
        }
        return Array.from(map.entries());
    }, [rows]);

    const patchStatus = async (id: string, status: FeedbackStatus) => {
        await adminFetch(`/api/feedback/${id}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ status }),
        });
        await load();
    };

    const remove = async (id: string) => {
        if (!window.confirm('Delete this feedback permanently?')) return;
        await adminFetch(`/api/feedback/${id}`, { method: 'DELETE' });
        await load();
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {(['all', 'open', 'complete', 'archived'] as StatusFilter[]).map((s) => (
                        <button
                            key={s}
                            type="button"
                            onClick={() => setFilter(s)}
                            style={{
                                padding: '6px 12px',
                                borderRadius: 999,
                                border: filter === s ? `1px solid ${ADMIN_PRIMARY}` : '1px solid #E2E8F0',
                                background: filter === s ? 'rgba(51,122,255,0.10)' : '#FFFFFF',
                                color: filter === s ? ADMIN_PRIMARY : '#64748B',
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: 'pointer',
                                textTransform: 'capitalize',
                            }}
                        >
                            {s === 'all' ? 'All' : s}
                        </button>
                    ))}
                </div>
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

            {loading && rows.length === 0 && (
                <div style={{ padding: 24, color: '#94A3B8', fontSize: 14 }}>Loading…</div>
            )}

            {!loading && rows.length === 0 && (
                <div style={{ padding: 24, color: '#94A3B8', fontSize: 14, background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: 16 }}>
                    No feedback yet.
                </div>
            )}

            {grouped.map(([dateLabel, items]) => (
                <section key={dateLabel}>
                    <h3 style={{ margin: '0 0 10px', fontSize: 14, fontWeight: 700, color: '#64748B' }}>{dateLabel}</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {items.map((item) => {
                            const expanded = expandedId === item.id;
                            const badge = statusBadgeStyle(item.status);
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
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                                    <strong style={{ fontSize: 14, color: '#0F172A' }}>{item.name}</strong>
                                                    <span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 700, background: badge.bg, color: badge.color }}>
                                                        {badge.label}
                                                    </span>
                                                    {item.image_url && (
                                                        <span style={{ fontSize: 11, color: '#64748B', fontWeight: 600 }}>📎 image attached</span>
                                                    )}
                                                </div>
                                                <p style={{ margin: '6px 0 0', fontSize: 13, color: '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: expanded ? 'normal' : 'nowrap' }}>
                                                    {item.message}
                                                </p>
                                            </div>
                                            <span style={{ fontSize: 12, color: '#94A3B8', whiteSpace: 'nowrap' }}>{formatTime(item.created_at)}</span>
                                        </div>
                                    </button>

                                    {expanded && (
                                        <div style={{ padding: '0 16px 16px', borderTop: '1px solid #F1F5F9' }}>
                                            {item.email && (
                                                <p style={{ margin: '12px 0 0', fontSize: 13, color: '#64748B' }}>
                                                    <strong>Email:</strong> {item.email}
                                                </p>
                                            )}
                                            <p style={{ margin: '12px 0 0', fontSize: 14, color: '#0F172A', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                                                {item.message}
                                            </p>
                                            {item.image_url && (
                                                <a href={item.image_url} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-block', marginTop: 12 }}>
                                                    <img
                                                        src={item.image_url}
                                                        alt="Feedback attachment"
                                                        style={{ maxWidth: 200, maxHeight: 140, borderRadius: 8, border: '1px solid #E2E8F0', objectFit: 'cover' }}
                                                    />
                                                </a>
                                            )}
                                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
                                                <ActionBtn label="Mark Complete" onClick={() => patchStatus(item.id, 'complete')} />
                                                <ActionBtn label="Archive" onClick={() => patchStatus(item.id, 'archived')} muted />
                                                <ActionBtn label="Delete" onClick={() => remove(item.id)} danger />
                                            </div>
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

function ActionBtn({ label, onClick, muted, danger }: { label: string; onClick: () => void; muted?: boolean; danger?: boolean }) {
    return (
        <button
            type="button"
            onClick={onClick}
            style={{
                padding: '6px 12px',
                borderRadius: 8,
                border: '1px solid #E2E8F0',
                background: danger ? '#FEF2F2' : muted ? '#F8FAFC' : '#FFFFFF',
                color: danger ? '#DC2626' : muted ? '#64748B' : ADMIN_PRIMARY,
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
            }}
        >
            {label}
        </button>
    );
}
