'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { apiFetch } from '@/lib/utils';
import { syncStudioConnections } from '@/components/analytics/analytics-types';
import type { SocialConnection } from '@/lib/types';
import { useTranslation } from '@/lib/i18n';

/* ── Platform metadata ──────────────────────────────────────────────────── */
const PLATFORMS = [
    {
        id: 'instagram',
        name: 'Instagram',
        color: '#E1306C',
        icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 28, height: 28 }}>
                <rect x="2" y="2" width="20" height="20" rx="5" />
                <circle cx="12" cy="12" r="5" />
                <circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none" />
            </svg>
        ),
    },
    {
        id: 'tiktok',
        name: 'TikTok',
        color: '#000000',
        icon: (
            <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: 28, height: 28 }}>
                <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1 0-5.78 2.93 2.93 0 0 1 .88.13v-3.5a6.37 6.37 0 0 0-.88-.07 6.33 6.33 0 0 0 0 12.67 6.33 6.33 0 0 0 6.33-6.33V9.41a8.16 8.16 0 0 0 3.77.94V6.88a4.85 4.85 0 0 1-.01-.19z" />
            </svg>
        ),
    },
    {
        id: 'youtube',
        name: 'YouTube',
        color: '#FF0000',
        icon: (
            <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: 28, height: 28 }}>
                <path d="M23.5 6.19a3.02 3.02 0 0 0-2.12-2.14C19.54 3.5 12 3.5 12 3.5s-7.54 0-9.38.55A3.02 3.02 0 0 0 .5 6.19 31.6 31.6 0 0 0 0 12a31.6 31.6 0 0 0 .5 5.81 3.02 3.02 0 0 0 2.12 2.14c1.84.55 9.38.55 9.38.55s7.54 0 9.38-.55a3.02 3.02 0 0 0 2.12-2.14A31.6 31.6 0 0 0 24 12a31.6 31.6 0 0 0-.5-5.81zM9.75 15.02V8.98L15.5 12l-5.75 3.02z" />
            </svg>
        ),
    },
    {
        id: 'facebook',
        name: 'Facebook',
        color: '#1877F2',
        icon: (
            <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: 28, height: 28 }}>
                <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
            </svg>
        ),
    },
];

