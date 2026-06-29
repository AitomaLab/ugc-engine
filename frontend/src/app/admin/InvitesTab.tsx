'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { adminFetch, ADMIN_PRIMARY } from './adminFetch';

interface Invite {
    id: string;
    email: string | null;
    code: string;
    label: string | null;
    is_used: boolean;
    brevo_synced: boolean;
    created_at: string;
    used_at?: string | null;
}

function labelForList(listId: number): string {
    if (listId === 3) return 'Brevo Waitlist';
    if (listId === 10) return 'Beta Testers';
    return `Brevo List ${listId}`;
}

function listDisplayName(listId: number): string {
    if (listId === 3) return 'Waitlist';
    if (listId === 10) return 'Beta Testers';
    return `List ${listId}`;
}

export default function InvitesTab() {
    const [invites, setInvites] = useState<Invite[]>([]);
    const [loadingInvites, setLoadingInvites] = useState(false);
    const [selectedListId, setSelectedListId] = useState(3);

    const loadInvites = useCallback(async () => {
        setLoadingInvites(true);
        try {
            const rows = await adminFetch<Invite[]>('/api/admin/invites');
            setInvites(Array.isArray(rows) ? rows : []);
        } catch (err) {
            console.error('Failed to load invites', err);
        } finally {
            setLoadingInvites(false);
        }
    }, []);

    useEffect(() => {
        loadInvites();
    }, [loadInvites]);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <ListSegmentControl selectedListId={selectedListId} onChange={setSelectedListId} />
            <BrevoImportPanel listId={selectedListId} onDone={loadInvites} />
            <ManualGeneratePanel onDone={loadInvites} />
            <CodeTablePanel invites={invites} listId={selectedListId} loading={loadingInvites} onReload={loadInvites} />
        </div>
    );
}

function ListSegmentControl({ selectedListId, onChange }: { selectedListId: number; onChange: (id: number) => void }) {
    const options = [
        { id: 3, label: 'Waitlist (List 3)' },
        { id: 10, label: 'Beta Testers (List 10)' },
    ] as const;

    return (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {options.map((opt) => {
                const active = selectedListId === opt.id;
                return (
                    <button
                        key={opt.id}
                        type="button"
                        onClick={() => onChange(opt.id)}
                        style={{
                            padding: '8px 16px',
                            borderRadius: 999,
                            border: active ? 'none' : `1px solid ${ADMIN_PRIMARY}`,
                            background: active ? ADMIN_PRIMARY : '#FFFFFF',
                            color: active ? '#FFFFFF' : ADMIN_PRIMARY,
                            fontSize: 13,
                            fontWeight: 700,
                            cursor: 'pointer',
                            transition: 'background 0.15s ease, color 0.15s ease',
                        }}
                    >
                        {opt.label}
                    </button>
                );
            })}
        </div>
    );
}

function Panel({ title, subtitle, children, action }: { title: string; subtitle?: string; children: React.ReactNode; action?: React.ReactNode }) {
    return (
        <section style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: 16, padding: 22, boxShadow: '0 1px 2px rgba(15,23,42,0.04)' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
                <div>
                    <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#0F172A' }}>{title}</h2>
                    {subtitle && <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748B' }}>{subtitle}</p>}
                </div>
                {action}
            </div>
            {children}
        </section>
    );
}

function PrimaryButton({ onClick, disabled, children }: { onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '9px 16px',
                borderRadius: 10,
                border: 'none',
                background: disabled ? '#94A3B8' : ADMIN_PRIMARY,
                color: '#FFFFFF',
                fontSize: 13,
                fontWeight: 700,
                cursor: disabled ? 'not-allowed' : 'pointer',
                whiteSpace: 'nowrap',
                transition: 'background 0.15s ease',
            }}
        >
            {children}
        </button>
    );
}

function Spinner() {
    return (
        <span
            aria-hidden
            style={{
                width: 14,
                height: 14,
                border: '2px solid rgba(255,255,255,0.5)',
                borderTopColor: '#FFFFFF',
                borderRadius: '50%',
                display: 'inline-block',
                animation: 'admin-spin 0.7s linear infinite',
            }}
        />
    );
}

function StatusNote({ tone, children }: { tone: 'ok' | 'err' | 'info'; children: React.ReactNode }) {
    const color = tone === 'ok' ? '#059669' : tone === 'err' ? '#DC2626' : '#475569';
    const bg = tone === 'ok' ? 'rgba(5,150,105,0.10)' : tone === 'err' ? 'rgba(220,38,38,0.10)' : '#F1F5F9';
    return (
        <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 8, background: bg, color, fontSize: 13, fontWeight: 600 }}>
            {children}
        </div>
    );
}

