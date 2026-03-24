'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { apiFetch, formatDate } from '@/lib/utils';
import type { SocialPost, SocialConnection } from '@/lib/types';
import SchedulePostModal from '@/components/modals/SchedulePostModal';

/* ── Platform colours ───────────────────────────────────────────────────── */
const PLATFORM_COLORS: Record<string, string> = {
    instagram: '#E1306C',
    tiktok:    '#000000',
    youtube:   '#FF0000',
    facebook:  '#1877F2',
};

const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
    scheduled: { bg: 'rgba(51,122,255,0.1)',  color: 'var(--blue)',   label: 'Scheduled' },
    posted:    { bg: 'rgba(52,199,89,0.1)',   color: '#34C759',       label: 'Posted' },
    failed:    { bg: 'rgba(255,59,48,0.1)',   color: '#FF3B30',       label: 'Failed' },
    cancelled: { bg: 'rgba(142,142,147,0.1)', color: '#8E8E93',       label: 'Cancelled' },
};

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function getMonthDays(year: number, month: number) {
    const first = new Date(year, month, 1);
    const lastDate = new Date(year, month + 1, 0).getDate();
    const startDay = first.getDay(); // 0 = Sun
    const days: (number | null)[] = [];
    for (let i = 0; i < startDay; i++) days.push(null);
    for (let d = 1; d <= lastDate; d++) days.push(d);
    return days;
}

function formatMonth(year: number, month: number) {
    return new Date(year, month).toLocaleString('default', { month: 'long', year: 'numeric' });
}

