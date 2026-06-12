'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import {
    analyticsFetch,
    timeAgo,
    type AnalyticsPlatform,
    type TrackedAccount,
    type TrackedAccountWithJob,
} from './analytics-types';

const PLATFORMS: AnalyticsPlatform[] = ['tiktok', 'instagram', 'youtube', 'facebook'];

interface Props {
    /**
     * Called after the user adds, refreshes, or removes a tracked account so
     * the parent can re-fetch posts + stats and refresh the account pill row.
     */
    onChanged?: () => void;
}

export default function TrackedAccountsManager({ onChanged }: Props) {
    const { t } = useTranslation();
    const [open, setOpen] = useState(false);
    const [accounts, setAccounts] = useState<TrackedAccount[]>([]);
    const [loading, setLoading] = useState(false);
    const [platform, setPlatform] = useState<AnalyticsPlatform>('tiktok');
    const [username, setUsername] = useState('');
    const [adding, setAdding] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [refreshingId, setRefreshingId] = useState<string | null>(null);

    const reload = async () => {
        setLoading(true);
        try {
            const rows = await analyticsFetch<TrackedAccount[]>('/api/analytics/tracked-accounts', {
                skipProjectScope: true,
            });
            setAccounts(rows);
        } catch {
            setAccounts([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (open) reload();
    }, [open]);

    const notifyParent = () => {
        onChanged?.();
    };

    const addAccount = async () => {
        const u = username.trim().replace(/^@/, '');
        if (!u) return;
        setAdding(true);
        setError(null);
        try {
            // POST /tracked-accounts now auto-scrapes the account, so this
            // round-trip can take ~10s. The response carries the scraped
            // posts so the parent grid updates immediately on refetch.
            const res = await analyticsFetch<TrackedAccountWithJob>('/api/analytics/tracked-accounts', {
                method: 'POST',
                body: JSON.stringify({ platform, username: u }),
                skipProjectScope: true,
            });
            if (res.status === 'failed' && res.error_message) {
                setError(res.error_message);
            } else {
                setUsername('');
            }
            await reload();
            notifyParent();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to add account');
        } finally {
            setAdding(false);
        }
    };

    const refreshAccount = async (id: string) => {
        setRefreshingId(id);
        setError(null);
        try {
            const res = await analyticsFetch<TrackedAccountWithJob>(
                `/api/analytics/tracked-accounts/${id}/refresh`,
                { method: 'POST', skipProjectScope: true },
            );
            if (res.status === 'failed' && res.error_message) {
                setError(res.error_message);
            }
            await reload();
            notifyParent();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to refresh account');
        } finally {
            setRefreshingId(null);
        }
    };

    const removeAccount = async (id: string) => {
        try {
            await analyticsFetch(`/api/analytics/tracked-accounts/${id}`, {
                method: 'DELETE',
                skipProjectScope: true,
            });
            setAccounts((prev) => prev.filter((a) => a.id !== id));
            notifyParent();
        } catch {
            // best-effort
        }
    };

    return (
        <div style={{ position: 'relative' }}>
            <button
                onClick={() => setOpen((v) => !v)}
                style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 14px',
                    borderRadius: '10px',
                    border: '1px solid var(--border)',
                    background: 'white',
                    color: 'var(--text-1)',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                }}
            >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="8.5" cy="7" r="4" />
                    <line x1="20" y1="8" x2="20" y2="14" />
                    <line x1="23" y1="11" x2="17" y2="11" />
                </svg>
                {t('analytics.tracked.title')}
                {accounts.length > 0 && (
                    <span
                        style={{
                            background: 'var(--blue-light)',
                            color: 'var(--blue)',
                            padding: '1px 8px',
                            borderRadius: '999px',
                            fontSize: '11px',
                            fontWeight: 700,
                        }}
                    >
                        {accounts.length}
                    </span>
                )}
            </button>

            {open && (
                <>
                    <div
                        onClick={() => setOpen(false)}
                        style={{ position: 'fixed', inset: 0, zIndex: 50, background: 'transparent' }}
                    />
                    <div
                        style={{
                            position: 'absolute',
                            top: 'calc(100% + 6px)',
                            right: 0,
                            zIndex: 51,
                            background: 'white',
                            borderRadius: 'var(--radius)',
                            border: '1px solid var(--border)',
                            boxShadow: 'var(--shadow-lg)',
                            padding: '14px',
                            width: 360,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '12px',
                        }}
                    >
                        <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-1)' }}>
                            {t('analytics.tracked.title')}
                        </div>

                        <div style={{ display: 'flex', gap: '6px' }}>
                            <select
                                value={platform}
                                onChange={(e) => setPlatform(e.target.value as AnalyticsPlatform)}
                                disabled={adding}
                                style={{
                                    padding: '7px 8px',
                                    borderRadius: '8px',
                                    border: '1px solid var(--border)',
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    color: 'var(--text-1)',
                                    background: 'white',
                                }}
                            >
                                {PLATFORMS.map((p) => (
                                    <option key={p} value={p}>
                                        {p}
                                    </option>
                                ))}
                            </select>
                            <input
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                placeholder="@handle"
                                disabled={adding}
                                style={{
                                    flex: 1,
                                    padding: '7px 10px',
                                    borderRadius: '8px',
                                    border: '1px solid var(--border)',
                                    fontSize: '12px',
                                    color: 'var(--text-1)',
                                }}
                            />
                            <button
                                onClick={addAccount}
                                disabled={adding || !username.trim()}
                                style={{
                                    padding: '7px 12px',
                                    borderRadius: '8px',
                                    border: 'none',
                                    background: 'var(--blue)',
                                    color: 'white',
                                    fontSize: '12px',
                                    fontWeight: 700,
                                    cursor: adding || !username.trim() ? 'not-allowed' : 'pointer',
                                }}
                            >
                                {adding ? t('analytics.tracked.adding') : t('analytics.tracked.add')}
                            </button>
                        </div>

                        {error && (
                            <div
                                style={{
                                    fontSize: '11px',
                                    color: '#FF3B30',
                                    background: 'rgba(255,59,48,0.08)',
                                    padding: '6px 8px',
                                    borderRadius: '8px',
                                }}
                            >
                                {error}
                            </div>
                        )}

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: 300, overflowY: 'auto' }}>
                            {loading && <div style={{ fontSize: '12px', color: 'var(--text-3)' }}>{t('common.loading')}</div>}
                            {!loading && accounts.length === 0 && (
                                <div style={{ fontSize: '12px', color: 'var(--text-3)', padding: '8px 0' }}>
                                    {t('analytics.tracked.empty')}
                                </div>
                            )}
                            {accounts.map((a) => {
                                const isRefreshing = refreshingId === a.id;
                                return (
                                    <div
                                        key={a.id}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'space-between',
                                            padding: '8px 10px',
                                            background: 'var(--blue-light)',
                                            borderRadius: '8px',
                                            gap: '6px',
                                        }}
                                    >
                                        <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
                                            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-1)' }}>
                                                @{a.username}
                                            </span>
                                            <span style={{ fontSize: '10px', color: 'var(--text-3)' }}>
                                                <span style={{ textTransform: 'uppercase', fontWeight: 600 }}>
                                                    {a.platform}
                                                </span>
                                                {a.total_posts != null && (
                                                    <>
                                                        {' · '}
                                                        {a.total_posts} {t('analytics.tracked.posts')}
                                                    </>
                                                )}
                                                {a.last_scraped_at && (
                                                    <>
                                                        {' · '}
                                                        {t('analytics.tracked.lastScraped')} {timeAgo(a.last_scraped_at)}
                                                    </>
                                                )}
                                            </span>
                                        </div>
                                        <button
                                            onClick={() => refreshAccount(a.id)}
                                            disabled={isRefreshing}
                                            aria-label={`Refresh ${a.username}`}
                                            title={t('analytics.tracked.refresh')}
                                            style={{
                                                border: '1px solid var(--border)',
                                                background: 'white',
                                                color: isRefreshing ? 'var(--text-3)' : 'var(--blue)',
                                                fontSize: '11px',
                                                fontWeight: 600,
                                                cursor: isRefreshing ? 'not-allowed' : 'pointer',
                                                padding: '4px 10px',
                                                borderRadius: '6px',
                                            }}
                                        >
                                            {isRefreshing ? '…' : t('analytics.tracked.refresh')}
                                        </button>
                                        <button
                                            onClick={() => removeAccount(a.id)}
                                            aria-label={`Remove ${a.username}`}
                                            style={{
                                                border: 'none',
                                                background: 'transparent',
                                                color: 'var(--text-3)',
                                                fontSize: '14px',
                                                cursor: 'pointer',
                                                padding: '4px 6px',
                                            }}
                                        >
                                            ×
                                        </button>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