function BrevoImportPanel({ listId, onDone }: { listId: number; onDone: () => void }) {
    const [busy, setBusy] = useState(false);
    const [note, setNote] = useState<{ tone: 'ok' | 'err' | 'info'; text: string } | null>(null);

    const listName = listDisplayName(listId);
    const pullLabel = `Pull ${listName} (List ${listId})`;

    const pull = async () => {
        setBusy(true);
        setNote({ tone: 'info', text: `Pulling ${listName} contacts from Brevo… this can take a moment for large lists.` });
        try {
            const res = await adminFetch<{ imported: number; skipped: number }>(
                `/api/admin/invites/pull-brevo?list_id=${listId}`,
                { method: 'POST' },
            );
            setNote({ tone: 'ok', text: `Imported ${res.imported} new contacts · ${res.skipped} already present.` });
            onDone();
        } catch (err) {
            setNote({ tone: 'err', text: err instanceof Error ? err.message : 'Pull failed.' });
        } finally {
            setBusy(false);
        }
    };

    return (
        <Panel
            title={`Pull ${listName} from Brevo`}
            subtitle={`Fetch contacts from Brevo list ${listId} and generate a BETA- code for each new email.`}
            action={<PrimaryButton onClick={pull} disabled={busy}>{busy && <Spinner />}{busy ? 'Pulling…' : pullLabel}</PrimaryButton>}
        >
            {note && <StatusNote tone={note.tone}>{note.text}</StatusNote>}
        </Panel>
    );
}

function ManualGeneratePanel({ onDone }: { onDone: () => void }) {
    const [emails, setEmails] = useState('');
    const [label, setLabel] = useState('');
    const [busy, setBusy] = useState(false);
    const [note, setNote] = useState<{ tone: 'ok' | 'err' | 'info'; text: string } | null>(null);

    const generate = async () => {
        const list = emails.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
        if (list.length === 0) {
            setNote({ tone: 'err', text: 'Paste at least one email address.' });
            return;
        }
        setBusy(true);
        setNote(null);
        try {
            const res = await adminFetch<{ created: number; skipped: number }>(
                '/api/admin/invites/generate',
                { method: 'POST', body: JSON.stringify({ emails: list, label: label || null }) },
            );
            setNote({ tone: 'ok', text: `Created ${res.created} codes · skipped ${res.skipped} (already existed / invalid).` });
            setEmails('');
            onDone();
        } catch (err) {
            setNote({ tone: 'err', text: err instanceof Error ? err.message : 'Generation failed.' });
        } finally {
            setBusy(false);
        }
    };

    return (
        <Panel
            title="Manual Invite Generation"
            subtitle="Paste one email per line and optionally tag them with a label (e.g. VC Round, Press)."
        >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <textarea
                    value={emails}
                    onChange={(e) => setEmails(e.target.value)}
                    placeholder={'jane@fund.com\njohn@press.com'}
                    rows={5}
                    style={{
                        width: '100%',
                        padding: '10px 12px',
                        border: '1px solid #E2E8F0',
                        borderRadius: 10,
                        fontSize: 13,
                        fontFamily: 'inherit',
                        resize: 'vertical',
                        outline: 'none',
                        boxSizing: 'border-box',
                        color: '#0F172A',
                    }}
                />
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                    <input
                        type="text"
                        value={label}
                        onChange={(e) => setLabel(e.target.value)}
                        placeholder="Label (e.g. VC Round)"
                        style={{
                            flex: 1,
                            minWidth: 200,
                            padding: '9px 12px',
                            border: '1px solid #E2E8F0',
                            borderRadius: 10,
                            fontSize: 13,
                            outline: 'none',
                            boxSizing: 'border-box',
                            color: '#0F172A',
                        }}
                    />
                    <PrimaryButton onClick={generate} disabled={busy}>{busy && <Spinner />}{busy ? 'Generating…' : 'Generate Codes'}</PrimaryButton>
                </div>
                {note && <StatusNote tone={note.tone}>{note.text}</StatusNote>}
            </div>
        </Panel>
    );
}

