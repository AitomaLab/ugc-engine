'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useRef, useEffect } from 'react';
import { useApp } from '@/providers/AppProvider';
import { ProjectSwitcher } from '@/components/layout/ProjectSwitcher';
import { supabase } from '@/lib/supabaseClient';
import { apiFetch } from '@/lib/utils';
import { useTranslation } from '@/lib/i18n';
import type { Notification } from '@/lib/types';

// SVG icon components — no emoji allowed
const IconHome = () => <svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></svg>;
const IconGrid = () => <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>;
const IconPlay = () => <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><polygon points="10,8 16,12 10,16" /></svg>;
const IconVideo = () => <svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></svg>;
const IconUser = () => <svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" /></svg>;
const IconFile = () => <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>;
const IconBox = () => <svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /></svg>;
const IconActivity = () => <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>;
const IconArrowRight = () => <svg viewBox="0 0 24 24"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /><polyline points="10 17 15 12 10 7" /><line x1="15" y1="12" x2="3" y2="12" /></svg>;
const IconPlus = () => <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>;
const IconBell = () => <svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></svg>;
const IconSettings = () => <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>;
const IconStar = () => <svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" /></svg>;
const IconLogOut = () => <svg viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>;
const IconFilm = () => <svg viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" /><line x1="7" y1="2" x2="7" y2="22" /><line x1="17" y1="2" x2="17" y2="22" /><line x1="2" y1="12" x2="22" y2="12" /><line x1="2" y1="7" x2="7" y2="7" /><line x1="2" y1="17" x2="7" y2="17" /><line x1="17" y1="7" x2="22" y2="7" /><line x1="17" y1="17" x2="22" y2="17" /></svg>;
const IconCalendar = () => <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>;

const NAV_ITEMS = [
    { href: '/', labelKey: 'nav.dashboard', label: 'Home', Icon: IconHome },
    { divider: true },
    { href: '/videos', labelKey: 'nav.videos', label: 'Videos', Icon: IconVideo },
    { href: '/influencers', labelKey: 'nav.influencers', label: 'Influencers', Icon: IconUser },
    { href: '/scripts', labelKey: 'nav.scripts', label: 'Scripts', Icon: IconFile },
    { href: '/products', labelKey: 'nav.products', label: 'Products', Icon: IconBox },
    { href: '/schedule', labelKey: 'nav.schedule', label: 'Schedule', Icon: IconCalendar },
    { divider: true },
    { href: '/activity', labelKey: 'nav.activity', label: 'Activity', Icon: IconActivity },
];

// ── Language Toggle ────────────────────────────────────────────────────
function LangToggle() {
    const { lang, setLang } = useTranslation();
    return (
        <button
            className="lang-toggle"
            onClick={() => setLang(lang === 'en' ? 'es' : 'en')}
            title={lang === 'en' ? 'Switch to Spanish' : 'Cambiar a Inglés'}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: '2px',
                padding: '4px 8px',
                borderRadius: '6px',
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                transition: 'all 0.15s ease',
                whiteSpace: 'nowrap' as const,
            }}
        >
            <span style={{
                padding: '2px 6px',
                borderRadius: '4px',
                background: lang === 'en' ? 'var(--blue, #337AFF)' : 'transparent',
                color: lang === 'en' ? '#fff' : 'var(--text-3, #999)',
                transition: 'all 0.15s ease',
                fontWeight: lang === 'en' ? 700 : 500,
            }}>EN</span>
            <span style={{
                padding: '2px 6px',
                borderRadius: '4px',
                background: lang === 'es' ? 'var(--blue, #337AFF)' : 'transparent',
                color: lang === 'es' ? '#fff' : 'var(--text-3, #999)',
                transition: 'all 0.15s ease',
                fontWeight: lang === 'es' ? 700 : 500,
            }}>ES</span>
        </button>
    );
}

function NavItem({ href, label, Icon, onClick }: { href: string; label: string; Icon: React.ComponentType; onClick?: () => void }) {
    const pathname = usePathname();
    const isActive = pathname === href || (href !== '/' && pathname.startsWith(href));
    return (
        <Link href={href} className={`nav-item ${isActive ? 'active' : ''}`} onClick={onClick}>
            <Icon />
            {label}
        </Link>
    );
}