/* ── Page Component ─────────────────────────────────────────────────────── */
export default function ConnectionsPage() {
    const { t } = useTranslation();
    const search = useSearchParams();
    const [socials, setSocials] = useState<SocialConnection[]>([]);
    const [loading, setLoading] = useState(true);
    const [connecting, setConnecting] = useState(false);
    const [verifying, setVerifying] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [connectError, setConnectError] = useState<string | null>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const pollDeadlineRef = useRef<number>(0);
    const linkedPollStartedRef = useRef(false);

    const stopPolling = () => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    };

    /* Fetch connections */
    const fetchConnections = async (opts?: { syncAnalytics?: boolean }) => {
        try {
            const data = await apiFetch<{ socials: SocialConnection[] }>('/api/connections');
            setSocials(data.socials || []);
            // Always nudge analytics sync when asked — empty socials is the
            // disconnect signal the backend reconciler needs, and non-empty
            // socials is the connect signal.
            if (opts?.syncAnalytics) {
                syncStudioConnections().catch(() => { /* best-effort */ });
            }
            return data.socials || [];
        } catch {
            return [];
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchConnections(); }, []);

    /* Re-poll connections whenever the SaaS tab regains focus or visibility.
     * After the user finishes linking on the Ayrshare popup and switches back
     * to our tab, Ayrshare's `/user` endpoint usually reflects the new
     * platform within a few seconds — refetching on focus surfaces it
     * without forcing a hard refresh. */
    useEffect(() => {
        const onVisible = () => {
            if (document.visibilityState === 'visible') {
                void fetchConnections({ syncAnalytics: true });
            }
        };
        const onFocus = () => { void fetchConnections({ syncAnalytics: true }); };
        document.addEventListener('visibilitychange', onVisible);
        window.addEventListener('focus', onFocus);
        return () => {
            document.removeEventListener('visibilitychange', onVisible);
            window.removeEventListener('focus', onFocus);
        };
    }, []);

    /* Clean up polling on unmount */
    useEffect(() => () => stopPolling(), []);

    /** Poll Ayrshare until a new platform appears or the deadline passes.
     *  OAuth can take 2–3 minutes to propagate — we must NOT stop polling
     *  just because the user closed the Ayrshare tab. */
    const startConnectionPoll = useCallback((baselinePlatforms: Set<string>) => {
        stopPolling();
        setVerifying(true);
        setConnectError(null);
        pollDeadlineRef.current = Date.now() + 180_000;

        pollRef.current = setInterval(async () => {
            try {
                const newSocials = await fetchConnections({ syncAnalytics: true });
                const gained = newSocials.some(
                    (s) => !baselinePlatforms.has((s.platform || '').toLowerCase()),
                );
                const expired = Date.now() >= pollDeadlineRef.current;
                if (gained) {
                    stopPolling();
                    setConnecting(false);
                    setVerifying(false);
                    return;
                }
                if (expired) {
                    stopPolling();
                    setConnecting(false);
                    setVerifying(false);
                    setConnectError(t('connections.linkIncomplete'));
                }
            } catch { /* keep polling until deadline */ }
        }, 3000);
    }, [t]);

    /* When Ayrshare redirects back after linking (?linked=1), start polling
     * even if Connect wasn't clicked in this tab session. */
    useEffect(() => {
        if (search.get('linked') !== '1' || loading || linkedPollStartedRef.current) return;
        linkedPollStartedRef.current = true;
        const baseline = new Set(
            socials.map((s) => (s.platform || '').toLowerCase()).filter(Boolean),
        );
        startConnectionPoll(baseline);
    }, [search, loading, socials, startConnectionPoll]);

    /* Handle connect click — opens Ayrshare OAuth popup
     *
     * CRITICAL: browsers only treat `window.open(...)` as user-initiated
     * (and therefore allow the popup) when it runs SYNCHRONOUSLY inside a
     * click handler. The Ayrshare JWT roundtrip is async — if we wait for
     * it before calling `window.open`, Chrome/Brave/Safari silently block
     * the popup ("nothing happens"). To dodge that we open about:blank
     * synchronously and redirect it once the URL is back. */
    const handleConnect = async () => {
        setConnectError(null);

        // Step 1: open the popup synchronously while we still have the
        // user-gesture token. `about:blank` is fine here — Meta / Instagram
        // OAuth needs a full browser tab, not a fixed-size popup window,
        // because cookies, storage partitioning, and bot detection behave
        // differently inside small popups.
        const popup = window.open('about:blank', '_blank');
        if (!popup) {
            setConnectError('Popup was blocked. Allow popups for this site and try again.');
            return;
        }

        // Helpful holding screen so the user knows what's happening if
        // the JWT fetch is slow. Inline HTML to avoid an extra round trip.
        try {
            popup.document.write(
                '<!doctype html><meta charset="utf-8"><title>Connecting…</title>'
                + '<style>html,body{height:100%;margin:0;display:flex;align-items:center;justify-content:center;'
                + 'font:14px -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;color:#5b6679;'
                + 'background:#F6F8FC}</style><div>Preparing secure connect link…</div>'
            );
        } catch { /* cross-origin guard — fine, the about:blank page already shows nothing */ }

        setConnecting(true);
        try {
            // Pass our real origin so Ayrshare returns the user to this page
            // after they finish linking instead of leaving them on the social
            // platform's own site.
            const redirect = `${window.location.origin}/connections?linked=1`;
            const data = await apiFetch<{ url: string }>('/api/ayrshare/jwt', {
                method: 'POST',
                body: JSON.stringify({ redirect }),
            });
            if (!data.url) {
                popup.close();
                throw new Error('Ayrshare did not return a connect URL.');
            }
            // Step 2: redirect the already-open popup to the real URL.
            popup.location.href = data.url;

            // Snapshot which platforms were connected *before* this OAuth
            // attempt so we can detect a newly-linked IG/TikTok/etc. even
            // when the user already had other platforms connected.
            const baselinePlatforms = new Set(
                socials.map((s) => (s.platform || '').toLowerCase()).filter(Boolean),
            );
            startConnectionPoll(baselinePlatforms);
        } catch (err) {
            setConnecting(false);
            setVerifying(false);
            stopPolling();
            try { popup.close(); } catch { /* already closed */ }
            // Surface the backend's `detail` message so the user / dev can
            // see why a connection attempt is failing instead of staring
            // at a button that just toggles state.
            setConnectError(err instanceof Error ? err.message : 'Failed to start connection flow.');
        }
    };

    /* Is a specific platform connected? */
    const getConnection = (platformId: string): SocialConnection | undefined => {
        return socials.find(s => s.platform?.toLowerCase() === platformId);
    };

    if (loading) {
        return (
            <div className="content-area">
                <div className="page-header" style={{ marginBottom: '32px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                        <Link href="/schedule" style={{ color: 'var(--blue)', fontSize: '14px', textDecoration: 'none', fontWeight: 500 }}>{t('connections.backSchedule')}</Link>
                    </div>
                    <h1>{t('connections.title')}</h1>
                    <p>{t('connections.subtitle')}</p>
                </div>

                {/* Info banner */}
                <div style={{
                    background: 'var(--blue-light, #F0F4FF)',
                    border: '1px solid rgba(51,122,255,0.15)',
                    borderRadius: '12px',
                    padding: '16px 20px',
                    marginBottom: '32px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                }}>
                    <svg viewBox="0 0 24 24" style={{ width: 20, height: 20, stroke: 'var(--blue)', fill: 'none', strokeWidth: 2, flexShrink: 0 }}>
                        <circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" />
                    </svg>
                    <span style={{ fontSize: '13px', color: 'var(--text-2)', lineHeight: 1.5 }}>
                        {t('connections.securityNote')}
                        {' '}
                        {t('connections.metaLoginHint')}
                    </span>
                </div>

                {/* Skeleton cards */}
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                    gap: '20px',
                }}>
                    {PLATFORMS.map(platform => (
                        <div key={platform.id} style={{
                            background: 'white',
                            border: '1px solid var(--border)',
                            borderRadius: '14px',
                            padding: '24px',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: '16px',
                            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                        }}>
                            <div style={{
                                width: '56px', height: '56px', borderRadius: '14px',
                                background: `${platform.color}12`, color: platform.color,
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                            }}>
                                {platform.icon}
                            </div>
                            <div style={{ fontWeight: 700, fontSize: '16px', color: 'var(--text-1)' }}>{platform.name}</div>
                            <div style={{ fontSize: '13px', color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--border)', animation: 'pulse 1.5s infinite' }} />
                                {t('connections.checking')}
                            </div>
                            <div style={{
                                width: '100%', padding: '10px 0', borderRadius: '10px',
                                border: '1px solid var(--border)', background: 'transparent',
                                color: 'var(--text-3)', fontSize: '13px', fontWeight: 600, textAlign: 'center',
                            }}>
                                {t('common.loading')}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="content-area">
            <div className="page-header" style={{ marginBottom: '32px' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                            <Link href="/schedule" style={{ color: 'var(--blue)', fontSize: '14px', textDecoration: 'none', fontWeight: 500 }}>{t('connections.backSchedule')}</Link>
                        </div>
                        <h1>{t('connections.title')}</h1>
                        <p>{t('connections.subtitle')}</p>
                    </div>
                    <button
                        type="button"
                        disabled={refreshing || connecting}
                        onClick={async () => {
                            setRefreshing(true);
                            await fetchConnections({ syncAnalytics: true });
                            setRefreshing(false);
                        }}
                        style={{
                            padding: '9px 14px',
                            borderRadius: '8px',
                            border: '1px solid var(--border)',
                            background: 'white',
                            color: 'var(--text-1)',
                            fontSize: '13px',
                            fontWeight: 600,
                            cursor: (refreshing || connecting) ? 'not-allowed' : 'pointer',
                            whiteSpace: 'nowrap',
                            alignSelf: 'flex-start',
                        }}
                    >
                        {refreshing ? t('connections.refreshing') : t('connections.refresh')}
                    </button>
                </div>
            </div>

            {/* Info banner */}
            <div style={{
                background: 'var(--blue-light, #F0F4FF)',
                border: '1px solid rgba(51,122,255,0.15)',
                borderRadius: '12px',
                padding: '16px 20px',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
            }}>
                <svg viewBox="0 0 24 24" style={{ width: 20, height: 20, stroke: 'var(--blue)', fill: 'none', strokeWidth: 2, flexShrink: 0 }}>
                    <circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" />
                </svg>
                <span style={{ fontSize: '13px', color: 'var(--text-2)', lineHeight: 1.5 }}>
                    {t('connections.securityNote')}
                    {' '}
                    {t('connections.metaLoginHint')}
                </span>
            </div>

            {verifying && (
                <div style={{
                    background: 'rgba(51,122,255,0.08)',
                    border: '1px solid rgba(51,122,255,0.2)',
                    borderRadius: '12px',
                    padding: '12px 16px',
                    marginBottom: '16px',
                    fontSize: '13px',
                    color: 'var(--text-2)',
                }}>
                    {t('connections.verifying')}
                </div>
            )}

            {connectError && (
                <div
                    role="alert"
                    style={{
                        background: 'rgba(255,59,48,0.08)',
                        border: '1px solid rgba(255,59,48,0.25)',
                        color: '#b3261e',
                        borderRadius: '12px',
                        padding: '12px 16px',
                        marginBottom: '32px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '10px',
                        fontSize: '13px',
                    }}
                >
                    <svg viewBox="0 0 24 24" style={{ width: 18, height: 18, stroke: 'currentColor', fill: 'none', strokeWidth: 2, flexShrink: 0, marginTop: 1 }}>
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="8" x2="12" y2="12" />
                        <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    <span style={{ flex: 1 }}>{connectError}</span>
                    <button
                        onClick={() => setConnectError(null)}
                        aria-label="Dismiss"
                        style={{
                            background: 'transparent', border: 'none',
                            color: 'currentColor', cursor: 'pointer',
                            fontWeight: 700, fontSize: '15px', lineHeight: 1,
                            padding: '0 4px',
                        }}
                    >
                        ×
                    </button>
                </div>
            )}

            {/* Platform cards grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: '20px',
            }}>
                {PLATFORMS.map(platform => {
                    const conn = getConnection(platform.id);
                    const isConnected = !!conn;

                    return (
                        <div
                            key={platform.id}
                            style={{
                                background: 'white',
                                border: `1px solid ${isConnected ? 'rgba(52,199,89,0.3)' : 'var(--border)'}`,
                                borderRadius: '14px',
                                padding: '24px',
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                gap: '16px',
                                transition: 'all 0.2s ease',
                                boxShadow: isConnected ? '0 2px 12px rgba(52,199,89,0.08)' : '0 1px 4px rgba(0,0,0,0.04)',
                            }}
                        >
                            {/* Platform icon */}
                            <div style={{
                                width: '56px',
                                height: '56px',
                                borderRadius: '14px',
                                background: `${platform.color}12`,
                                color: platform.color,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}>
                                {platform.icon}
                            </div>

                            {/* Platform name */}
                            <div style={{ fontWeight: 700, fontSize: '16px', color: 'var(--text-1)' }}>{platform.name}</div>

                            {/* Status */}
                            {isConnected ? (
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '6px',
                                        justifyContent: 'center',
                                        marginBottom: '4px',
                                    }}>
                                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#34C759' }} />
                                        <span style={{ fontSize: '13px', color: '#34C759', fontWeight: 600 }}>{t('connections.connected')}</span>
                                    </div>
                                    {conn.username && (
                                        <div style={{ fontSize: '12px', color: 'var(--text-3)' }}>@{conn.username}</div>
                                    )}
                                </div>
                            ) : (
                                <div style={{
                                    fontSize: '13px',
                                    color: verifying ? 'var(--blue)' : 'var(--text-3)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                }}>
                                    <div style={{
                                        width: 8, height: 8, borderRadius: '50%',
                                        background: verifying ? 'var(--blue)' : 'var(--border)',
                                        animation: verifying ? 'pulse 1.5s infinite' : undefined,
                                    }} />
                                    {verifying ? t('connections.verifyingShort') : t('connections.notConnected')}
                                </div>
                            )}

                            {/* Action button */}
                            {isConnected ? (
                                <button
                                    style={{
                                        width: '100%',
                                        padding: '10px 0',
                                        borderRadius: '10px',
                                        border: '1px solid var(--border)',
                                        background: 'transparent',
                                        color: 'var(--text-2)',
                                        fontSize: '13px',
                                        fontWeight: 600,
                                        cursor: 'pointer',
                                        transition: 'all 0.15s ease',
                                    }}
                                    onClick={handleConnect}
                                >
                                    {t('connections.manage')}
                                </button>
                            ) : (
                                <button
                                    disabled={connecting}
                                    style={{
                                        width: '100%',
                                        padding: '10px 0',
                                        borderRadius: '10px',
                                        border: 'none',
                                        background: connecting ? 'var(--border)' : platform.color,
                                        color: 'white',
                                        fontSize: '13px',
                                        fontWeight: 600,
                                        cursor: connecting ? 'not-allowed' : 'pointer',
                                        transition: 'all 0.15s ease',
                                        opacity: connecting ? 0.6 : 1,
                                    }}
                                    onClick={handleConnect}
                                >
                                    {connecting ? t('connections.connecting') : t('connections.connect')}
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
