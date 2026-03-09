'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState, useCallback } from 'react';
import { getApiUrl } from '@/lib/utils';

// ---------------------------------------------------------------------------
// SVG Icon Components
// ---------------------------------------------------------------------------

function StudioIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="7" rx="2" />
            <rect x="14" y="3" width="7" height="7" rx="2" />
            <rect x="3" y="14" width="7" height="7" rx="2" />
            <rect x="14" y="14" width="7" height="7" rx="2" />
        </svg>
    );
}

function CreateIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 5v14m-7-7h14" />
            <circle cx="12" cy="12" r="10" />
        </svg>
    );
}

function LibraryIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
            <path d="M8 7h8m-8 4h6" />
        </svg>
    );
}

function ActivityIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
    );
}

function BellIcon() {
    return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 01-3.46 0" />
        </svg>
    );
}

// ---------------------------------------------------------------------------
// Navigation Items
// ---------------------------------------------------------------------------

const navItems = [
    { href: '/', label: 'Studio', icon: StudioIcon, shortcut: null },
    { href: '/create', label: 'Create', icon: CreateIcon, shortcut: 'N' },
    { href: '/library', label: 'Library', icon: LibraryIcon, shortcut: 'L' },
    { href: '/activity', label: 'Activity', icon: ActivityIcon, shortcut: null },
];

// ---------------------------------------------------------------------------
// Sidebar Component
// ---------------------------------------------------------------------------

export default function Sidebar() {
    const pathname = usePathname();
    const router = useRouter();
    const [notifications, setNotifications] = useState<string[]>([]);
    const [showNotifications, setShowNotifications] = useState(false);

    // Keyboard shortcuts
    useEffect(() => {
        function handleKeyDown(e: KeyboardEvent) {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;

            if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
                e.preventDefault();
                router.push('/create');
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
                e.preventDefault();
                router.push('/library');
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                router.push('/library');
            } else if (e.key === 'Escape') {
                setShowNotifications(false);
            }
        }

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [router]);

    // Poll for notifications (recently completed/failed jobs)
    const fetchNotifications = useCallback(async () => {
        try {
            const res = await fetch(`${getApiUrl()}/jobs?limit=10`);
            if (!res.ok) return;
            const jobs = await res.json();
            const recent = jobs
                .filter((j: { status: string; created_at: string }) => {
                    const age = Date.now() - new Date(j.created_at).getTime();
                    return age < 3600000 && (j.status === 'success' || j.status === 'failed');
                })
                .map((j: { id: string; status: string }) =>
                    j.status === 'success'
                        ? `Video ${j.id.substring(0, 6)} — Completed`
                        : `Job ${j.id.substring(0, 6)} — Failed`
                );
            setNotifications(recent);
        } catch { /* silent */ }
    }, []);

    useEffect(() => {
        fetchNotifications();
        const interval = setInterval(fetchNotifications, 30000);
        return () => clearInterval(interval);
    }, [fetchNotifications]);

    const isActive = (href: string) => {
        if (href === '/') return pathname === '/';
        return pathname.startsWith(href);
    };

    return (
        <aside className="w-64 flex flex-col sticky top-0 h-screen glass-dark border-r border-white/5">
            {/* Logo */}
            <div className="p-6 border-b border-white/5">
                <img src="/studio-logo-white.svg" alt="Aitoma Studio" className="h-8 w-auto" />
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-3 space-y-1 mt-2">
                {navItems.map(({ href, label, icon: Icon, shortcut }) => {
                    const active = isActive(href);
                    return (
                        <Link
                            key={href}
                            href={href}
                            className={`
                sidebar-link group flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200
                ${active
                                    ? 'bg-white/10 text-white border-l-2 border-[#337AFF] shadow-[inset_0_0_20px_rgba(51,122,255,0.08)]'
                                    : 'text-white/50 hover:text-white hover:bg-white/[0.08] border-l-2 border-transparent'
                                }
              `}
                        >
                            <span className={`transition-colors duration-200 ${active ? 'text-[#337AFF]' : 'text-white/30 group-hover:text-white/70'}`}>
                                <Icon />
                            </span>
                            <span className="font-medium text-sm">{label}</span>
                            {shortcut && (
                                <span className="ml-auto text-[10px] text-white/20 font-mono opacity-0 group-hover:opacity-100 transition-opacity">
                                    {shortcut}
                                </span>
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* Notifications */}
            <div className="px-4 pb-2 relative">
                <button
                    onClick={() => setShowNotifications(!showNotifications)}
                    className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-white/50 hover:text-white hover:bg-white/[0.08] transition-all text-sm"
                >
                    <BellIcon />
                    <span className="font-medium">Notifications</span>
                    {notifications.length > 0 && (
                        <span className="ml-auto w-5 h-5 rounded-full bg-[#337AFF] text-white text-[10px] font-bold flex items-center justify-center">
                            {notifications.length}
                        </span>
                    )}
                </button>

                {showNotifications && (
                    <div className="absolute bottom-14 left-3 right-3 glass-dark border border-white/[0.08] rounded-xl shadow-2xl p-3 space-y-2 z-50 max-h-60 overflow-y-auto">
                        {notifications.length === 0 ? (
                            <p className="text-xs text-white/30 text-center py-4 italic">No recent notifications</p>
                        ) : (
                            notifications.map((n, i) => (
                                <div key={i} className="text-xs text-white/70 p-2 rounded-lg bg-white/5 border border-white/[0.08]">
                                    {n}
                                </div>
                            ))
                        )}
                    </div>
                )}
            </div>

            {/* User Profile */}
            <div className="p-4 border-t border-white/5">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl gradient-cta flex items-center justify-center text-white font-bold text-sm">
                        U
                    </div>
                    <div className="overflow-hidden">
                        <p className="text-white font-medium text-sm truncate">Creator</p>
                        <p className="text-[10px] text-white/40">Pro Account</p>
                    </div>
                </div>
            </div>
        </aside>
    );
}