function CreateDropdown() {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);
    const pathname = usePathname();
    const isActive = pathname === '/create' || pathname === '/cinematic';
    const { t } = useTranslation();

    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    return (
        <div ref={ref} style={{ position: 'relative' }}>
            <button
                className={`btn-create ${isActive ? 'active' : ''}`}
                onClick={() => setOpen(o => !o)}
            >
                <IconPlus />
                <span className="btn-label">{t('common.create')}</span>
                <svg viewBox="0 0 24 24" style={{ width: '12px', height: '12px', stroke: 'currentColor', fill: 'none', strokeWidth: 2, marginLeft: '2px', transition: 'transform 0.15s', transform: open ? 'rotate(180deg)' : 'none' }}>
                    <polyline points="6 9 12 15 18 9" />
                </svg>
            </button>
            {open && (
                <div style={{
                    position: 'absolute', top: 'calc(100% + 8px)', right: 0,
                    background: 'white', borderRadius: '12px', minWidth: '260px',
                    boxShadow: '0 12px 36px rgba(51,122,255,0.18)',
                    border: '1px solid var(--border-soft)', zIndex: 200,
                    overflow: 'hidden', animation: 'cssFadeIn 0.15s ease',
                }}>
                    <Link href="/create" className="cd-item" onClick={() => setOpen(false)}>
                        <div className="cd-icon">
                            <svg viewBox="0 0 24 24"><polygon points="23 7 16 12 23 17 23 7" /><rect x="1" y="5" width="15" height="14" rx="2" /></svg>
                        </div>
                        <div><div className="cd-label">{t('header.createVideo')}</div><div className="cd-desc">{t('create.title')}</div></div>
                    </Link>
                    <Link href="/cinematic" className="cd-item" onClick={() => setOpen(false)}>
                        <div className="cd-icon"><IconFilm /></div>
                        <div><div className="cd-label">{t('header.cinematicShots')}</div><div className="cd-desc">{t('products.cinematic')}</div></div>
                    </Link>
                </div>
            )}
        </div>
    );
}

function timeAgo(dateStr: string): string {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const diff = Math.max(0, now - then);
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(dateStr).toLocaleDateString();
}