/* ── Page Component ─────────────────────────────────────────────────────── */
export default function SchedulePage() {
    const [viewDate, setViewDate] = useState(new Date());
    const [posts, setPosts] = useState<SocialPost[]>([]);
    const [connectedCount, setConnectedCount] = useState(0);
    const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
    const [loading, setLoading] = useState(true);

    const year = viewDate.getFullYear();
    const month = viewDate.getMonth();
    const days = useMemo(() => getMonthDays(year, month), [year, month]);

    /* Fetch posts for the current month */
    useEffect(() => {
        setLoading(true);
        const start = new Date(year, month, 1).toISOString();
        const end = new Date(year, month + 1, 0, 23, 59, 59).toISOString();
        apiFetch<SocialPost[]>(`/api/schedule?start_date=${start}&end_date=${end}`)
            .then(d => setPosts(d || []))
            .catch(() => setPosts([]))
            .finally(() => setLoading(false));
        apiFetch<{ socials: SocialConnection[] }>('/api/connections')
            .then(d => setConnectedCount((d.socials || []).length))
            .catch(() => {});
    }, [year, month]);

    const prevMonth = () => setViewDate(new Date(year, month - 1));
    const nextMonth = () => setViewDate(new Date(year, month + 1));
    const goToday = () => setViewDate(new Date());

    /* Group posts by day-of-month */
    const postsByDay = useMemo(() => {
        const map: Record<number, SocialPost[]> = {};
        posts.forEach(p => {
            const d = new Date(p.scheduled_at).getDate();
            (map[d] ||= []).push(p);
        });
        return map;
    }, [posts]);

    /* Stats */
    const stats = useMemo(() => {
        const now = new Date();
        return {
            total:     posts.length,
            posted:    posts.filter(p => p.status === 'posted' || (p.status === 'scheduled' && new Date(p.scheduled_at) <= now)).length,
            upcoming:  posts.filter(p => p.status === 'scheduled' && new Date(p.scheduled_at) > now).length,
            failed:    posts.filter(p => p.status === 'failed').length,
        };
    }, [posts]);

    /* Upcoming posts (next 7 days) */
    const upcoming = useMemo(() => {
        const now = new Date();
        const weekLater = new Date(now.getTime() + 7 * 86400000);
        return posts
            .filter(p => p.status === 'scheduled' && new Date(p.scheduled_at) >= now && new Date(p.scheduled_at) <= weekLater)
            .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime());
    }, [posts]);

    const today = new Date();
    const isToday = (day: number | null) => day !== null && year === today.getFullYear() && month === today.getMonth() && day === today.getDate();

    const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

    return (
        <div className="content-area">
            {/* Page header with CTA buttons */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '24px' }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700 }}>Content Calendar</h1>
                    <p style={{ margin: '4px 0 0', color: 'var(--text-3)', fontSize: '14px' }}>Schedule and manage your social media posts</p>
                </div>
                <div style={{ display: 'flex', gap: '10px', flexShrink: 0 }}>
                    <Link href="/connections" style={{
                        display: 'flex', alignItems: 'center', gap: '6px',
                        padding: '9px 16px', borderRadius: '10px',
                        border: '1px solid var(--border)', background: 'white',
                        color: 'var(--text-1)', fontSize: '13px', fontWeight: 600,
                        textDecoration: 'none', transition: 'all 0.15s ease',
                    }}>
                        <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: 'currentColor', fill: 'none', strokeWidth: 2 }}>
                            <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                        </svg>
                        Manage Connections
                    </Link>
                    <button onClick={() => setScheduleModalOpen(true)} style={{
                        display: 'flex', alignItems: 'center', gap: '6px',
                        padding: '9px 18px', borderRadius: '10px',
                        border: 'none', background: 'var(--blue)',
                        color: 'white', fontSize: '13px', fontWeight: 600,
                        cursor: 'pointer', transition: 'all 0.15s ease',
                    }}>
                        <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, stroke: 'currentColor', fill: 'none', strokeWidth: 2.5 }}>
                            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                        </svg>
                        Schedule Posts
                    </button>
                </div>
            </div>

            {/* Stats bar — matching design */}
            <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px',
                marginBottom: '28px',
            }}>
                {/* Scheduled this month */}
                <div style={{
                    background: 'white', borderRadius: '14px', padding: '18px 20px',
                    border: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', gap: '14px',
                }}>
                    <div style={{
                        width: 42, height: 42, borderRadius: '12px',
                        background: 'rgba(51,122,255,0.08)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                        <svg viewBox="0 0 24 24" style={{ width: 20, height: 20, stroke: 'var(--blue)', fill: 'none', strokeWidth: 2 }}>
                            <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
                        </svg>
                    </div>
                    <div>
                        <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-1)', lineHeight: 1.1 }}>{stats.total}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 500, marginTop: '2px' }}>Total this month</div>
                    </div>
                </div>

                {/* Posts published */}
                <div style={{
                    background: 'white', borderRadius: '14px', padding: '18px 20px',
                    border: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', gap: '14px',
                }}>
                    <div style={{
                        width: 42, height: 42, borderRadius: '12px',
                        background: 'rgba(52,199,89,0.08)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                        <svg viewBox="0 0 24 24" style={{ width: 20, height: 20, stroke: '#34C759', fill: 'none', strokeWidth: 2 }}>
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
                        </svg>
                    </div>
                    <div>
                        <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-1)', lineHeight: 1.1 }}>{stats.posted}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 500, marginTop: '2px' }}>Posts published</div>
                    </div>
                </div>

                {/* Pending approval */}
                <div style={{
                    background: 'white', borderRadius: '14px', padding: '18px 20px',
                    border: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', gap: '14px',
                }}>
                    <div style={{
                        width: 42, height: 42, borderRadius: '12px',
                        background: 'rgba(255,159,10,0.08)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                        <svg viewBox="0 0 24 24" style={{ width: 20, height: 20, stroke: '#FF9F0A', fill: 'none', strokeWidth: 2 }}>
                            <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                        </svg>
                    </div>
                    <div>
                        <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-1)', lineHeight: 1.1 }}>{stats.upcoming}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 500, marginTop: '2px' }}>Upcoming</div>
                    </div>
                </div>

                {/* Connected platforms */}
                <div style={{
                    background: 'white', borderRadius: '14px', padding: '18px 20px',
                    border: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', gap: '14px',
                }}>
                    <div style={{
                        width: 42, height: 42, borderRadius: '12px',
                        background: 'rgba(94,92,230,0.08)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                        <svg viewBox="0 0 24 24" style={{ width: 20, height: 20, stroke: '#5E5CE6', fill: 'none', strokeWidth: 2 }}>
                            <rect x="2" y="3" width="20" height="14" rx="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" />
                        </svg>
                    </div>
                    <div>
                        <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-1)', lineHeight: 1.1 }}>{connectedCount}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 500, marginTop: '2px' }}>Connected platforms</div>
                    </div>
                </div>
            </div>

            {/* Main layout: calendar + sidebar */}
            <div style={{ display: 'flex', gap: '24px' }}>
                {/* Left: Calendar */}
                <div style={{ flex: 1, minWidth: 0 }}>
                    {/* Month navigator */}
                    <div style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        marginBottom: '16px',
                        background: 'white', borderRadius: '14px', border: '1px solid var(--border)',
                        padding: '12px 16px',
                    }}>
                        <button onClick={prevMonth} style={{
                            width: 36, height: 36, borderRadius: '10px', border: '1px solid var(--border)',
                            background: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                            <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: 'var(--text-2)', fill: 'none', strokeWidth: 2 }}>
                                <polyline points="15 18 9 12 15 6" />
                            </svg>
                        </button>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <span style={{ fontWeight: 700, fontSize: '18px' }}>{formatMonth(year, month)}</span>
                            <button onClick={goToday} style={{
                                padding: '6px 14px', borderRadius: '8px',
                                border: '1px solid var(--border)', background: 'white',
                                fontSize: '12px', fontWeight: 600, color: 'var(--blue)',
                                cursor: 'pointer',
                            }}>
                                Today
                            </button>
                        </div>
                        <button onClick={nextMonth} style={{
                            width: 36, height: 36, borderRadius: '10px', border: '1px solid var(--border)',
                            background: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                            <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: 'var(--text-2)', fill: 'none', strokeWidth: 2 }}>
                                <polyline points="9 18 15 12 9 6" />
                            </svg>
                        </button>
                    </div>

                    {/* Day headers */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '1px', background: 'var(--border)', borderRadius: '14px', overflow: 'hidden', border: '1px solid var(--border)' }}>
                        {DAY_NAMES.map(d => (
                            <div key={d} style={{
                                background: 'var(--surface-hover)',
                                padding: '10px 0', textAlign: 'center',
                                fontSize: '11px', fontWeight: 700, color: 'var(--text-3)',
                                textTransform: 'uppercase', letterSpacing: '0.5px',
                            }}>
                                {d}
                            </div>
                        ))}

                        {/* Calendar cells */}
                        {days.map((day, i) => {
                            const dayPosts = day ? (postsByDay[day] || []) : [];
                            return (
                                <div key={i} style={{
                                    background: isToday(day) ? 'rgba(51,122,255,0.04)' : 'white',
                                    minHeight: '90px', padding: '6px',
                                    display: 'flex', flexDirection: 'column',
                                }}>
                                    {day !== null && (
                                        <>
                                            <div style={{
                                                fontSize: '13px', fontWeight: isToday(day) ? 700 : 500,
                                                color: isToday(day) ? 'var(--blue)' : 'var(--text-2)',
                                                marginBottom: '4px',
                                                display: 'flex', alignItems: 'center', gap: '4px',
                                            }}>
                                                {isToday(day) && <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--blue)' }} />}
                                                {day}
                                            </div>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                                                {dayPosts.slice(0, 3).map(p => {
                                                    const sts = STATUS_STYLES[p.status] || STATUS_STYLES.scheduled;
                                                    return (
                                                        <div key={p.id} style={{
                                                            padding: '3px 6px', borderRadius: '4px',
                                                            background: sts.bg, fontSize: '10px', fontWeight: 600,
                                                            color: sts.color, whiteSpace: 'nowrap',
                                                            overflow: 'hidden', textOverflow: 'ellipsis',
                                                        }}>
                                                            {p.platform?.charAt(0).toUpperCase() || ''}
                                                            {' '}
                                                            {new Date(p.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                        </div>
                                                    );
                                                })}
                                                {dayPosts.length > 3 && (
                                                    <div style={{ fontSize: '10px', color: 'var(--text-3)', fontWeight: 600 }}>
                                                        +{dayPosts.length - 3} more
                                                    </div>
                                                )}
                                            </div>
                                        </>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Right sidebar */}
                <div style={{ width: '280px', flexShrink: 0 }}>
                    <div style={{
                        background: 'white', borderRadius: '14px', border: '1px solid var(--border)',
                        padding: '20px', position: 'sticky', top: '100px',
                    }}>
                        <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '16px' }}>
                            Upcoming (7 days)
                        </h3>
                        {loading ? (
                            <div style={{ color: 'var(--text-3)', fontSize: '13px' }}>Loading...</div>
                        ) : upcoming.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text-3)' }}>
                                <svg viewBox="0 0 24 24" style={{ width: 32, height: 32, stroke: 'var(--border)', fill: 'none', strokeWidth: 1.5, marginBottom: '8px' }}>
                                    <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
                                </svg>
                                <div style={{ fontSize: '13px' }}>No upcoming posts</div>
                                <Link href="/videos" style={{ fontSize: '12px', color: 'var(--blue)', textDecoration: 'none', fontWeight: 600, marginTop: '8px', display: 'inline-block' }}>
                                    Schedule from Videos →
                                </Link>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                {upcoming.map(p => (
                                    <div key={p.id} style={{
                                        padding: '12px', borderRadius: '10px',
                                        border: '1px solid var(--border)', background: 'var(--surface-hover)',
                                    }}>
                                        <div style={{ display: 'flex', gap: '6px', marginBottom: '6px', flexWrap: 'wrap' }}>
                                            {p.platform && (
                                                <span style={{
                                                    fontSize: '10px', fontWeight: 700,
                                                    padding: '2px 6px', borderRadius: '8px',
                                                    background: `${PLATFORM_COLORS[p.platform] ?? '#666'}18`,
                                                    color: PLATFORM_COLORS[p.platform] ?? '#666',
                                                }}>
                                                    {p.platform}
                                                </span>
                                            )}
                                        </div>
                                        <div style={{ fontSize: '12px', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px' }}>
                                            <svg viewBox="0 0 24 24" style={{ width: 12, height: 12, stroke: 'currentColor', fill: 'none', strokeWidth: 2 }}>
                                                <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                                            </svg>
                                            {new Date(p.scheduled_at).toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                        </div>
                                        {p.caption && (
                                            <div style={{
                                                fontSize: '11px', color: 'var(--text-3)', overflow: 'hidden',
                                                textOverflow: 'ellipsis', display: '-webkit-box',
                                                WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                                            }}>
                                                {p.caption}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <SchedulePostModal
                isOpen={scheduleModalOpen}
                onClose={() => setScheduleModalOpen(false)}
            />
        </div>
    );
}
