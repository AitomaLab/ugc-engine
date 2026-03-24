'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/utils';
import type { SocialConnection } from '@/lib/types';

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
    const [socials, setSocials] = useState<SocialConnection[]>([]);
    const [loading, setLoading] = useState(true);
    const [connecting, setConnecting] = useState(false);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    /* Fetch connections */
    const fetchConnections = async () => {
        try {
            const data = await apiFetch<{ socials: SocialConnection[] }>('/api/connections');
            setSocials(data.socials || []);
        } catch { /* empty */ }
        setLoading(false);
    };

    useEffect(() => { fetchConnections(); }, []);

    /* Clean up polling on unmount */
    useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

    /* Handle connect click — opens Ayrshare OAuth popup */
    const handleConnect = async () => {
        setConnecting(true);
        try {
            const data = await apiFetch<{ url: string }>('/api/ayrshare/jwt', { method: 'POST' });
            if (data.url) {
                const popup = window.open(data.url, '_blank', 'width=600,height=700,left=400,top=100');

                // Poll for updates every 3 seconds
                pollRef.current = setInterval(async () => {
                    try {
                        const updated = await apiFetch<{ socials: SocialConnection[] }>('/api/connections');
                        const newSocials = updated.socials || [];
                        if (newSocials.length > socials.length || !popup || popup.closed) {
                            setSocials(newSocials);
                            setConnecting(false);
                            if (pollRef.current) clearInterval(pollRef.current);
                        }
                    } catch { /* keep polling */ }
                }, 3000);

                // Also stop polling after 2 minutes max
                setTimeout(() => {
                    setConnecting(false);
                    if (pollRef.current) clearInterval(pollRef.current);
                    fetchConnections();
                }, 120000);
            }
        } catch {
            setConnecting(false);
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
                        <Link href="/schedule" style={{ color: 'var(--blue)', fontSize: '14px', textDecoration: 'none', fontWeight: 500 }}>← Schedule</Link>
                    </div>
                    <h1>Social Connections</h1>
                    <p>Connect your social media accounts to schedule and publish your UGC videos directly.</p>
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
                    <span style={{ fontSize: '13px', color: 'var(--text-2)' }}>
                        Your credentials are handled securely by Ayrshare — we never see your social media passwords.
                        After connecting a new account, it may take 2–3 minutes to appear as connected on this page.
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
                                Checking...
                            </div>
                            <div style={{
                                width: '100%', padding: '10px 0', borderRadius: '10px',
                                border: '1px solid var(--border)', background: 'transparent',
                                color: 'var(--text-3)', fontSize: '13px', fontWeight: 600, textAlign: 'center',
                            }}>
                                Loading
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
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                    <Link href="/schedule" style={{ color: 'var(--blue)', fontSize: '14px', textDecoration: 'none', fontWeight: 500 }}>← Schedule</Link>
                </div>
                <h1>Social Connections</h1>
                <p>Connect your social media accounts to schedule and publish your UGC videos directly.</p>
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
                <span style={{ fontSize: '13px', color: 'var(--text-2)' }}>
                    Your credentials are handled securely by Ayrshare — we never see your social media passwords.
                    After connecting a new account, it may take 2–3 minutes to appear as connected on this page.
                </span>
            </div>

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
                                        <span style={{ fontSize: '13px', color: '#34C759', fontWeight: 600 }}>Connected</span>
                                    </div>
                                    {conn.username && (
                                        <div style={{ fontSize: '12px', color: 'var(--text-3)' }}>@{conn.username}</div>
                                    )}
                                </div>
                            ) : (
                                <div style={{
                                    fontSize: '13px',
                                    color: 'var(--text-3)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                }}>
                                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--border)' }} />
                                    Not connected
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
                                    Manage
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
                                    {connecting ? 'Connecting...' : 'Connect'}
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