function CodeTablePanel({ invites, listId, loading, onReload }: { invites: Invite[]; listId: number; loading: boolean; onReload: () => void }) {
    const [syncing, setSyncing] = useState(false);
    const [copiedId, setCopiedId] = useState<string | null>(null);
    const [note, setNote] = useState<{ tone: 'ok' | 'err' | 'info'; text: string } | null>(null);

    const syncLabel = labelForList(listId);
    const listName = listDisplayName(listId);
    const unsyncedCount = useMemo(
        () => invites.filter((i) => !i.brevo_synced && i.email && i.label === syncLabel).length,
        [invites, syncLabel],
    );

    const filteredCodes = invites.filter((c) => c.label === labelForList(listId));

    const copyLink = async (code: string, id: string) => {
        const base =
            process.env.NEXT_PUBLIC_SIGNUP_BASE_URL?.replace(/\/$/, '') ||
            (typeof window !== 'undefined' ? window.location.origin : '');
        const link = `${base}/signup?invite=${code}`;
        try {
            await navigator.clipboard.writeText(link);
            setCopiedId(id);
            setTimeout(() => setCopiedId((c) => (c === id ? null : c)), 1500);
        } catch {
            setNote({ tone: 'err', text: 'Clipboard blocked by the browser.' });
        }
    };

    const syncAll = async () => {
        setSyncing(true);
        setNote({ tone: 'info', text: `Syncing ${unsyncedCount.toLocaleString()} unsynced ${listName} contacts to Brevo…` });
        try {
            const res = await adminFetch<{ synced: number; failed: number }>(
                `/api/admin/invites/sync-brevo?list_id=${listId}`,
                { method: 'POST' },
            );
            setNote({ tone: res.failed ? 'err' : 'ok', text: `Synced ${res.synced} · failed ${res.failed}.` });
            onReload();
        } catch (err) {
            setNote({ tone: 'err', text: err instanceof Error ? err.message : 'Sync failed.' });
        } finally {
            setSyncing(false);
        }
    };

    return (
        <Panel
            title="Code Management"
            subtitle={`${filteredCodes.length.toLocaleString()} codes · ${unsyncedCount.toLocaleString()} ${listName} not yet synced to Brevo`}
            action={
                <PrimaryButton onClick={syncAll} disabled={syncing || unsyncedCount === 0}>
                    {syncing && <Spinner />}
                    {syncing ? `Syncing ${unsyncedCount.toLocaleString()}…` : `Sync ${listName} to Brevo (${unsyncedCount.toLocaleString()})`}
                </PrimaryButton>
            }
        >
            {note && <StatusNote tone={note.tone}>{note.text}</StatusNote>}
            <div style={{ overflowX: 'auto', marginTop: note ? 12 : 0 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                        <tr style={{ textAlign: 'left', color: '#64748B', borderBottom: '1px solid #E2E8F0' }}>
                            {['Email', 'Code', 'Label', 'Used', 'Brevo Synced', 'Created At', ''].map((h) => (
                                <th key={h} style={{ padding: '10px 10px', fontWeight: 700, whiteSpace: 'nowrap' }}>{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {loading && (
                            <tr><td colSpan={7} style={{ padding: 20, color: '#94A3B8' }}>Loading…</td></tr>
                        )}
                        {!loading && filteredCodes.length === 0 && (
                            <tr><td colSpan={7} style={{ padding: 20, color: '#94A3B8' }}>No codes for this list yet. Pull from Brevo or generate above.</td></tr>
                        )}
                        {filteredCodes.map((inv) => (
                            <tr key={inv.id} style={{ borderBottom: '1px solid #F1F5F9', color: '#0F172A' }}>
                                <td style={{ padding: '10px 10px', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{inv.email || '—'}</td>
                                <td style={{ padding: '10px 10px', fontFamily: 'ui-monospace, monospace', fontWeight: 700 }}>{inv.code}</td>
                                <td style={{ padding: '10px 10px', color: '#475569' }}>{inv.label || '—'}</td>
                                <td style={{ padding: '10px 10px' }}><Badge on={inv.is_used} onText="Yes" offText="No" /></td>
                                <td style={{ padding: '10px 10px' }}><Badge on={inv.brevo_synced} onText="Synced" offText="No" /></td>
                                <td style={{ padding: '10px 10px', color: '#64748B', whiteSpace: 'nowrap' }}>{formatDate(inv.created_at)}</td>
                                <td style={{ padding: '10px 10px', whiteSpace: 'nowrap' }}>
                                    <button
                                        type="button"
                                        title="Copy signup link"
                                        aria-label="Copy signup link"
                                        onClick={() => copyLink(inv.code, inv.id)}
                                        style={{
                                            display: 'inline-flex',
                                            alignItems: 'center',
                                            gap: 6,
                                            padding: '5px 10px',
                                            borderRadius: 8,
                                            border: '1px solid #E2E8F0',
                                            background: '#FFFFFF',
                                            color: copiedId === inv.id ? '#059669' : ADMIN_PRIMARY,
                                            fontSize: 12,
                                            fontWeight: 700,
                                            cursor: 'pointer',
                                        }}
                                    >
                                        <CopyIcon />
                                        {copiedId === inv.id ? 'Copied!' : 'Copy Link'}
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <style>{`@keyframes admin-spin { to { transform: rotate(360deg); } }`}</style>
        </Panel>
    );
}

function Badge({ on, onText, offText }: { on: boolean; onText: string; offText: string }) {
    return (
        <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 700, background: on ? 'rgba(5,150,105,0.12)' : '#F1F5F9', color: on ? '#059669' : '#94A3B8' }}>
            {on ? onText : offText}
        </span>
    );
}

function CopyIcon() {
    return (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
    );
}

function formatDate(iso: string): string {
    try {
        return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
        return iso;
    }
}