const NOTIF_ICONS: Record<string, { color: string; path: string }> = {
    job_success:    { color: 'var(--green)',  path: 'M20 6L9 17l-5-5' },
    job_failed:     { color: 'var(--red)',    path: 'M18 6L6 18M6 6l12 12' },
    job_processing: { color: 'var(--blue)',   path: 'M12 2v4m0 12v4m-7.07-2.93l2.83-2.83m8.48-8.48l2.83-2.83M2 12h4m12 0h4m-2.93 7.07l-2.83-2.83M7.76 7.76L4.93 4.93' },
    job_pending:    { color: 'var(--amber)',  path: 'M12 6v6l4 2' },
    script_created: { color: '#6B4EFF',       path: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6' },
};

function NotificationDropdown() {
    const { t } = useTranslation();
    const [open, setOpen] = useState(false);
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [readIds, setReadIds] = useState<Set<string>>(new Set());
    const [loading, setLoading] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    // Load read IDs from localStorage on mount
    useEffect(() => {
        try {
            const stored = localStorage.getItem('notif_read_ids');
            if (stored) setReadIds(new Set(JSON.parse(stored)));
        } catch { /* ignore */ }
    }, []);

    // Click-outside handler
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    // Fetch notifications when dropdown opens
    useEffect(() => {
        if (!open) return;
        let cancelled = false;
        setLoading(true);
        apiFetch<Notification[]>('/api/notifications?limit=20')
            .then(data => { if (!cancelled) setNotifications(data); })
            .catch(() => {})
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [open]);

    // Auto-refresh every 30s when open
    useEffect(() => {
        if (!open) return;
        const interval = setInterval(() => {
            apiFetch<Notification[]>('/api/notifications?limit=20')
                .then(setNotifications)
                .catch(() => {});
        }, 30000);
        return () => clearInterval(interval);
    }, [open]);

    const hasUnread = notifications.some(n => !readIds.has(n.id));

    const markAllRead = () => {
        const ids = new Set(notifications.map(n => n.id));
        setReadIds(ids);
        try { localStorage.setItem('notif_read_ids', JSON.stringify([...ids])); } catch { /* ignore */ }
    };

    const handleItemClick = (n: Notification) => {
        const next = new Set(readIds);
        next.add(n.id);
        setReadIds(next);
        try { localStorage.setItem('notif_read_ids', JSON.stringify([...next])); } catch { /* ignore */ }
        setOpen(false);
        if (n.type === 'job_success' && n.video_url) {
            window.location.href = '/videos';
        } else if (n.type === 'script_created') {
            window.location.href = '/scripts';
        } else {
            window.location.href = '/activity';
        }
    };

    return (
        <div ref={ref} className={`notif-wrapper hide-mobile ${open ? 'open' : ''}`}>
            <button className="icon-btn" onClick={() => setOpen(o => !o)}>
                <IconBell />
                {hasUnread && <span className="notif-dot" />}
            </button>
            {open && (
                <div className="notif-dropdown" onClick={e => e.stopPropagation()}>
                    <div className="notif-header">
                        <span className="notif-title">{t('notif.title')}</span>
                        {notifications.length > 0 && (
                            <button className="notif-mark-read" onClick={markAllRead}>{t('notif.markAllRead')}</button>
                        )}
                    </div>
                    <div className="notif-list">
                        {loading && notifications.length === 0 && (
                            <div className="notif-empty">{t('notif.loading')}</div>
                        )}
                        {!loading && notifications.length === 0 && (
                            <div className="notif-empty">
                                <svg viewBox="0 0 24 24" style={{ width: 32, height: 32, stroke: 'var(--text-3)', fill: 'none', strokeWidth: 1.5, marginBottom: 8 }}>
                                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" />
                                </svg>
                                <div>{t('notif.empty')}</div>
                            </div>
                        )}
                        {notifications.map(n => {
                            const icon = NOTIF_ICONS[n.type] || NOTIF_ICONS.job_pending;
                            const isUnread = !readIds.has(n.id);

                            // Translate notification title based on type
                            const TITLE_MAP: Record<string, string> = {
                                job_success: t('notif.videoReady'),
                                job_failed: t('notif.generationFailed'),
                                job_processing: t('notif.generatingVideo'),
                                job_pending: t('notif.jobQueued'),
                                script_created: t('notif.scriptCreated'),
                            };
                            const translatedTitle = TITLE_MAP[n.type] || t('notif.jobUpdate');

                            // Translate notification message
                            const translateMessage = (msg: string): string => {
                                if (msg.includes('completed successfully')) {
                                    const name = msg.replace(' completed successfully', '');
                                    return `${name} ${t('notif.completedSuccess')}`;
                                }
                                if (msg.includes('failed:')) {
                                    const parts = msg.split('failed:');
                                    return `${parts[0]}${t('notif.failed')}: ${parts[1]?.trim() || ''}`;
                                }
                                if (msg.includes('is generating')) {
                                    const name = msg.split(' is generating')[0];
                                    const pct = msg.match(/\((\d+%)\)/)?.[1] || '';
                                    return `${name} ${t('notif.isGenerating')}${pct ? ` (${pct})` : ''}`;
                                }
                                if (msg.includes('is queued for generation')) {
                                    const name = msg.replace(' is queued for generation', '');
                                    return `${name} ${t('notif.isQueued')}`;
                                }
                                if (msg === 'New script') return t('notif.newScript');
                                return msg;
                            };
                            const translatedMessage = translateMessage(n.message);

                            return (
                                <div
                                    key={n.id}
                                    className={`notif-item ${isUnread ? 'unread' : ''}`}
                                    onClick={() => handleItemClick(n)}
                                >
                                    <div className="notif-icon" style={{ background: `${icon.color}18`, color: icon.color }}>
                                        <svg viewBox="0 0 24 24"><path d={icon.path} /></svg>
                                    </div>
                                    <div className="notif-content">
                                        <div className="notif-item-title">{translatedTitle}</div>
                                        <div className="notif-message">{translatedMessage}</div>
                                        <div className="notif-time">{n.timestamp ? timeAgo(n.timestamp) : ''}</div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}

function ProfileDropdown() {
    const { t } = useTranslation();
    const [open, setOpen] = useState(false);
    const { profile, subscription, wallet } = useApp();

    const initials = profile?.name
        ? profile.name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
        : profile?.email
            ? profile.email[0].toUpperCase()
            : 'U';

    const planName = subscription?.plan?.name || 'Free';
    const balance = wallet?.balance ?? 0;
    const monthlyCredits = subscription?.plan?.credits_monthly ?? 0;
    const used = monthlyCredits > 0 ? monthlyCredits - balance : 0;
    const percentage = monthlyCredits > 0 ? Math.round((balance / monthlyCredits) * 100) : 0;

    const handleSignOut = async () => {
        await supabase.auth.signOut();
        window.location.href = '/login';
    };

    return (
        <div className={`profile-wrapper ${open ? 'open' : ''}`} onClick={() => setOpen(!open)}>
            <div className="avatar">{initials}</div>
            <div className="profile-dropdown" onClick={e => e.stopPropagation()}>
                <div className="pd-header">
                    <div className="pd-avatar">{initials}</div>
                    <div>
                        <div className="pd-name">{profile?.name || profile?.email || 'User'}</div>
                        <div className="pd-plan">{planName} {t('header.plan')}</div>
                    </div>
                </div>
                <div className="pd-credits">
                    <div className="pd-credits-label">{t('dashboard.credits')}</div>
                    <div className="pd-credits-row">
                        <span className="pd-credits-value">{balance.toLocaleString()}</span>
                        {monthlyCredits > 0 && <span className="pd-credits-total">{t('header.of')} {monthlyCredits.toLocaleString()}</span>}
                    </div>
                    {monthlyCredits > 0 && (
                        <>
                            <div className="pd-bar-bg"><div className="pd-bar-fill" style={{ width: `${percentage}%` }} /></div>
                            <div className="pd-bar-labels"><span>{t('header.used')} {used.toLocaleString()}</span><span>{percentage}% {t('header.remaining')}</span></div>
                        </>
                    )}
                    <button className="pd-topup" onClick={() => { window.location.href = '/manage?topup=1'; }}>{t('header.topUp')}</button>
                </div>
                <Link href="/profile" className="pd-menu-item"><IconUser />{t('nav.profile')}</Link>
                <Link href="/projects" className="pd-menu-item"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>{t('nav.projects')}</Link>
                <Link href="/manage" className="pd-menu-item"><IconSettings />{t('nav.settings')}</Link>
                <Link href="/upgrade" className="pd-menu-item"><IconStar />{t('header.upgradePlan')}</Link>
                <div className="pd-divider" />
                <div className="pd-menu-item danger" onClick={handleSignOut}><IconLogOut />{t('nav.signOut')}</div>
            </div>
        </div>
    );
}

export function Header() {
    const [menuOpen, setMenuOpen] = useState(false);
    const { t } = useTranslation();
    return (
        <header className="header">
            <button className="menu-toggle" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle menu">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
                    {menuOpen ? (
                        <><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></>
                    ) : (
                        <><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" /></>
                    )}
                </svg>
            </button>

            <Link href="/" className="logo">
                <img src="/StudioLogo_Black.svg" alt="Studio Logo" style={{ height: '32px' }} />
            </Link>

            <nav className={`main-nav ${menuOpen ? 'open' : ''}`}>
                {NAV_ITEMS.map((item, i) =>
                    'divider' in item ? (
                        <div key={`div-${i}`} className="nav-divider" />
                    ) : (
                        <NavItem key={item.href} href={item.href!} label={item.labelKey ? t(item.labelKey) : item.label!} Icon={item.Icon!} onClick={() => setMenuOpen(false)} />
                    )
                )}
                {/* Mobile-only items */}
                <div className="nav-divider mobile-only" />
                <Link href="/create" className="nav-item mobile-only-item" onClick={() => setMenuOpen(false)}>
                    <IconPlay /> {t('header.createVideo')}
                </Link>
                <Link href="/cinematic" className="nav-item mobile-only-item" onClick={() => setMenuOpen(false)}>
                    <IconFilm /> {t('header.cinematicShots')}
                </Link>
                <div className="nav-divider mobile-only" />
                <Link href="/profile" className="nav-item mobile-only-item" onClick={() => setMenuOpen(false)}>
                    <IconUser /> {t('nav.profile')}
                </Link>
                <Link href="/manage" className="nav-item mobile-only-item" onClick={() => setMenuOpen(false)}>
                    <IconSettings /> {t('nav.settings')}
                </Link>
            </nav>

            <div className="header-actions">
                <ProjectSwitcher />
                <CreateDropdown />
                <div className="nav-divider hide-mobile" />
                <LangToggle />
                <NotificationDropdown />
                <ProfileDropdown />
            </div>
        </header>
    );
}
