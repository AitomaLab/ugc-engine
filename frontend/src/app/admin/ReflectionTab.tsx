'use client';

import { useCallback, useEffect, useState } from 'react';
import { adminFetch, ADMIN_PRIMARY } from './adminFetch';

interface ReflectionUser {
    user_id: string;
    email: string | null;
    handles: string[];
}

interface ReflectionMemory {
    user_id: string;
    reflection_log: string | null;
    creative_guidelines: string | null;
    account_profile: string | null;
    last_sweep: Record<string, unknown>;
}

const CARD: React.CSSProperties = {
    background: 'white',
    border: '1px solid #E2E8F0',
    borderRadius: 12,
    padding: '16px 18px',
};

const PRE: React.CSSProperties = {
    margin: 0,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    fontSize: 12.5,
    lineHeight: 1.5,
    color: '#0F172A',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
};

function Block({ title, body }: { title: string; body: string | null }) {
    return (
        <div style={CARD}>
            <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: 0.4, color: '#64748B', textTransform: 'uppercase', marginBottom: 10 }}>
                {title}
            </div>
            {body
                ? <pre style={PRE}>{body}</pre>
                : <div style={{ fontSize: 13, color: '#94A3B8' }}>Not created yet.</div>}
        </div>
    );
}

export default function ReflectionTab() {
    const [users, setUsers] = useState<ReflectionUser[]>([]);
    const [selected, setSelected] = useState<string>('');
    const [memory, setMemory] = useState<ReflectionMemory | null>(null);
    const [lastSweep, setLastSweep] = useState<Record<string, unknown>>({});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        (async () => {
            try {
                const [u, s] = await Promise.all([
                    adminFetch<ReflectionUser[]>('/api/admin/reflection/users'),
                    adminFetch<Record<string, unknown>>('/api/admin/reflection/last-sweep'),
                ]);
                setUsers(u);
                setLastSweep(s);
            } catch (e) {
                setError(e instanceof Error ? e.message : 'Failed to load');
            }
        })();
    }, []);

    const loadUser = useCallback(async (userId: string) => {
        if (!userId) { setMemory(null); return; }
        setLoading(true);
        setError(null);
        try {
            const m = await adminFetch<ReflectionMemory>(`/api/admin/reflection/${userId}`);
            setMemory(m);
            if (m.last_sweep && Object.keys(m.last_sweep).length) setLastSweep(m.last_sweep);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load user');
            setMemory(null);
        } finally {
            setLoading(false);
        }
    }, []);

    const sweepEmpty = !lastSweep || Object.keys(lastSweep).length === 0;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {error && (
                <div style={{ ...CARD, borderColor: '#FCA5A5', background: '#FEF2F2', color: '#B91C1C', fontSize: 13 }}>
                    {error}
                </div>
            )}

            <div style={CARD}>
                <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: 0.4, color: '#64748B', textTransform: 'uppercase', marginBottom: 10 }}>
                    Last nightly sweep
                </div>
                {sweepEmpty
                    ? <div style={{ fontSize: 13, color: '#94A3B8' }}>No sweep has run in this backend process yet.</div>
                    : (
                        <div style={{ fontSize: 13, color: '#0F172A', display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                            <span><strong>Status:</strong> {String(lastSweep.status ?? '—')}</span>
                            <span><strong>Users:</strong> {String(lastSweep.users_synced ?? 0)}/{String(lastSweep.users_total ?? 0)} synced</span>
                            <span><strong>Failed:</strong> {String(lastSweep.users_failed ?? 0)}</span>
                            <span><strong>Finished:</strong> {String(lastSweep.finished_at ?? 'running…')}</span>
                        </div>
                    )}
            </div>

            <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <label style={{ fontSize: 13, fontWeight: 700, color: '#334155' }}>Account:</label>
                <select
                    value={selected}
                    onChange={(e) => { setSelected(e.target.value); loadUser(e.target.value); }}
                    style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #CBD5E1', fontSize: 13, minWidth: 320, background: 'white', color: '#0F172A' }}
                >
                    <option value="">Select an account…</option>
                    {users.map((u) => (
                        <option key={u.user_id} value={u.user_id}>
                            {(u.handles[0] || u.email || u.user_id)}{u.email ? ` — ${u.email}` : ''}
                        </option>
                    ))}
                </select>
                {loading && <span style={{ fontSize: 13, color: '#94A3B8' }}>Loading…</span>}
            </div>

            {memory && (
                <>
                    <Block title="Creative Guidelines (raw)" body={memory.creative_guidelines} />
                    <Block title="Reflection Log" body={memory.reflection_log} />
                    <Block title="Account Profile" body={memory.account_profile} />
                </>
            )}
        </div>
    );
}
